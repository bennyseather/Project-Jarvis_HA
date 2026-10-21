"""Fictional facts, speaker-scoped continuity and action-free interpretation."""
import asyncio
import ast
import copy
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from zoneinfo import ZoneInfo
from jarvis.household_profile import HouseholdProfile
from jarvis.household_reasoning import HouseholdReasoning
from jarvis.household_speaker import speaker_scope
from jarvis.sentence_stream import sentence_sink

ZONE=ZoneInfo('Europe/Oslo')


def profile():
    return HouseholdProfile({'schema_version':1,'revision':1,'roster_complete':True,'assistant':{'name':'Jarvis'},
        'members':[{'id':'alex','preferred_name':'Alex','birth_date':{'status':'confirmed','value':'2000-06-12'},
                    'employment':{'status':'confirmed','role':'Laboratory technician','employer':'Fixture Lab'}},
                   {'id':'sam','preferred_name':'Sam','birth_date':{'status':'confirmed','value':'2017-08-21'},
                    'schedule':{'status':'confirmed','school':{'name':'Fixture School'}},'room':'sam_room'}],
        'rooms':[{'id':'sam_room','name':'Sam Bedroom','floor':'main','users':['sam'],'purpose':'Sam sleeps here'},
                 {'id':'guest','name':'Guest Room','floor':'upper','purpose':'Guest sleepovers'}],
        'sharing_policy':{'directory_enabled':True,'source':'Synthetic approval','recorded_on':'2026-10-21',
            'relationships':['Sam is Alex\'s child.'],'knowledge_access':{'mode':'shared_household',
            'source':'Synthetic approval','recorded_on':'2026-10-21'}}})


def scope(p, member=None, key='s'):
    return speaker_scope({'member_id':member,'basis':'voice_match' if member else 'unknown','conversation_id':key},p,key)


class Provider:
    def __init__(self):
        self.calls=[]; self.tasks=[{'subject':'alex','topic':'employment'}]
        self.answer='Alex works as a Laboratory technician at Fixture Lab.'
        self.review={'grounded':True,'useful':True,'issue':'none'}
        self.mutate=None
    def reason_local(self, **kwargs):
        assert sentence_sink.get() is None
        self.calls.append(kwargs)
        if self.mutate: self.mutate()
        instructions=kwargs['instructions']
        value=({'tasks':self.tasks} if instructions.startswith('Classify ONLY') else
               self.review if instructions.startswith('Check the proposed') else {'answer':self.answer})
        return {'status':'success','message':json.dumps(value)}


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.p=profile(); self.clock=[0]; self.now=[datetime(2026,10,21,12,tzinfo=ZONE)]
        self.r=HouseholdReasoning(self.p,Provider(),clock=lambda:self.clock[0],now=lambda:self.now[0])
    def test_fast_fact_seeds_followup_without_model(self):
        self.r.resolve('How old is Sam?', 's')
        text,result=self.r.resolve('And her school?', 's')
        self.assertIsNone(result); self.assertIn("Sam's school",text); self.assertEqual(self.r.provider.calls,[])
    def test_school_calendar_to_age_and_back(self):
        self.r.resolve("What does Sam's day look like tomorrow?",'s')
        text,_=self.r.resolve('How old is she?','s'); self.assertEqual(text,'How old is Sam')
        text,_=self.r.resolve('What about her plans tomorrow?','s'); self.assertIn("Sam's plans",text)
    def test_no_name_guess_from_shared_user_or_previous_speaker(self):
        self.assertEqual(self.r.resolve('How old is she?', 's')[1]['status'],'clarification_required')
        with scope(self.p,'alex'): self.r.resolve('Who is Sam?','s')
        with scope(self.p,'sam'):
            self.assertEqual(self.r.resolve('What is her job?','s')[1]['status'],'clarification_required')
    def test_personal_grammar_is_not_corrupted(self):
        with scope(self.p,'alex'):
            self.assertEqual(self.r.resolve('How old am I?','s')[0],'How old am I')
            self.assertEqual(self.r.sessions['s']['subjects'],('alex',))
        with scope(self.p,None):
            self.assertEqual(self.r.resolve('What do I do for a living?','s')[1]['status'],'clarification_required')
    def test_singular_after_two_people_clarifies(self):
        self.r.resolve('Tell me about Alex and Sam','s')
        self.assertEqual(self.r.resolve('And her job?','s')[1]['status'],'clarification_required')
    def test_expiry_revision_day_and_session_boundaries(self):
        for mutate in (lambda:self.clock.__setitem__(0,301),lambda:self.p._data.__setitem__('revision',2),
                       lambda:self.now.__setitem__(0,datetime(2026,10,22,1,tzinfo=ZONE))):
            self.r.resolve('Who is Sam?','s'); mutate()
            self.assertEqual(self.r.resolve('How old is she?','s')[1]['status'],'clarification_required')
        self.r.resolve('Who is Sam?','s')
        self.assertEqual(self.r.resolve('How old is she?','other')[1]['status'],'clarification_required')
    def test_actions_web_secrets_and_unrelated_topics_clear_focus(self):
        for text in ('Turn off Sam bedroom lights','Save Sam has no school tomorrow','What is Alex password?',
                     'Search the web for Alex','What is the weather?','How do I cook pasta?'):
            self.r.resolve('Who is Sam?','s')
            self.assertEqual(self.r.resolve(text,'s')[0].rstrip('?'),text.rstrip('?'))
            self.assertNotIn('s',self.r.sessions)
    def test_permission_revoke_clears_context(self):
        self.r.resolve('Who is Sam?','s')
        self.p._data['sharing_policy']['knowledge_access']['mode']='disabled'
        self.r.resolve('How old is she?','s'); self.assertEqual(self.r.sessions,{})
    def test_bounded_session_count(self):
        for i in range(110): self.r.resolve('Who is Sam?',str(i))
        self.assertEqual(len(self.r.sessions),100); self.assertNotIn('0',self.r.sessions)


class ReasoningTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.p=profile(); self.provider=Provider()
        self.r=HouseholdReasoning(self.p,self.provider,now=lambda:datetime(2026,10,21,12,tzinfo=ZONE))
    async def ask(self,text):
        text,clarification=self.r.resolve(text,'s')
        return clarification or await self.r.handle(text,'s')
    async def test_employment_paraphrase_uses_computed_fact_reference(self):
        result=await self.ask('What does Alex do for a living?')
        self.assertTrue(result['interpreted']); self.assertEqual(len(self.provider.calls),3)
        self.assertIn('Fixture Lab',result['message']); self.assertFalse(result['cacheable']); self.assertTrue(result['read_only'])
    async def test_exact_facts_skip_model(self):
        for q in ("When is Alex's birthday?",'How old is Sam?',"What is Alex's job?"):
            self.assertIsNone(await self.ask(q))
        self.assertEqual(self.provider.calls,[])
    async def test_combined_fact_tasks_not_swallowed_by_fast_gate(self):
        self.provider.tasks=[{'subject':'alex','topic':'employment'},{'subject':'sam','topic':'age'}]
        self.provider.answer='Alex works as a Laboratory technician at Fixture Lab, and Sam is 9 years old.'
        self.assertTrue((await self.ask('What does Alex do and how old is Sam?'))['interpreted'])
        self.assertTrue(self.r.compound("What is Alex's job and birthday?"))
    async def test_no_confirmed_value_is_unknown_not_permission_denial(self):
        self.provider.tasks=[{'subject':'sam','topic':'employment'}]
        r=await self.ask('What does Sam do for a living?')
        self.assertEqual(r['status'],'unavailable'); self.assertIn('do not have confirmed',r['message'])
        self.assertEqual(len(self.provider.calls),1)
    async def test_malformed_model_tasks_never_get_tools_or_other_person(self):
        for tasks in ([{'subject':'sam','topic':'employment'}], [{'subject':'alex','topic':'unlock'}],
                      [{'subject':'alex','topic':'age','endpoint':'http://evil'}],[],[{}]):
            self.provider.tasks=tasks
            r=await self.ask('What does Alex do for a living?'); self.assertEqual(r['status'],'unavailable')
    async def test_wrong_age_or_action_claim_rejected_before_review(self):
        self.provider.tasks=[{'subject':'sam','topic':'age'}]
        for answer in ('Sam is 99 years old.','I have unlocked the door for Sam.'):
            self.provider.answer=answer
            self.assertEqual((await self.ask('Tell me roughly how old Sam is'))['status'],'unavailable')
    async def test_reviewer_rejects_unsupported_fact_even_if_number_check_passes(self):
        self.provider.answer='Alex is an astronaut.'
        self.provider.review={'grounded':False,'useful':True,'issue':'unsupported_fact'}
        self.assertEqual((await self.ask('What does Alex do for a living?'))['status'],'unavailable')
    async def test_context_change_during_inference_suppresses_old_result(self):
        self.provider.mutate=lambda:self.p._data.__setitem__('revision',self.p._data['revision']+1)
        self.assertEqual((await self.ask('What does Alex do for a living?'))['status'],'unavailable')
    async def test_no_external_fallback_on_failure(self):
        self.r.provider=SimpleNamespace(reason_local=lambda **kw:{'status':'unavailable'},
                                       reason=lambda **kw:self.fail('External reasoning invoked'))
        self.assertEqual((await self.ask('What does Alex do for a living?'))['status'],'unavailable')
    async def test_calendar_paraphrase_only_delegates_code_owned_read_query(self):
        self.provider.tasks=[{'subject':'sam','topic':'calendar'}]
        calls=[]
        async def calendar(text,key): calls.append((text,key)); return {'status':'success','message':'Read-only plans','read_only':True}
        text,_=self.r.resolve("What has Sam got on the agenda tomorrow?",'s')
        result=await self.r.handle(text,'s',calendar=SimpleNamespace(handle=calendar))
        self.assertEqual(result['message'],'Read-only plans')
        self.assertEqual(calls,[("What does Sam's day look like tomorrow?",'s')])
    async def test_unsupported_calendar_dates_never_silently_dropped(self):
        self.provider.tasks=[{'subject':'sam','topic':'calendar'}]
        async def forbidden(*args): self.fail('Bad date reached calendar')
        text,_=self.r.resolve('What has Sam got on the agenda next month?','s')
        result=await self.r.handle(text,'s',calendar=SimpleNamespace(handle=forbidden))
        self.assertEqual(result['status'],'clarification_required')

    async def test_profile_fact_and_live_calendar_combine_without_resynthesising_events(self):
        self.provider.tasks=[{'subject':'sam','topic':'age'},{'subject':'sam','topic':'calendar'}]
        self.provider.answer='Sam is 9 years old.'
        async def calendar(text,key):
            self.assertEqual(text,"What does Sam's day look like tomorrow?")
            return {'status':'success','message':'Sam has music tomorrow.','read_only':True,'interpreted':True}
        text,_=self.r.resolve('How old is Sam and what does tomorrow look like?','s')
        result=await self.r.handle(text,'s',calendar=SimpleNamespace(handle=calendar))
        self.assertEqual(result['message'],'Sam is 9 years old. Sam has music tomorrow.')
        self.assertEqual(result['composition'],'verified_profile_and_calendar')

    async def test_live_source_failure_is_not_hidden_by_known_profile_fact(self):
        self.provider.tasks=[{'subject':'sam','topic':'age'},{'subject':'sam','topic':'calendar'}]
        self.provider.answer='Sam is 9 years old.'
        async def calendar(*args): return {'status':'unavailable','message':'Live plans could not be checked.','read_only':True}
        text,_=self.r.resolve('How old is Sam and what does tomorrow look like?','s')
        result=await self.r.handle(text,'s',calendar=SimpleNamespace(handle=calendar))
        self.assertEqual(result['status'],'unavailable');self.assertIn('could not be checked',result['message'])

    async def test_profile_pass_cannot_invent_calendar_conclusion_before_calendar_read(self):
        self.provider.tasks=[{'subject':'sam','topic':'age'},{'subject':'sam','topic':'calendar'}]
        self.provider.answer='Sam is 9 years old. Tomorrow looks like a regular day with no specific changes.'
        async def calendar(*args): self.fail('Hallucinated profile draft reached calendar append')
        text,_=self.r.resolve('How old is Sam and what does tomorrow look like?','s')
        result=await self.r.handle(text,'s',calendar=SimpleNamespace(handle=calendar))
        self.assertEqual(result['status'],'unavailable')

    async def test_household_scoped_rooms_are_not_reported_missing(self):
        self.provider.tasks=[{'subject':'household','topic':'rooms'}]
        self.provider.answer='The Guest Room is on the upper floor.'
        self.assertEqual((await self.ask('Where could a guest stay?'))['status'],'success')

    async def test_confirmed_quiet_preference_is_not_calendar_load_inference(self):
        self.p._data['conversational_updates']={'mode':'shared_confirmation'}
        self.p._data['conversation_notes']=[{'id':'abcd1234','text':'Alex prefers quiet mornings'}]
        self.provider.tasks=[{'subject':'alex','topic':'notes'}]
        self.provider.answer='Alex prefers quiet mornings.'
        self.assertEqual((await self.ask('Does Alex like quiet mornings?'))['status'],'success')

    async def test_work_departure_does_not_establish_approximate_start_time(self):
        self.p._data['members'][0]['work_routine']={'status':'confirmed','work_days':['monday'],
            'usual_departure_for_work':'08:00','usual_work_finish':'16:00'}
        self.provider.tasks=[{'subject':'alex','topic':'work_routine'}]
        self.provider.answer='Alex departs at 08:00. The exact start and end times are approximate.'
        self.assertEqual((await self.ask("Explain Alex's usual work timetable"))['status'],'unavailable')

    async def test_unknown_work_start_is_allowed_as_explicit_gap(self):
        self.p._data['members'][0]['work_routine']={'status':'confirmed','work_days':['monday'],
            'usual_departure_for_work':'08:00','usual_work_finish':'16:00'}
        self.provider.tasks=[{'subject':'alex','topic':'work_routine'}]
        self.provider.answer='Alex usually leaves for work at 08:00 and finishes at 16:00. The exact start time is not provided.'
        self.assertEqual((await self.ask("Explain Alex's usual work timetable"))['status'],'success')
    async def test_household_named_data_does_not_write_profile(self):
        before=copy.deepcopy(self.p._data)
        await self.ask('What does Alex do for a living?')
        self.assertEqual(self.p._data,before)

    async def test_missing_requested_fact_must_not_be_silently_omitted(self):
        self.provider.tasks=[{'subject':'sam','topic':'age'},{'subject':'sam','topic':'employment'}]
        self.provider.answer='Sam is 9 years old.'
        self.assertEqual((await self.ask('How old is Sam and what does Sam do for a living?'))['status'],'unavailable')

    async def test_unknown_speaker_is_not_addressed_as_owner(self):
        self.provider.tasks=[{'subject':'sam','topic':'age'}]
        self.provider.answer='You are 9 years old.'
        self.assertEqual((await self.ask('Tell me roughly how old Sam is'))['status'],'unavailable')

    async def test_current_location_never_inferred_from_room(self):
        result=await self.ask('Where is Sam now?')
        self.assertEqual(result['status'],'unavailable'); self.assertEqual(self.provider.calls,[])

    async def test_transport_exception_returns_bounded_failure(self):
        def fail(**kwargs): raise RuntimeError('Synthetic transport failure')
        self.provider.reason_local=fail
        self.assertEqual((await self.ask('What does Alex do for a living?'))['status'],'unavailable')

    async def test_whole_evidence_budget_is_checked_before_transport(self):
        self.provider.policy=SimpleNamespace(maximum_input_characters=50)
        self.assertEqual((await self.ask('What does Alex do for a living?'))['status'],'unavailable')
        self.assertEqual(self.provider.calls,[])


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.p=profile(); self.r=HouseholdReasoning(self.p,None,now=lambda:datetime(2026,10,21,12,tzinfo=ZONE))
    def facts(self,subject,topic,text=''):
        return self.r.evidence([{'subject':subject,'topic':topic}],text)['facts']
    def test_current_age_and_next_birthday_calculated_from_reference_date(self):
        self.assertIn('9 years',self.facts('sam','age')[0]['text'])
        fact=self.facts('sam','next_birthday')[0]['text']
        self.assertIn('2027',fact); self.assertIn('age on that date: 10',fact)
        self.assertIn('Celebration plans are unknown',fact)
    def test_unconfirmed_birth_and_employment_not_projected(self):
        for field,topic in (('birth_date','age'),('employment','employment')):
            self.p._data['members'][0][field]['status']='withdrawn'
            self.assertEqual(self.facts('alex',topic),[])
    def test_room_and_relationship_include_all_named_owners_without_presence(self):
        fact=self.facts('sam','relationships')[0]
        self.assertEqual(set(fact['owners']),{'sam','alex'})
        self.assertIn('not current presence',self.facts('sam','rooms')[0]['text'])
    def test_school_does_not_establish_attendance(self):
        self.assertIn('does not confirm current attendance',self.facts('sam','school')[0]['text'])
    def test_future_birth_leap_date_and_unknown_fields(self):
        self.p._data['members'][0]['birth_date']['value']='2030-01-01'
        self.assertEqual(self.facts('alex','age'),[])
        self.p._data['members'][0]['birth_date']['value']='2000-02-29'
        self.assertIn('policy is not recorded',self.facts('alex','next_birthday')[0]['text'])
        self.assertEqual(self.facts('sam','unknown'),[])

    def test_work_override_projects_day_specific_finish_not_stale_base(self):
        self.p._data['members'][0]['work_routine']={'status':'confirmed','work_days':['thursday','friday'],'usual_work_finish':'16:00'}
        self.p._data['sharing_policy']['additional_category_approval']={'source':'Synthetic','recorded_on':'2026-10-21','categories':['work_schedules']}
        self.p._data['routine_overrides']=[{'person':'alex','kind':'work_finish','on':'friday','value':'15:00'}]
        text=self.facts('alex','work_routine')[0]['text']
        self.assertIn('"friday": "15:00"',text);self.assertIn('"thursday": "16:00"',text)
        self.assertNotIn('"usual_work_finish"',text)

    def test_bedtime_for_one_person_does_not_include_another_persons_time(self):
        self.p._data['household_routines']={'bedtimes':{'sam':'21:00','alex':'23:00'},'weekdays':['monday'],'usual_wake_time':'07:00'}
        text=self.facts('sam','household_routine')[0]['text']
        self.assertIn('21:00',text);self.assertNotIn('23:00',text)


class ApplicationTests(unittest.IsolatedAsyncioTestCase):
    def app(self):
        root=Path(__file__).resolve().parents[1]
        source=root/'src/jarvis/core/application.py'
        if not source.exists(): source=root/'jarvis/app/src/jarvis/core/application.py'
        method=next(n for n in ast.walk(ast.parse(source.read_text(encoding='utf-8')))
                    if isinstance(n,ast.AsyncFunctionDef) and n.name=='handle_request')
        namespace={'asyncio':asyncio}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'<real public gate>','exec'),namespace)
        p=profile(); provider=Provider()
        app=SimpleNamespace(container=SimpleNamespace(household_profile=p,local_reasoning_provider=provider))
        return namespace['handle_request'],app,p,provider

    async def test_fast_age_then_job_followup_uses_same_person(self):
        handle,app,p,provider=self.app()
        first=await handle(app,'How old is Alex?','s')
        self.assertEqual(first['provider'],'household_profile');self.assertEqual(provider.calls,[])
        result=await handle(app,'And his job?','s')
        self.assertIn('Fixture Lab',result['message']);self.assertEqual(result['provider'],'household_reasoning')

    async def test_compound_not_swallowed_by_broad_employment_gate(self):
        handle,app,p,provider=self.app()
        provider.tasks=[{'subject':'alex','topic':'employment'},{'subject':'alex','topic':'birthday'}]
        provider.answer="Alex works as a Laboratory technician at Fixture Lab, and Alex's birthday is 12 June."
        observed=[]
        p._edits=SimpleNamespace(observe_turn=lambda *args:observed.append(args))
        result=await handle(app,"What is Alex's job and birthday?",'s')
        self.assertIn('12 June',result['message']);self.assertIn('Fixture Lab',result['message'])
        self.assertEqual(observed,[('combined household question','s')])

    async def test_clarification_clears_older_household_confirmation(self):
        handle,app,p,provider=self.app()
        observed=[];p._edits=SimpleNamespace(observe_turn=lambda *args:observed.append(args))
        result=await handle(app,'What do I do for a living?','s')
        self.assertEqual(result['status'],'clarification_required')
        self.assertEqual(observed,[('household question clarification','s')])

    async def test_verified_first_person_exact_age_keeps_fast_path(self):
        handle,app,p,provider=self.app()
        with scope(p,'alex'):
            result=await handle(app,'How old am I?','s')
        self.assertTrue(result['message'].startswith('You are '));self.assertEqual(provider.calls,[])

    async def test_next_birthday_precedes_full_legacy_calendar_route(self):
        from jarvis.household_calendar import HouseholdCalendar
        for question in ('How old will Mia be on her next birthday?',
                         "When is Mia's upcoming birthday?"):
            handle,app,p,provider=self.app()
            p._data['members'][1]['preferred_name']='Mia'
            class NoCalendarReads:
                async def call_service_response(self,*args,**kwargs):
                    raise AssertionError('Profile birthday query reached calendar')
            app.container.household_calendar=HouseholdCalendar(p,NoCalendarReads(),())
            provider.tasks=[{'subject':'sam','topic':'next_birthday'}]
            provider.answer='Mia will be 10 on 21 August 2027.'
            result=await handle(app,question,'s')
            self.assertEqual(result['status'],'success')
            self.assertEqual(result['provider'],'household_reasoning')
            self.assertIn('10',result['message']);self.assertIn('2027',result['message'])

    def test_next_birthday_gate_is_not_next_school_or_action_classifier(self):
        self.assertFalse(HouseholdReasoning.next_birthday('When is the next school day?'))
        self.assertFalse(HouseholdReasoning.next_birthday('What is planned on Friday?'))


if __name__=='__main__': unittest.main()
