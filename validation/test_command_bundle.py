"""Regressions for direct speech acts, faithful shortening and cache-only United."""
import unittest
from datetime import timedelta
from unittest.mock import AsyncMock,patch
import test_companion_agent as agent_fixture
import test_football_updates as football_fixture
from jarvis.calendar_context import calendar_scope

class RoutingRepairs(unittest.IsolatedAsyncioTestCase):
 setUp=agent_fixture.AgentTests.setUp
 async def choice(self,text,expected):
  with calendar_scope({'actor':'user','read':True,'write':True}):
   state=self.a.agent.state('chat','phone')
   async def choose(provider,instructions,data,schema,**kw):
    self.assertEqual(schema['properties']['tool']['enum'],[expected])
    return {'tool':expected,'members':['benny'] if expected=='remember_detail' else ['emrik']}
   with patch('jarvis.companion_agent.local_json',new=choose):return await self.a.agent.plan(text,'chat','phone',state)
 async def test_anything_on_for_person_is_calendar_overview(self):
  out=await self.choice('Anything on for Emrik next Friday?','household_plans');self.assertEqual(out['tool'],'plans')
 async def test_named_preference_is_report_not_biography(self):
  out=await self.choice('Benny prefers high fidelity music.','remember_detail');self.assertEqual((out['tool'],out['operation']),('memory','write'))
 async def test_explicit_light_command_reaches_existing_authorised_home_tool(self):
  out=await self.choice('Turn off the kitchen lights','home_tools');self.assertEqual(out['tool'],'home')
 async def test_introduced_first_person_preference_uses_memory_executor(self):
  out=await self.choice('I prefer high fidelity when listening to music','remember_detail');self.assertEqual(out['tool'],'memory')
 async def test_recall_question_keeps_read_only_capability(self):
  with calendar_scope({'actor':'user','read':True,'write':True}):
   state=self.a.agent.state('chat','phone')
   with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'tool':'recall_detail','members':['benny']})) as model:
    out=await self.a.agent.plan('What does Benny prefer when listening to music?','chat','phone',state)
   self.assertEqual(model.call_args.args[3]['properties']['tool']['enum'],['recall_detail']);self.assertEqual(out['operation'],'query')
 async def test_quoted_preference_does_not_force_report(self):
  with calendar_scope({'actor':'user','read':True,'write':True}):
   state=self.a.agent.state('chat','phone')
   with patch('jarvis.companion_agent.local_json',new=AsyncMock(side_effect=[{'tool':'general_chat','members':[]},{'answer':'That is reported speech.'}])) as model:
    await self.a.agent.plan('Linda said "I prefer trains"','chat','phone',state)
   self.assertGreater(len(model.call_args_list[0].args[3]['properties']['tool']['enum']),1)
 async def test_shortening_review_receives_explicit_kit_and_venue_semantics(self):
  self.profile._data['activity_profiles']=[{'usual_venue':'Haddal School','equipment':['instrument','sheet music']}]
  original='Have the instrument and sheet music ready for rehearsal tomorrow at 17:30. It usually takes place at Haddal School; check the venue for this appointment.'
  state={'response_reference':{'text':original,'expires':300}}
  answer='Bring instrument and sheet music; check the usual Haddal School for this appointment.'
  with patch('jarvis.companion_agent.local_json',new=AsyncMock(side_effect=[{'answer':answer},{'faithful':True}])) as model:
   result=await self.a.agent.present_answer('Make that shorter',state)
  self.assertEqual(result,answer);review=model.call_args_list[1]
  self.assertEqual(review.args[2]['required_kit'],['instrument','sheet music']);self.assertTrue(review.args[2]['venue_check'])
  self.assertIn('NOT a lost venue check',review.args[1]);self.assertEqual(state['response_reference']['expires'],300)

class UnitedDashboard(unittest.IsolatedAsyncioTestCase):
 setUp=football_fixture.FootballTests.setUp
 async def test_projection_only_reads_cache_and_never_sends_notifications(self):
  self.assertIsNone(self.f.dashboard()['next_match']);self.f.notify.assert_not_awaited()
  await self.f.refresh();board=self.f.project()['dashboard']
  self.assertEqual(board['next_match']['home'],'Manchester United');self.assertEqual(board['standing']['id'],'360')
  self.assertTrue(board['cache_only']);self.f.notify.assert_not_awaited()
 async def test_failed_source_withholds_old_result(self):
  await self.f.refresh();self.f.errors=['fixtures source unavailable; previous data is withheld.']
  self.assertIsNone(self.f.dashboard()['next_match']);self.assertNotIn('fixtures',self.f.dashboard()['sources'])
 async def test_stale_cache_is_not_presented_as_live(self):
  await self.f.refresh();self.time[0]+=timedelta(minutes=11)
  board=self.f.dashboard();self.assertIsNone(board['next_match']);self.assertIsNone(board['standing']);self.assertEqual(board['sources'],{})
 async def test_last_final_excludes_pending_and_future_scores(self):
  self.data['results']=football_fixture.schedule([football_fixture.event(id='7',status='STATUS_FULL_TIME',completed=True,when='2026-10-30T12:30Z',score=('2','1')),football_fixture.event(id='8')])
  await self.f.refresh();self.assertEqual(self.f.dashboard()['last_result']['id'],'7')

if __name__=='__main__':unittest.main()
