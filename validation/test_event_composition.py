"""Fictional final-prose checks; no external model, household writes or audio."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from jarvis.event_composition import board,compose,validate,strict,REVIEW
from jarvis.household_activities import notes
from jarvis.sentence_stream import sentence_sink
import test_preparation_wording as fixtures


class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.event=fixtures.WordingTests().event(location='Current Hall')
        self.note=dict(notes([self.event],'preparation')[0],id='N1')
        self.facts=board('What should Mia prepare for tomorrow?',[self.event],[self.note],None,'2026-10-23')
        self.good='Tomorrow, Mia has orchestra practice at 14:15 at Current Hall. Have the instrument and sheet music ready as usual.'
    def check(self,text):return validate(json.dumps({'answer':text}),self.facts)
    def test_natural_grounded_answer_passes_without_changing_facts(self):
        before=deepcopy(self.facts);self.assertEqual(self.check(self.good),self.good);self.assertEqual(before,self.facts)
    def test_wrong_time_or_missing_start_rejected(self):
        for value in ('15:15','later','14:15 and 16:00'):
            with self.assertRaises(ValueError):self.check(self.good.replace('14:15',value))
    def test_unlisted_equipment_rejected_before_semantic_review(self):
        with self.assertRaises(ValueError):self.check(self.good+' Bring goggles and a towel.')
    def test_question_cannot_introduce_new_facts(self):
        self.facts['question']='Should Mia bring goggles and a towel?'
        with self.assertRaises(ValueError):self.check(self.good+' Bring goggles and a towel.')
    def test_missing_selected_equipment_rejected(self):
        with self.assertRaises(ValueError):self.check(self.good.replace('and sheet music',''))
    def test_unknown_person_or_activity_rejected(self):
        for phrase in ('Emrik has swimming','Mia has swimming'):
            with self.assertRaises(ValueError):self.check(self.good.replace('Mia has orchestra practice',phrase))
    def test_usual_must_not_disappear(self):
        with self.assertRaises(ValueError):self.check(self.good.replace('as usual',''))
    def test_no_invented_routine_but_whole_current_usual_instruction_is_allowed(self):
        event={**self.event,'selected_excerpts':['Bring the usual folder.']}
        self.facts=board('prepare',[event],[],None,'2026-10-23')
        text='Tomorrow, Mia has orchestra practice at 14:15 at Current Hall. The instructions say: Bring the usual folder.'
        self.check(text)
        with self.assertRaises(ValueError):self.check(text+' As usual, prepare for the session.')
    def test_extra_duration_not_sourced_from_clock_digits(self):
        with self.assertRaises(ValueError):self.check(self.good+' It takes 15 minutes.')
    def test_date_scope_wrong_today_is_rejected(self):
        with self.assertRaises(ValueError):self.check(self.good.replace('Tomorrow','Today'))
    def test_wrong_speaker_claim_is_rejected(self):
        with self.assertRaises(ValueError):self.check(self.good.replace('Mia has','You have'))
    def test_raw_fields_or_added_question_rejected(self):
        for suffix in (' Usual equipment for Mia: instrument.',' Is that ready?'):
            with self.assertRaises(ValueError):self.check(self.good+suffix)
    def test_action_claim_links_and_ids_rejected(self):
        for suffix in (' I have booked it.',' See https://invalid.example.',' F1 N1'):
            with self.assertRaises(ValueError):self.check(self.good+suffix)
    def test_duplicate_schema_keys_rejected(self):
        with self.assertRaises(ValueError):strict('{"answer":"one","answer":"two"}',('answer',))
    def test_protected_negation_and_condition_must_remain_whole(self):
        for instruction in ('Do not bring water.','If the session is outdoors, bring a coat.'):
            event={**self.event,'selected_excerpts':[instruction]}
            self.facts=board('prepare',[event],[self.note],None,'2026-10-23')
            self.check(self.good+' The instructions say: “'+instruction+'”')
            with self.assertRaises(ValueError):self.check(self.good)
    def test_all_day_never_becomes_a_clock_time(self):
        event={**self.event,'all_day':True}
        self.facts=board('prepare',[event],[self.note],None,'2026-10-23')
        self.check(self.good.replace('at 14:15','all day'))
        with self.assertRaises(ValueError):self.check(self.good)
    def test_unselected_usual_fields_not_exposed(self):
        facts=board('prepare',[self.event],[],None,'2026-10-23')
        self.assertFalse(facts['usual_notes']);self.assertFalse(facts['required_words'])
        self.assertNotIn('Fictional School',json.dumps(facts))
    def test_usual_venue_cannot_be_upgraded_even_with_usual_elsewhere(self):
        event={**self.event,'location':''}
        note=dict(notes([event],'preparation')[0],id='N1')
        self.facts=board('prepare',[event],[note],None,'2026-10-23')
        invalid=self.good.replace('Current Hall','Fictional School')
        with self.assertRaises(ValueError):self.check(invalid)
        self.check(self.good.replace(' at Current Hall','')+' It usually takes place at Fictional School.')
    def test_usual_duration_not_confirmed_all_day_length(self):
        event={**self.event,'all_day':True,'activity_profile':{**self.event['activity_profile'],'duration_minutes':60}}
        note=dict(notes([event],'preparation')[0],id='N1')
        self.facts=board('prepare',[event],[note],None,'2026-10-23')
        start=self.good.replace('at 14:15','all day')
        for suffix in ('',' It lasts 60 minutes.',' Its usual duration is 60 minutes.'):
            with self.assertRaises(ValueError):self.check(start+suffix)
        self.check(start+' Its usual duration is 60 minutes, not a confirmed duration for the calendar entry.')


class Provider:
    policy=SimpleNamespace(enabled=True,maximum_input_characters=12000)
    def __init__(self,answer,verdict=None):self.answer=answer;self.verdict=verdict or {'grounded':True,'complete':True,'natural':True};self.calls=0
    def reason_local(self,**kw):
        assert sentence_sink.get() is None
        self.calls+=1
        return {'status':'success','message':json.dumps(self.verdict if kw['instructions']==REVIEW else {'answer':self.answer})}


class ComposeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixture=CompositionTests();fixture.setUp();self.facts=fixture.facts;self.good=fixture.good
        self.lock=asyncio.Lock();self.valid=lambda:True
    async def test_actual_draft_and_review_are_distinct_calls(self):
        provider=Provider(self.good);out=await compose(provider,self.facts,self.lock,self.valid)
        self.assertEqual(out['text'],self.good);self.assertEqual(out['calls'],2);self.assertFalse(self.lock.locked())
    async def test_reviewer_rejects_semantic_venue_upgrade_even_if_tokens_exist(self):
        provider=Provider(self.good,{'grounded':False,'complete':True,'natural':True})
        out=await compose(provider,self.facts,self.lock,self.valid)
        self.assertIsNone(out['text']);self.assertEqual(out['reason'],'review')
    async def test_unsafe_draft_never_reaches_reviewer(self):
        provider=Provider(self.good+' Bring goggles.')
        out=await compose(provider,self.facts,self.lock,self.valid)
        self.assertIsNone(out['text']);self.assertEqual(out['calls'],2);self.assertEqual(out['reason'],'validation')
    async def test_scope_changed_after_inference_does_not_return_draft(self):
        provider=Provider(self.good)
        out=await compose(provider,self.facts,self.lock,lambda:provider.calls==0)
        self.assertIsNone(out['text']);self.assertEqual(out['reason'],'changed')
    async def test_disabled_backend_makes_no_model_call(self):
        provider=Provider(self.good);provider.policy=SimpleNamespace(enabled=False)
        out=await compose(provider,self.facts,self.lock,self.valid)
        self.assertEqual(out['reason'],'disabled');self.assertEqual(provider.calls,0)
    async def test_bad_review_boolean_never_claims_model_composition(self):
        provider=Provider(self.good,{'grounded':'true','complete':True,'natural':True})
        self.assertIsNone((await compose(provider,self.facts,self.lock,self.valid))['text'])
    async def test_timeout_and_exception_release_lock_without_draft(self):
        for error in (asyncio.TimeoutError(),RuntimeError('fictional failure')):
            provider=Provider(self.good)
            with patch.object(provider,'reason_local',side_effect=error):
                out=await compose(provider,self.facts,self.lock,self.valid)
            self.assertIsNone(out['text']);self.assertFalse(self.lock.locked())
    async def test_busy_composer_does_not_call_model(self):
        provider=Provider(self.good);await self.lock.acquire()
        out=await compose(provider,self.facts,self.lock,self.valid)
        self.assertEqual(out['reason'],'busy');self.assertEqual(provider.calls,0);self.lock.release()
    async def test_single_correction_can_fix_missing_fact_then_review(self):
        good=self.good
        class Corrected(Provider):
            def reason_local(self,**kw):
                if self.calls==0:
                    self.calls+=1;return {'status':'success','message':json.dumps({'answer':good.replace('and sheet music','')})}
                return super().reason_local(**kw)
        provider=Corrected(good);out=await compose(provider,self.facts,self.lock,self.valid)
        self.assertEqual(out['text'],good);self.assertEqual(out['calls'],3);self.assertFalse(self.lock.locked())


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self,answer,verdict=None):
        from datetime import datetime
        from jarvis import household_activities as activities
        from jarvis.event_preparation import EventPreparation
        import test_event_preparation as preparation_fixtures
        from test_planning_preparation_bundle import profile,Client,ZONE,scope
        p=profile();client=Client()
        target='Remember Mia\'s activity "Club" in the family calendar '
        for tail in ('means "music orchestra practice"','usually needs "instrument, sheet music"'):
            activities.install(p._data,activities.proposal(target+tail,p._data))
        client.events['calendar.familiekalender']=[{'summary':'Club','start':'2026-10-24T14:15:00+02:00',
            'end':'2026-10-24T15:00:00+02:00','description':'','location':'Current Hall'}]
        class Combined(preparation_fixtures.Provider):
            policy=SimpleNamespace(enabled=True,maximum_input_characters=12000)
            composition_calls=0
            def reason_local(self,**kw):
                from jarvis.event_composition import DRAFT
                if kw['instructions'].startswith(DRAFT) or kw['instructions']==REVIEW:
                    self.composition_calls+=1
                    value=(verdict or {'grounded':True,'complete':True,'natural':True}) if kw['instructions']==REVIEW else {'answer':answer}
                    return {'status':'success','message':json.dumps(value)}
                return super().reason_local(**kw)
        provider=Combined();before=deepcopy(p._data)
        handler=EventPreparation(p,client,tuple(client.events),provider,now=lambda:datetime(2026,10,23,12,tzinfo=ZONE))
        with scope(p,'benny','s'):out=await handler.handle('What should Mia prepare for tomorrow?','s')
        self.assertEqual(before,p._data);self.assertEqual(out['status'],'success')
        self.assertFalse(handler.model_lock.locked())
        return out,provider
    async def test_accepted_prose_replaces_renderer_and_is_marked(self):
        text='Tomorrow, Mia has orchestra practice at 14:15 at Current Hall. Have the instrument and sheet music ready as usual.'
        out,provider=await self.run_case(text)
        self.assertEqual(out['message'],text);self.assertTrue(out['language_model_composition']);self.assertEqual(provider.composition_calls,2)
    async def test_bad_draft_returns_existing_verified_renderer(self):
        out,provider=await self.run_case('Bring goggles for swimming tomorrow.')
        self.assertFalse(out['language_model_composition']);self.assertEqual(provider.composition_calls,2)
        self.assertIn('orchestra practice',out['message']);self.assertIn('sheet music',out['message']);self.assertNotIn('goggles',out['message'])
    async def test_failed_review_never_returns_prose_as_verified(self):
        text='Tomorrow, Mia has orchestra practice at 14:15 at Current Hall. Have the instrument and sheet music ready as usual.'
        out,provider=await self.run_case(text,{'grounded':False,'complete':True,'natural':True})
        self.assertFalse(out['language_model_composition']);self.assertEqual(out['language_fallback_reason'],'review')
        self.assertEqual(provider.composition_calls,2);self.assertIn("For Mia's",out['message'])
