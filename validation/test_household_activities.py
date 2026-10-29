"""Fictional activity records only. No real profile, calendar writes or audio."""
import asyncio
import ast
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jarvis.household_profile import HouseholdProfile
from jarvis import household_activities as activities
from jarvis.event_preparation import EventPreparation
from test_planning_preparation_bundle import profile,scope,Client,ZONE
from test_event_preparation import Provider


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'profile.json';self.path.write_text(json.dumps(profile()._data))
        self.p=HouseholdProfile.load(self.path)
        self.target='Mia\'s activity "Training" in the family calendar'
    def ask(self,value,key='s'):return self.p.edit_request(value,key)
    def save(self,tail='means "gymnastics"'):
        out=self.ask('Remember '+self.target+' '+tail)
        self.assertEqual(out['status'],'clarification_required',out)
        out=self.ask('confirm household change');self.assertEqual(out['status'],'success',out)
        return self.p._data['activity_profiles'][0]

    def test_review_then_confirm_reload_projection_and_undo(self):
        before=self.path.read_bytes();self.ask('Remember '+self.target+' means "gymnastics"')
        self.assertEqual(before,self.path.read_bytes());self.assertFalse(self.p.context()['confirmed_activity_profiles'])
        self.ask('confirm household change');reloaded=HouseholdProfile.load(self.path)
        self.assertEqual(reloaded.context()['confirmed_activity_profiles'][0]['activity'],'gymnastics')
        self.assertNotIn('conversation_notes',self.p._data)
        self.ask('undo last household change');self.ask('confirm household change')
        self.assertFalse(self.p._data.get('activity_profiles'))

    def test_calendar_meaning_keeps_exact_scope_and_current_overrides(self):
        self.save()
        label=activities.calendar_meaning(self.p._data,'Training',['mia'],'family')
        self.assertEqual(label['activity'],'gymnastics')
        for title,owners,source in (('Training',['emrik'],'family'),('Training',['mia'],'work'),('Other training',['mia'],'family'),('Training',['mia','benny'],'family')):
            self.assertIsNone(activities.calendar_meaning(self.p._data,title,owners,source))
        for notes in ('This is swimming training.','Gymnastics is cancelled.'):
            self.assertIsNone(activities.calendar_meaning(self.p._data,'Training',['mia'],'family',notes))

    def test_unmapped_training_does_not_get_a_guessed_sport(self):
        self.assertIsNone(activities.calendar_meaning(self.p._data,'Training',['mia'],'family'))
        from jarvis.calendar_insights import appointment_label
        self.assertIn('sport not specified',appointment_label({'text':'Trening','owners':['mia'],'source':'family'}))

    def test_usual_details_append_replace_duplicates_and_kind_change_reset(self):
        self.save();self.save('usually needs "water bottle, training clothes"')
        self.save('also needs "water bottle, small towel"')
        self.assertEqual(len(self.p._data['activity_profiles'][0]['equipment']),3)
        self.save('usually takes place at "Fictional Hall"');self.save('usually lasts 60 minutes')
        self.save('usual preparation is "Check the bag the evening before"')
        row=self.save('means "swimming"')
        self.assertEqual(row['activity'],'swimming');self.assertEqual(row['equipment'],[])
        self.assertIsNone(row['usual_venue']);self.assertIsNone(row['preparation']);self.assertIsNone(row['duration_minutes'])

    def test_duplicate_does_not_write_or_leave_confirmation(self):
        self.save();before=self.path.read_bytes()
        self.assertIn('already saved',self.ask('Remember '+self.target+' means "gymnastics"')['message'])
        self.assertEqual(before,self.path.read_bytes());self.assertIn('no pending',self.ask('confirm household change')['message'])

    def test_remove_requires_review_and_undo_restores(self):
        self.save();before=self.path.read_bytes()
        self.ask('Forget '+self.target);self.assertEqual(before,self.path.read_bytes())
        self.ask('confirm household change');self.assertFalse(self.p._data['activity_profiles'])
        self.ask('undo last household change');self.ask('confirm household change')
        self.assertEqual(len(self.p._data['activity_profiles']),1)

    def test_cancellation_expiry_and_wrong_conversation(self):
        before=self.path.read_bytes();self.ask('Remember '+self.target+' means "gymnastics"')
        self.assertIn('no pending',self.ask('confirm household change','other')['message'])
        self.ask('cancel household change');self.assertIn('no pending',self.ask('confirm household change')['message'])
        self.ask('Remember '+self.target+' means "gymnastics"');self.p._edits.clock=lambda:10**20
        self.assertIn('no pending',self.ask('confirm household change')['message']);self.assertEqual(before,self.path.read_bytes())

    def test_stale_revision_and_failed_disk_do_not_claim_saved(self):
        self.ask('Remember '+self.target+' means "gymnastics"','one')
        self.ask('Remember '+self.target+' means "swimming"','two');self.ask('confirm household change','two')
        self.assertIn('changed since',self.ask('confirm household change','one')['message'])
        before=self.path.read_bytes();self.ask('Remember '+self.target+' usually needs "water bottle"')
        with patch.object(self.p._edits,'_atomic',side_effect=OSError('fixture disk full')):
            self.assertEqual(self.ask('confirm household change')['status'],'unavailable')
        self.assertEqual(before,self.path.read_bytes())

    def test_first_person_needs_actual_speaker_and_shared_confirmation_is_not_auth(self):
        self.assertIn('Whose',self.ask('Remember my activity "Club" in the family calendar means "robotics"')['message'])
        with scope(self.p,'benny'):
            self.ask('Remember my activity "Club" in the work calendar means "robotics"')
        with scope(self.p,'linda'):
            self.assertEqual(self.ask('yes')['status'],'clarification_required')
            self.assertEqual(self.ask('confirm household change')['status'],'success')
        self.assertEqual(self.p._data['activity_profiles'][0]['person'],'benny')

    def test_policy_optout_and_invalid_inputs_never_save(self):
        for command in ('Remember '+self.target+' usually needs "water"',
                'Remember Unknown\'s activity "Club" in the family calendar means "robotics"',
                'Remember '+self.target+' means "https://invalid.example"',
                'Remember '+self.target+' means "api key hidden"'):
            before=self.path.read_bytes();self.assertEqual(self.ask(command)['status'],'clarification_required')
            self.assertEqual(before,self.path.read_bytes())
        self.p._data['sharing_policy']['knowledge_access']['mode']='disabled'
        self.assertEqual(self.ask('Remember '+self.target+' means "gymnastics"')['status'],'clarification_required')
        self.assertEqual(activities.view('Show activity profiles',self.p)['status'],'unavailable')
        self.assertNotIn('confirmed_activity_profiles',self.p.context())

    def test_views_and_case_insensitive_owner_and_emoji_identity(self):
        self.ask('Remember MIA\'S activity "Training 💪" in the family calendar means "gymnastics"');self.ask('confirm household change')
        self.assertEqual(len(self.p._data['activity_profiles']),1)
        self.assertIn('gymnastics',activities.view('Show Mia\'s activity profiles',self.p)['message'])
        self.assertIn('gymnastics',activities.view('Show all activity profiles',self.p)['message'])
        self.assertIn('known household',activities.view('Show Someone\'s activity profiles',self.p)['message'])

    def test_schema_rejects_unknown_fields_duplicates_and_bad_duration(self):
        row=self.save()
        for mutation in ('field','duplicate','owner','duration'):
            data=deepcopy(self.p._data)
            if mutation=='field':data['activity_profiles'][0]['permissions']='all'
            elif mutation=='duplicate':data['activity_profiles'].append(deepcopy(row))
            elif mutation=='owner':data['activity_profiles'][0]['person']='unknown'
            else:data['activity_profiles'][0]['duration_minutes']=True
            with self.assertRaises(ValueError):HouseholdProfile(data)

    def test_disabling_sharing_after_proposal_blocks_confirmation(self):
        before=self.path.read_bytes();self.ask('Remember '+self.target+' means "gymnastics"')
        self.p._data['sharing_policy']['knowledge_access']['mode']='disabled'
        self.assertEqual(self.ask('confirm household change')['status'],'unavailable')
        self.assertEqual(before,self.path.read_bytes());self.assertNotIn('activity_profiles',self.p._data)

    def test_existing_note_save_replace_delete_and_undo_remain_separate(self):
        self.ask('Remember Mia likes painting');self.ask('confirm household change')
        identifier=self.p._data['conversation_notes'][0]['id']
        self.ask('Replace household note '+identifier+': Mia likes drawing');self.ask('confirm household change')
        self.assertEqual(self.p._data['conversation_notes'][0]['text'],'Mia likes drawing')
        self.ask('Forget Mia likes drawing');self.ask('confirm household change')
        self.assertFalse(self.p._data['conversation_notes'])
        self.ask('undo last household change');self.ask('confirm household change')
        self.assertEqual(self.p._data['conversation_notes'][0]['text'],'Mia likes drawing')
        self.assertNotIn('activity_profiles',self.p._data)


class EventTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'profile.json';self.path.write_text(json.dumps(profile()._data))
        self.p=HouseholdProfile.load(self.path);self.client=Client();self.provider=Provider()
        self.target='Mia\'s activity "Training" in the family calendar'
        for tail in ('means "gymnastics"','usually needs "water bottle, training clothes"',
                     'usually takes place at "Usual Fictional Hall"','usually lasts 60 minutes'):
            self.p.edit_request('Remember '+self.target+' '+tail,'setup');self.p.edit_request('confirm household change','setup')
        self.event={'summary':'Training 💪','start':'2026-10-24T17:00:00+02:00','end':'2026-10-24T18:30:00+02:00',
                    'location':'Current Fictional Hall','description':''}
        self.client.events['calendar.familiekalender']=[deepcopy(self.event)]
        self.h=EventPreparation(self.p,self.client,tuple(self.client.events),self.provider,now=lambda:datetime(2026,10,23,12,tzinfo=ZONE))
    async def ask(self,text='What should Mia bring for gymnastics tomorrow?',key='s'):
        with scope(self.p,None,key):return await self.h.handle(text,key)

    async def test_confirmed_mapping_and_usual_equipment_are_attributed(self):
        before=self.path.read_bytes();out=await self.ask()
        self.assertEqual(out['status'],'success',out);self.assertIn('water bottle',out['message'])
        self.assertIn('usual',out['message']);self.assertIn('gymnastics',out['message'])
        self.assertNotIn('recorded as',out['message']);self.assertNotIn('usual equipment for',out['message'])
        self.assertEqual(before,self.path.read_bytes());self.assertNotIn('60 minutes',out['message'])

    async def test_exact_owner_source_title_not_prefix_or_another_person(self):
        for change in ('title','owner','source'):
            event=deepcopy(self.event)
            if change=='title':event['summary']='Training 2'
            elif change=='owner':event['owners']=['emrik']
            else:event['source']='work'
            if change=='title':self.client.events['calendar.familiekalender']=[event];self.assertEqual((await self.ask())['status'],'clarification_required')
            else:
                event.update(text='Training',owners=event.get('owners',['mia']),source=event.get('source','family'),description_units=[])
                self.assertIsNone(activities.match(self.p._data,event))

    async def test_current_other_activity_overrides_usual_mapping(self):
        self.client.events['calendar.familiekalender'][0]['description']='This is swimming training. Bring a towel.'
        out=await self.ask('What should Mia bring for swimming tomorrow?')
        self.assertEqual(out['status'],'success');self.assertNotIn('training clothes',out['message'])
        self.assertEqual((await self.ask())['status'],'clarification_required')

    async def test_current_requirements_and_venue_override_usual_values(self):
        self.client.events['calendar.familiekalender'][0]['description']='Do not bring a water bottle.'
        out=await self.ask();self.assertIn('Do not bring a water bottle.',out['message'])
        self.assertNotIn('training clothes',out['message'])
        out=await self.ask('Where is Mia\'s gymnastics tomorrow?')
        self.assertIn('Current Fictional Hall',out['message']);self.assertNotIn('Usual Fictional Hall',out['message'])

    async def test_usual_venue_is_not_current_confirmation(self):
        self.client.events['calendar.familiekalender'][0]['location']=''
        out=await self.ask('Where is Mia\'s gymnastics tomorrow?')
        self.assertEqual(out['status'],'success',out);self.assertIn('Usual Fictional Hall',out['message'])
        self.assertIn('not confirmed',out['message']);self.assertIn('still the venue',out['message'])

    def ask_for_missing_venue(self):
        def response(context):
            return {'status':'success','message':json.dumps({'events':{e['id']:{'use':True,'units':[]} for e in context['events']},'notes':{n['id']:True for n in context['approved_notes']},'suggestion':'none','question':'venue'})}
        self.provider.respond=response

    async def test_preparation_uses_qualified_usual_venue_without_missing_venue_question(self):
        self.client.events['calendar.familiekalender'][0]['location']='';self.ask_for_missing_venue()
        out=await self.ask('What should Mia prepare for gymnastics tomorrow?')
        self.assertEqual(out['status'],'success',out);self.assertIn('Usual Fictional Hall',out['message']);self.assertIn('usual',out['message'])
        self.assertIn('check it for this appointment',out['message']);self.assertNotIn('I do not have a usable venue',out['message']);self.assertNotIn('Where will it take place',out['message'])

    async def test_preparation_still_asks_when_no_current_or_usual_venue(self):
        self.client.events['calendar.familiekalender'][0]['location']='';self.p._data['activity_profiles'][0]['usual_venue']=None;self.ask_for_missing_venue()
        out=await self.ask('What should Mia prepare for gymnastics tomorrow?')
        self.assertIn('Where will it take place',out['message']);self.assertNotIn('Usual Fictional Hall',out['message'])

    async def test_no_event_no_synthetic_appointment_from_profile(self):
        self.client.events['calendar.familiekalender']=[];out=await self.ask()
        self.assertEqual(out['status'],'clarification_required');self.assertNotIn('water bottle',out['message'])
        self.assertFalse(self.provider.calls)

    async def test_negative_current_type_and_cancel_notice_block_mapping(self):
        for clause in ('Not gymnastics today.','Cancelled.'):
            self.client.events['calendar.familiekalender'][0]['description']=clause
            out=await self.ask();self.assertEqual(out['status'],'clarification_required',clause)

    async def test_usual_duration_never_replaces_all_day_or_event_times(self):
        event=self.client.events['calendar.familiekalender'][0];event.update(start='2026-10-24',end='2026-10-25',location='')
        out=await self.ask();self.assertIn('all day',out['message'])
        self.assertIn('not a confirmed duration',out['message']);self.assertNotIn('18:00',out['message'])

    async def test_current_unknown_definition_and_discarded_clause_block_usual_mapping(self):
        for clause in ('This is robotics club.', 'Not gymnastics today. See https://invalid.example for details.', 'x'*950):
            self.client.events['calendar.familiekalender'][0]['description']=clause
            out=await self.ask();self.assertEqual(out['status'],'clarification_required',clause[:80])
            self.assertNotIn('water bottle',out['message'])

    async def test_venue_routing_does_not_treat_whereabouts_as_an_activity(self):
        self.assertIsNone(self.h.request('Where is Mia tomorrow?','x'))
        self.assertIsNone(self.h.request('Where is Mia right now?','x'))
        self.assertIsNone(self.h.request('Where is Mia travelling tomorrow?','x'))


class ApplicationTests(unittest.IsolatedAsyncioTestCase):
    setUp=EventTests.setUp
    def application(self):
        source=Path(__file__).resolve().parents[1]/'src/jarvis/core/application.py'
        if not source.exists():source=Path(__file__).resolve().parents[1]/'jarvis/app/src/jarvis/core/application.py'
        method=next(n for n in ast.walk(ast.parse(source.read_text(encoding='utf-8')))
                    if isinstance(n,ast.AsyncFunctionDef) and n.name=='handle_request')
        namespace={'asyncio':asyncio}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'<activity application>','exec'),namespace)
        app=SimpleNamespace(container=SimpleNamespace(household_profile=self.p,home_assistant=self.client,
            proactive_allowed_entities=tuple(self.client.events),local_reasoning_provider=self.provider,event_preparation=self.h))
        async def request(text):
            with scope(self.p,None,'application'):return await namespace['handle_request'](app,text,'application')
        return request

    async def test_actual_application_review_confirm_read_and_infer(self):
        self.p._data.pop('activity_profiles');self.path.write_text(json.dumps(self.p._data))
        ask=self.application();before=self.path.read_bytes()
        out=await ask('Remember '+self.target+' means "gymnastics"')
        self.assertEqual(out['status'],'clarification_required',out);self.assertEqual(self.path.read_bytes(),before)
        out=await ask('confirm household change');self.assertEqual(out['status'],'success',out)
        out=await ask('Remember '+self.target+' usually needs "water bottle"')
        self.assertEqual(out['status'],'clarification_required',out)
        out=await ask('yes');self.assertEqual(out['status'],'success',out)
        before=self.path.read_bytes();calls=len(self.provider.calls)
        out=await ask('Show Mia\'s activity profiles');self.assertIn('water bottle',out['message'])
        self.assertEqual(calls,len(self.provider.calls));self.assertEqual(before,self.path.read_bytes())
        out=await ask('What should Mia bring for gymnastics tomorrow?')
        self.assertEqual(out['status'],'success',out);self.assertIn('water bottle',out['message'])
        self.assertGreater(len(self.provider.calls),calls)

    async def test_read_question_clears_pending_and_disabled_read_calls_no_model(self):
        ask=self.application();before=self.path.read_bytes()
        await ask('Remember '+self.target+' also needs "small towel"')
        await ask('Show activity profiles')
        self.assertIn('no pending',self.p.edit_request('confirm household change','application')['message'])
        self.assertEqual(before,self.path.read_bytes());calls=len(self.provider.calls)
        self.p._data['sharing_policy']['knowledge_access']['mode']='disabled'
        out=await ask('Show activity profiles');self.assertEqual(out['status'],'unavailable')
        self.assertEqual(calls,len(self.provider.calls))
