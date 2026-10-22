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
        self.answer='The kitchen window is reported open now, so consider checking it again before departure.'
        self.review={'grounded':True,'useful':True,'issue':'none'}
        self.mutate=None
    def reason_local(self,**kw):
        assert sentence_sink.get() is None
        self.calls.append(kw)
        if self.mutate: self.mutate()
        return {'status':'success','message':json.dumps(self.review if kw['instructions'].startswith('Check ONLY') else {'answer':self.answer})}


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
        self.provider.answer='Some exposed window readings are unknown; consider checking the kitchen window before departure.'
        out=await self.ask('How does the weather affect things at home today?')
        self.assertTrue(out['partial']);self.assertIn('Still unknown',out['message'])
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
    async def test_next_trip_and_exact_destination_are_not_substituted(self):
        self.p._data['members'][0]['id']='benny'
        self.p._data['sharing_policy']['additional_category_approval']={'source':'Fixture approval','recorded_on':'2026-10-22','categories':['benny_travel_details']}
        out=await self.ask('What should Alex prepare for the next trip and what is open at home?')
        self.assertEqual(out['status'],'success');self.assertEqual(self.travel_calls,['When is my next travel?'])
        self.assertIsNone(json.loads(self.provider.calls[0]['input_messages'][0]['content'])['reasoning_board']['conditional_connection'])
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
