"""Fictional cross-domain sources, isolation, bounded inference and read-only contracts."""
import asyncio
import copy
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from jarvis.connected_understanding import ConnectedUnderstanding
from jarvis.household_speaker import speaker_scope
from jarvis.sentence_stream import sentence_sink
from test_household_reasoning import profile

ZONE=ZoneInfo('Europe/Oslo')
NOW=datetime(2026,10,22,12,tzinfo=ZONE)
STATES=[{'entity_id':'binary_sensor.kitchen','state':'on','attributes':{'device_class':'window','friendly_name':'Kitchen window'}},
        {'entity_id':'light.office','state':'on','attributes':{'friendly_name':'Office light'}},
        {'entity_id':'binary_sensor.secret','state':'on','attributes':{'device_class':'door','friendly_name':'Excluded private door'}},
        {'entity_id':'camera.doorbell','state':'idle','attributes':{'friendly_name':'Doorbell'}}]


class Provider:
    def __init__(self):
        self.calls=[]
        self.answer='The kitchen window is reported open now, so consider checking it again.'
        self.review={'grounded':True,'useful':True,'issue':'none'}
        self.mutate=None
    def reason_local(self,**kw):
        assert sentence_sink.get() is None
        self.calls.append(kw)
        if self.mutate: self.mutate()
        answer=self.answer
        context=json.loads(kw['input_messages'][0]['content'])
        if answer=='The kitchen window is reported open now, so consider checking it again.' and any(
                f['kind']=='home_weather' and 'rain.' in f['text'] for f in context['evidence']['facts']):
            answer='HA currently reports the kitchen window open, so with rain forecast locally, consider rechecking it.'
        if self.answer=='The kitchen window is reported open now, so consider checking it again.' and any(
                f['kind']=='travel_summary' for f in context['evidence']['facts']):
            answer='The selected trip is a flight to Fixture City on Friday at 12:00. HA currently reports the kitchen window open.'
        return {'status':'success','message':json.dumps(self.review if kw['instructions'].startswith('Check ONLY') else {'answer':answer})}


class Client:
    def __init__(self): self.calls=[]; self.states=copy.deepcopy(STATES)
    async def get_states_isolated(self): self.calls.append('states'); return self.states
    async def call_service(self,*args): raise AssertionError('Device action attempted')
    async def dispatch_event(self,*args): raise AssertionError('Event/notification attempted')


class ConnectedTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.p=profile(); self.provider=Provider(); self.client=Client(); self.clock=[0]; self.now=[NOW]
        self.public_calls=[]; self.weather_calls=[]; self.travel_calls=[]
        async def weather(a,b):
            self.weather_calls.append((a,b)); return 'Home-area forecast, not destination weather: Thursday 22 October: rain.'
        async def public(text,**kw):
            assert sentence_sink.get() is None
            self.public_calls.append(text)
            return {'status':'success','message':'The latest Fixture release is 2026.10.',
                    'sources':[{'title':'Fixture releases','url':'https://example.com/releases'}]}
        async def travel(text,**kw):
            self.travel_calls.append(text); return {'status':'success','message':'Your next travel entry is a flight to Fixture City on Friday 23 October at 12:00.'}
        self.r=ConnectedUnderstanding(self.p,self.provider,self.client,None,{'binary_sensor.kitchen','light.office'},
            weather=weather,public=SimpleNamespace(handle=public),travel=SimpleNamespace(handle=travel),
            now=lambda:self.now[0],clock=lambda:self.clock[0])
    async def ask(self,q,key='s',speaker=None):
        with speaker_scope({'member_id':speaker,'basis':'voice_match' if speaker else 'unknown','conversation_id':key},self.p,key):
            return await self.r.handle(q,key)
    async def test_pure_facts_controls_and_single_source_stay_fast(self):
        for q in ('How old is Sam?','When is Alex birthday?','Turn off the office light',
                  'What is the weather tomorrow?','Are any windows open?','Remember Sam likes rain',
                  'What are the plans tomorrow?'):
            self.assertIsNone(await self.ask(q))
        self.assertEqual(self.provider.calls,[]);self.assertEqual(self.client.calls,[])
    async def test_home_weather_connects_without_actions_or_excluded_entities(self):
        out=await self.ask('How does the weather affect things at home today?')
        self.assertEqual(out['status'],'success');self.assertTrue(out['read_only'])
        self.assertEqual(len(self.provider.calls),2); self.assertEqual(self.client.calls,['states'])
        evidence=self.provider.calls[0]['input_messages'][0]['content']
        self.assertNotIn('Excluded private door',evidence);self.assertNotIn('Doorbell',evidence)
        self.assertNotIn('camera.doorbell',evidence)
        board=json.loads(evidence)['reasoning_board']
        self.assertNotIn('key_appointments',board);self.assertNotIn('recorded_overlaps',board)
        self.assertEqual(self.public_calls,[])
    async def test_predeparture_unknown_first_person_clarifies_before_reads(self):
        out=await self.ask('Is there anything I should sort out before leaving tomorrow?')
        self.assertEqual(out['status'],'clarification_required');self.assertIn('Whose',out['message'])
        self.assertEqual(self.client.calls,[]);self.assertEqual(self.provider.calls,[])
    async def test_named_and_collective_departure_dates_are_code_owned(self):
        plan=self.r.request('What should Alex deal with before leaving tomorrow?','s')
        self.assertEqual(plan['subject'],'alex');self.assertEqual(plan['start'],'2026-10-23')
        self.assertEqual(set(plan['sources']),{'calendar','home','weather'})
        plan=self.r.request('What should we sort out before leaving next Thursday?','s')
        self.assertEqual(plan['start'],'2026-10-29');self.assertEqual(plan['subject'],'all')
    async def test_unsupported_dates_clarify_and_do_not_fall_back_to_today(self):
        for date in ('next month','tomorrow at 07:00','tomorrow and Friday'):
            out=await self.ask('What should we sort out before leaving '+date+'?')
            self.assertEqual(out['status'],'clarification_required');self.assertEqual(self.client.calls,[])
    async def test_followup_refreshes_sources_and_keeps_date_person(self):
        await self.ask('How does the weather affect things at home tomorrow?')
        out=await self.ask('And Friday?')
        self.assertEqual(out['period']['start'],'2026-10-23');self.assertEqual(self.client.calls,['states','states'])
        self.assertEqual(len(self.weather_calls),2)
    async def test_scope_expiry_revision_day_speaker_and_unrelated_clear(self):
        mutations=(lambda:self.clock.__setitem__(0,301),lambda:self.p._data.__setitem__('revision',2),
                   lambda:self.now.__setitem__(0,datetime(2026,10,23,1,tzinfo=ZONE)))
        for change in mutations:
            await self.ask('How does the weather affect things at home today?');change()
            self.assertIsNone(await self.ask('And Friday?'))
        await self.ask('How does the weather affect things at home today?',speaker='alex')
        self.assertIsNone(await self.ask('And Friday?',speaker='sam'))
        await self.ask('How does the weather affect things at home today?')
        await self.ask('How do I cook pasta?');self.assertNotIn('s',self.r.sessions)
    async def test_unknown_singular_after_household_clarifies(self):
        self.r.sessions['s']={'scope':self.r.scope(),'expires':300,'subject':'all','sources':['home','weather'],
                              'start':'2026-10-22','end':'2026-10-23','goal':'connections','question':'Household check'}
        out=await self.ask('And her plans?');self.assertEqual(out['status'],'clarification_required')
    async def test_only_literal_public_clause_is_sent_without_private_context(self):
        out=await self.ask('How does the weather affect things at home today, and check the latest Fixture release?')
        self.assertEqual(out['status'],'success')
        self.assertEqual(self.public_calls,['the latest Fixture release']);self.assertIn('https://example.com/releases',out['message'])
        self.assertNotIn('Kitchen window',self.public_calls[0])
        await self.ask('And Friday?');self.assertEqual(len(self.public_calls),1)
    async def test_private_public_queries_clarify_without_any_search(self):
        for q in ('Sam school timetable','Sams school timetable','my travel calendar','https://example.com/private','user@example.com','192.168.1.1 uptime'):
            out=await self.ask('How does weather affect our plans tomorrow, and check '+q+'?')
            self.assertEqual(out['status'],'clarification_required')
        self.assertEqual(self.public_calls,[])
    async def test_public_noun_update_does_not_bypass_private_query_gate(self):
        out=await self.ask('How does weather affect our plans tomorrow, and check the latest Sam calendar update?')
        self.assertEqual(out['status'],'clarification_required');self.assertEqual(self.public_calls,[])
    async def test_model_cannot_emit_actions_assurances_or_home_departure_time(self):
        for answer in ('Everything is safe.','The house is secure.','Leave home at 08:00.',
                       'I have booked the flight.','You are free tomorrow.','The kitchen window is 99 percent open.'):
            self.provider.answer=answer
            out=await self.ask('How does the weather affect things at home today?')
            self.assertEqual(out['status'],'unavailable')
    async def test_model_review_failure_has_no_external_fallback(self):
        self.provider.review={'grounded':False,'useful':True,'issue':'unsupported_fact'}
        out=await self.ask('How does the weather affect things at home today?')
        self.assertEqual(out['status'],'unavailable');self.assertEqual(self.public_calls,[])
    async def test_changed_context_during_inference_suppresses_result(self):
        self.provider.mutate=lambda:self.p._data.__setitem__('revision',self.p._data['revision']+1)
        out=await self.ask('How does the weather affect things at home today?')
        self.assertEqual(out['status'],'unavailable')
    async def test_permission_revoke_and_unknown_states_do_not_report_all_clear(self):
        self.client.states[0]['state']='unavailable'
        self.provider.answer='Some exposed window readings are unknown; with rain forecast, consider checking the kitchen window.'
        out=await self.ask('How does the weather affect things at home today?')
        self.assertTrue(out['partial']);self.assertIn("can't see every home sensor",out['message'])
        self.p._data['sharing_policy']['knowledge_access']['mode']='disabled'
        self.assertIsNone(await self.ask('And Friday?'));self.assertEqual(self.r.sessions,{})
    async def test_seasonal_mower_and_unrelated_unavailable_devices_are_not_alerts(self):
        self.client.states.append({'entity_id':'vacuum.fixture','state':'unavailable','attributes':{}})
        self.r.allowed=frozenset(set(self.r.allowed)|{'vacuum.fixture'})
        out=await self.ask('How does the weather affect things at home today?')
        self.assertEqual(out['status'],'success');self.assertNotIn('vacuum',json.dumps(self.provider.calls))
    async def test_security_request_is_not_answered_as_departure_assurance(self):
        out=await self.ask('Is the house secure before we leave tomorrow?')
        self.assertEqual(out['status'],'clarification_required');self.assertEqual(self.client.calls,[])
    async def test_next_trip_owner_gate_prevents_other_person_read(self):
        out=await self.ask('What should Sam prepare for the next trip and what is open at home?')
        self.assertEqual(self.travel_calls,[])
        self.assertEqual(out['status'],'success');self.assertTrue(out['partial'])

    async def test_unavailable_journey_does_not_require_invented_travel_facts(self):
        self.provider.answer="Sam's requested trip details are unknown; HA currently reports the kitchen window open, so consider rechecking before leaving."
        out=await self.ask('What should Sam prepare for the next trip and what is open at home?')
        self.assertEqual(out['status'],'success');self.assertTrue(out['partial']);self.assertEqual(self.travel_calls,[])
        context=json.loads(self.provider.calls[0]['input_messages'][0]['content'])
        self.assertEqual([f['kind'] for f in context['evidence']['facts']].count('travel_summary'),0)
        self.assertTrue(any(f['kind']=='source_gap' and f['owners']==['sam'] for f in context['evidence']['facts']))
    async def test_next_trip_and_exact_destination_are_not_substituted(self):
        self.p._data['members'][0]['id']='benny'
        self.p._data['sharing_policy']['additional_category_approval']={'source':'Fixture approval','recorded_on':'2026-10-22','categories':['benny_travel_details']}
        out=await self.ask('What should Alex prepare for the next trip and what is open at home?')
        self.assertEqual(out['status'],'success');self.assertEqual(self.travel_calls,['When is my next travel?'])
        self.assertNotIn('conditional_connection',json.loads(self.provider.calls[0]['input_messages'][0]['content'])['reasoning_board'])
        await self.ask('And Friday?');self.assertEqual(self.travel_calls[-1],'When is my next travel?')
        await self.ask('What should Alex prepare for travel to Perth and what is open at home?')
        self.assertEqual(self.travel_calls[-1],'When is my travel to Perth?')
        out=await self.ask('What should Alex prepare for travel to Atlantis and what is open at home?')
        self.assertEqual(out['status'],'clarification_required');self.assertEqual(len(self.travel_calls),3)
    async def test_connected_cannot_stream_internal_source_calls_and_restores_outer_sink(self):
        outer=lambda *args:None
        token=sentence_sink.set(outer)
        try:
            await self.ask('How does the weather affect things at home today, and check the latest Fixture release?')
            self.assertIs(sentence_sink.get(),outer)
        finally: sentence_sink.reset(token)
    async def test_multiple_named_subjects_need_clarification(self):
        out=await self.ask('What should Alex and Sam sort out before leaving tomorrow?')
        self.assertEqual(out['status'],'clarification_required')
    async def test_budget_and_timeout_never_send_truncated_evidence(self):
        self.provider.policy=SimpleNamespace(maximum_input_characters=100)
        out=await self.ask('How does the weather affect things at home today?')
        self.assertEqual(out['status'],'unavailable');self.assertEqual(self.provider.calls,[])
    async def test_groups_do_not_double_count_individual_contacts_or_lights(self):
        self.client.states.append({'entity_id':'light.group','state':'on','attributes':{'entity_id':['light.office'],'friendly_name':'Fixture group'}})
        self.r.allowed=frozenset(set(self.r.allowed)|{'light.group'})
        await self.ask('How does weather affect things at home today?')
        context=json.loads(self.provider.calls[0]['input_messages'][0]['content'])
        lights=[json.loads(f['text']) for f in context['evidence']['facts'] if f['kind']=='home_state' and 'lights' in f['text']]
        self.assertEqual(lights[0]['checked'],1)
    async def test_ambiguous_followup_after_public_lookup_clarifies(self):
        await self.ask('How does weather affect things at home today, and check the latest Fixture release?')
        out=await self.ask('Why?')
        self.assertEqual(out['status'],'clarification_required');self.assertEqual(len(self.public_calls),1)
    async def test_no_unchecked_calendar_or_any_safety_language_in_composed_reply(self):
        for answer in ('There are no specific plans for Friday.','This is not a safety assessment.',
                       'No home changes are reported.'):
            self.provider.answer=answer
            self.assertEqual((await self.ask('How does weather affect things at home today?'))['status'],'unavailable')
    async def test_session_limit_and_read_permission_change(self):
        for i in range(105):
            plan=self.r.request('How does weather affect things at home today?',str(i));self.r.sessions[str(i)]=plan
        # Cap applies to accepted handle calls, not the standalone parser.
        await self.ask('How does weather affect things at home today?')
        self.assertEqual(len(self.r.sessions),100)
        self.r.allowed=frozenset()
        self.assertIsNone(await self.ask('And Friday?'))
    async def test_explicit_person_fact_followup_leaves_connected_route(self):
        for question in ('And his birthday?','How old is she?','And her job?'):
            await self.ask('How does weather affect things at home today?')
            self.assertIsNone(await self.ask(question));self.assertNotIn('s',self.r.sessions)
    async def test_existing_web_research_disable_is_respected(self):
        self.r.public_enabled=lambda key:False
        out=await self.ask('How does weather affect things at home today, and check the latest Fixture release?')
        self.assertEqual(out['status'],'clarification_required');self.assertEqual(self.public_calls,[])
        self.assertEqual(self.client.calls,[])
    async def test_unavailable_forecast_is_explicit_partial_not_complete_success(self):
        async def unavailable(a,b): return 'The home forecast is temporarily unavailable; I have not guessed destination weather.'
        self.r.weather=unavailable
        out=await self.ask('How does weather affect things at home today?')
        self.assertEqual(out['status'],'success');self.assertTrue(out['partial']);self.assertIn('forecast coverage',out['message'])
    async def test_failed_neural_departure_with_no_appointments_has_verified_home_recovery(self):
        self.provider.answer='The house is secure.'
        out=await self.ask('What should we sort out before leaving tomorrow?')
        self.assertEqual(out['status'],'success');self.assertFalse(out['interpreted'])
        self.assertEqual(out['composition'],'verified_home_recheck_recovery')
        self.assertIn('reports 1 exposed door/window contacts open',out['message'])
        self.assertNotIn('secure',out['message']);self.assertTrue(out['partial'])
    def test_recovery_never_suppresses_a_recorded_appointment_or_travel_public_request(self):
        evidence={'facts':[{'kind':'appointment','text':'Fixture event'}],'source_failures':[]}
        self.assertIsNone(self.r.home_recheck_recovery(evidence,{'goal':'predeparture','sources':['home','calendar']}))
        self.assertIsNone(self.r.home_recheck_recovery({'facts':[],'source_failures':[]},
            {'goal':'predeparture','sources':['home','public']}))
    async def test_internal_rule_echo_is_not_a_natural_answer(self):
        self.provider.answer='The kitchen window is open. Do not claim rain will enter the home.'
        out=await self.ask('How does weather affect things at home today?')
        self.assertEqual(out['status'],'unavailable');self.assertEqual(out['interpretation_failure'],'Not conversational')
    def test_appointment_before_leaving_is_not_misclassified_as_a_work_routine(self):
        evidence={'people':{'sam':'Sam'},'source_failures':[],'truncated':False,'facts':[
            {'id':'R1','kind':'routine','owners':['sam'],'text':'Sam usual school timetable: 08:15–12:50; attendance unknown.'},
            {'id':'A1','kind':'appointment','owners':['sam'],'text':'Music rehearsal',
             'start':'2026-10-23T17:00:00+02:00','end':'2026-10-23T18:00:00+02:00',
             'local_start':'17:00','local_end':'18:00'}]}
        result=self.r.validate(json.dumps({'answer':"Sam's rehearsal is scheduled at 17:00, so consider that before leaving."}),evidence,None)
        self.assertIn('17:00',result)
        with self.assertRaisesRegex(ValueError,'Routine treated as attendance'):
            self.r.validate(json.dumps({'answer':'Sam is at school at 08:15.'}),evidence,None)

    async def test_destination_adapter_boilerplate_is_not_local_forecast_content(self):
        plan=self.r.request('How does weather affect our plans tomorrow?','s')
        evidence,_=await self.r.collect(plan)
        weather=next(f for f in evidence['facts'] if f['kind']=='home_weather')
        self.assertEqual(weather['scope'],'home_area_only')
        self.assertIn('rain',weather['text']);self.assertNotIn('destination',weather['text'])

    def test_coverage_note_is_short_and_unchanged_followup_does_not_repeat_it(self):
        gaps=['other household personal calendars are not connected in this view','some exposed home readings are unknown']
        evidence={'source_failures':gaps}
        self.assertEqual(self.r.coverage_note(evidence,{}),"I can't see everyone's calendar or every home sensor.")
        self.assertEqual(self.r.coverage_note(evidence,{'previous_gaps':tuple(sorted(gaps))}),'')
        self.assertIn('weather',self.r.coverage_note({'source_failures':gaps+['weather could not be checked']},
            {'previous_gaps':tuple(sorted(gaps))}))

    async def test_gap_note_dedup_does_not_cache_sensor_or_weather_reads(self):
        self.client.states[0]['state']='unknown'
        self.provider.answer='The forecast calls for rain locally; consider checking any unknown window readings.'
        first=await self.ask('How does weather affect things at home tomorrow?')
        again=await self.ask('And Friday?')
        self.assertIn("can't see every home sensor",first['message'])
        self.assertNotIn("can't see every home sensor",again['message'])
        self.assertTrue(first['partial']);self.assertTrue(again['partial'])
        self.assertEqual(self.client.calls,['states','states']);self.assertEqual(len(self.weather_calls),2)


class PilotSemanticRegressionTests(unittest.TestCase):
    def setUp(self):
        self.evidence={'people':{'benny':'Benny','mia':'Mia'},'source_failures':[],'truncated':False,'facts':[
            {'id':'H1','kind':'home_state','owners':[],'text':json.dumps({'scope':'exposed door/window contacts only',
                'checked':1,'active_count':1,'unknown_count':0,'active_examples':['Master bedroom window']})},
            {'id':'W1','kind':'home_weather','owners':[],'text':'Home-area forecast: Friday 23 October: rain.'},
            {'id':'C1','kind':'coverage','owners':['benny','mia'],'text':'Returned calendar entries are plans.',
                'returned_entries':0},
        ]}
        self.plan={'sources':['home','calendar','weather'],'goal':'predeparture','start':'2026-10-23'}

    def check(self,text,reason=None,plan=None):
        if reason:
            with self.assertRaisesRegex(ValueError,reason):
                ConnectedUnderstanding.validate(json.dumps({'answer':text}),self.evidence,None,plan or self.plan)
        else:return ConnectedUnderstanding.validate(json.dumps({'answer':text}),self.evidence,None,plan or self.plan)

    def test_user_reported_future_reading_is_rejected_even_with_positive_model_review(self):
        self.check("Friday's open contacts include the Master Bedroom window.",'Future home state inferred')
        self.check('The master bedroom window will be open tomorrow.','Future home state inferred')
        self.check('The master bedroom window is open on Friday.','Home snapshot needs current attribution')

    def test_snapshot_now_and_future_recheck_are_not_conflated(self):
        self.check('HA currently reports the master bedroom window open; with rain forecast for Friday, consider rechecking it before leaving.')
        self.check('Before leaving on Friday, consider checking the window, which HA currently reports open; rain is forecast locally.')
        self.check('These are the current HA readings. The bedroom window is open; with rain forecast for Friday, consider rechecking before leaving.')

    def test_present_tense_home_check_without_future_day_is_not_rejected(self):
        self.evidence['checked_on']=self.plan['start']
        self.check('The bedroom window is open; rain is forecast locally, so consider rechecking it.')

    def test_calendar_clash_never_assigns_a_work_location(self):
        self.evidence['facts'].append({'id':'O1','kind':'overlap','owners':['benny'],
            'text':'Benny has overlapping work meetings Friday.'})
        for claim in ('Benny has overlapping meetings Friday, so confirm if he needs to stay home.',
                      'Benny needs to work from home tomorrow.',
                      'Confirm whether the meetings require attendance in person.'):
            self.check(claim,'Unprovided location requirement')
        self.check("Benny's calendar shows overlapping meetings Friday, so consider checking which commitments apply; rain is forecast locally.")

    def test_conflict_needs_a_code_calculated_overlap_not_multiple_titles(self):
        self.check('Benny has overlapping work meetings Friday.','Unprovided calendar conflict')

    def test_real_overlap_cannot_be_dropped_to_evade_the_work_location_guard(self):
        self.evidence['facts'].append({'id':'O1','kind':'overlap','owners':['benny'],
            'text':'Benny has overlapping work meetings Friday.'})
        self.check('HA currently reports the bedroom window open; with rain forecast, consider checking it.',
            'Relevant calendar overlap omitted')
        self.check("Benny's meetings coincide on Friday, so consider checking which applies; rain is forecast locally.")

    def test_reported_mia_weather_evasion_and_destination_disclaimer_are_rejected(self):
        plan={**self.plan,'sources':['calendar','weather'],'subject':'mia','goal':'connections'}
        self.check("Mia's plans for tomorrow are not confirmed by the calendar, and the home-area forecast does not specify destination weather.",
            'Unrequested destination commentary',plan)
        self.check('The provided facts do not link weather to plans.','Available forecast omitted',plan)

    def test_local_forecast_is_still_useful_when_no_extra_appointments_returned(self):
        self.check("Rain is forecast locally for Friday, so if Mia is heading outside, rain protection could be useful. I found no extra appointments in her connected calendar.")

    def test_destination_scope_can_be_discussed_for_an_actual_journey(self):
        self.check('The local forecast calls for rain; destination weather was not checked.',
            plan={**self.plan,'sources':['weather','travel']})

    def test_explicit_public_airport_lookup_is_not_an_unrequested_destination_topic(self):
        self.evidence['facts'].append({'id':'P1','kind':'public_information','owners':[],
            'text':'The public airport update is available.'})
        self.check('Rain is forecast locally; the public airport update is available.',
            plan={**self.plan,'sources':['weather','public'],'query':'the public airport update'})

    def test_requested_journey_cannot_be_dropped_after_a_home_wording_correction(self):
        self.evidence['facts'].append({'id':'T1','kind':'travel_summary','owners':['benny'],'text':'Next journey to Perth.'})
        self.check('HA currently reports the window open; rain is forecast locally.',
            'Requested travel omitted',{**self.plan,'sources':['home','weather','travel']})
        self.check('No travel preparation details were requested; rain is forecast.',
            'Requested travel omitted',{**self.plan,'sources':['home','weather','travel']})

    def test_weather_without_departure_request_does_not_invent_one(self):
        self.check('Rain is forecast, so check the window before departure.','Unrequested departure commentary',
            {**self.plan,'goal':'connections'})

    def test_weather_plans_mentions_a_recorded_timed_commitment_not_only_the_forecast(self):
        self.evidence['facts'].append({'id':'A1','kind':'appointment','owners':['mia'],'text':'Music rehearsal',
            'start':'2026-10-23T17:00:00+02:00','end':'2026-10-23T18:00:00+02:00','local_start':'17:00','local_end':'18:00'})
        plan={**self.plan,'goal':'connections','subject':'mia','sources':['calendar','weather']}
        self.check('Rain is forecast locally; if Mia is going out, rain protection could be useful.',
            'Weather plans appointment omitted',plan)
        self.check('Mia has rehearsal scheduled at 17:00; with rain forecast locally, rain protection could be useful if going out.',plan=plan)

    def test_unavailable_forecast_does_not_require_an_invented_weather_condition(self):
        self.evidence['facts'][1]['text']='The home forecast is temporarily unavailable.'
        self.check('The home forecast is unavailable; HA currently reports the master bedroom window open, so consider rechecking before leaving.')

    def test_weather_cannot_classify_an_activity_as_indoor_or_unaffected(self):
        self.check('Rain is forecast; music rehearsal is indoors and not affected by the weather.',
            'Unprovided activity location',{**self.plan,'goal':'connections','sources':['calendar','weather']})

    def test_conditional_outdoor_uncertainty_is_not_routine_attendance(self):
        self.evidence['facts'].append({'id':'R1','kind':'routine','owners':['mia'],
            'text':'Mia usual school 08:15 to 12:50; attendance unknown.'})
        self.check('Rain is forecast; outdoor attendance is not confirmed, so rain protection could help if going out.')


class IsolatedStateReaderTests(unittest.IsolatedAsyncioTestCase):
    async def test_state_reader_uses_separate_client_and_disconnects_on_error(self):
        import ast
        from unittest.mock import AsyncMock
        # Windows' lightweight test runtime omits websockets. Exercise the exact
        # saved method here; actual class/socket regressions also run in the app.
        root=Path(__file__).resolve().parents[1]
        source=root/'src/jarvis/homeassistant/client.py'
        if not source.exists(): source=root/'jarvis/app/src/jarvis/homeassistant/client.py'
        node=next(n for n in ast.walk(ast.parse(source.read_text(encoding='utf-8')))
                  if isinstance(n,ast.AsyncFunctionDef) and n.name=='get_states_isolated')
        outer=SimpleNamespace(url='http://fixture',token='not-a-real-token',logger=SimpleNamespace())
        for failure in (False,True):
            reader=SimpleNamespace(_connect_socket=AsyncMock(),_get_states_once=AsyncMock(return_value=[]),disconnect=AsyncMock())
            if failure: reader._get_states_once.side_effect=RuntimeError('Fixture read failure')
            namespace={'asyncio':asyncio,'HomeAssistantClient':lambda *a:reader}
            exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual isolated read method>','exec'),namespace)
            if failure:
                with self.assertRaises(RuntimeError): await namespace['get_states_isolated'](outer)
            else: self.assertEqual(await namespace['get_states_isolated'](outer),[])
            reader.disconnect.assert_awaited_once()


class ApplicationRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_application_reuses_existing_normalized_research_disable(self):
        from test_household_reasoning import ApplicationTests
        handle,app,p,provider=ApplicationTests().app()
        checked=[]
        app.container.research_controller=SimpleNamespace(enabled=lambda key:checked.append(key) or False)
        app.container.conversation_store=SimpleNamespace(normalize_conversation_id=lambda key:'normalized-'+key)
        out=await handle(app,'How does weather affect things at home today, and check the latest Fixture release?','s')
        self.assertEqual(out['status'],'clarification_required');self.assertEqual(checked,['normalized-s'])
    async def test_connected_precedes_old_handlers_and_seeds_named_focus(self):
        from test_household_reasoning import ApplicationTests
        handle,app,p,provider=ApplicationTests().app()
        calls=[]
        async def connected(text,key):
            calls.append(text)
            return {'status':'success','message':'Checked connected facts.','provider':'connected_understanding','subject':'sam'}
        app.container.connected_understanding=SimpleNamespace(handle=connected)
        out=await handle(app,'What should Sam sort out before leaving tomorrow?','s')
        self.assertEqual(out['provider'],'connected_understanding')
        text,result=app.container.household_reasoning.resolve('How old is she?','s')
        self.assertEqual(text,'How old is Sam');self.assertIsNone(result)


if __name__=='__main__': unittest.main()
