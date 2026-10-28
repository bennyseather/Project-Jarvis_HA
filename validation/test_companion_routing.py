"""Interactive routing: exact places, private home, failures and no actions."""
import json,unittest
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from jarvis.companion_routing import CompanionRouting
from jarvis.calendar_context import calendar_scope
from test_companion_coordinator import NOW
from test_companion_agent import plan
import test_companion_agent as agent_fixture
class Provider:
 def __init__(self):self.calls=[];self.result={'origin_quote':'the house','destination_quote':'Ulsteinvik','mode':'driving','reverse':False}
 def reason_local(self,**kw):self.calls.append(kw);return {'status':'success','message':json.dumps(self.result)}
class Transport:
 def __init__(self):self.calls=[];self.minutes=18;self.fail=False
 def place(self,name):self.calls.append(('place',name));return {'label':'Ulsteinvik, Ulstein','coordinates':{'latitude':62.34,'longitude':5.85}}
 def route(self,a,b,when,mode,**kw):
  self.calls.append(('route',deepcopy(a),deepcopy(b),when,mode,kw))
  return {'state':'source_error' if self.fail else 'available','options':[] if self.fail else [{'duration_minutes':self.minutes}]}
class RoutingTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.provider=Provider();self.transport=Transport();self.home=AsyncMock(return_value={'latitude':62.12345678,'longitude':5.23456789});self.clock=[1]
  self.owner=SimpleNamespace(policy=SimpleNamespace(data={'interactive_home_routing':{'enabled':True,'approval_source':'Fictional explicit approval','recorded_on':'2026-10-28'}}),provider=self.provider,container=SimpleNamespace(home_assistant=SimpleNamespace(get_home_location=self.home),household_thinking=None),now=lambda:NOW,clock=lambda:self.clock[0])
  self.owner.agent=SimpleNamespace(reads=SimpleNamespace(prior=lambda state:state.get('read_focus')))
  self.router=CompanionRouting(self.owner,transport=self.transport);self.state={}
 async def ask(self,text='Can you check the driving time from the house to Ulsteinvik?',read=True):
  with calendar_scope({'actor':'u','read':read,'write':False}):return await self.router.handle(text,'s',self.state)
 async def test_unapproved_home_is_never_loaded_or_sent(self):
  self.owner.policy.data.pop('interactive_home_routing');r=await self.ask()
  self.assertTrue(r['home_route_approval_required']);self.assertEqual(self.home.await_count,0);self.assertEqual(self.transport.calls,[])
 async def test_user_route_is_checked_instead_of_calendar_evidence(self):
  r=await self.ask();self.assertEqual(r['driving_minutes'],18);self.assertIn('Entur estimates about 18',r['message']);self.assertFalse(r['live_traffic']);self.assertIn('saved home location',r['message'])
  self.assertTrue(self.transport.calls[-1][-1]['depart_after']);self.assertEqual(self.home.await_count,1)
 async def test_coordinates_are_not_sent_to_qwen_or_shown_in_response_state(self):
  r=await self.ask();payload=json.dumps([self.provider.calls,r,self.state]);self.assertNotIn('62.12345678',payload);self.assertNotIn('5.23456789',payload)
  self.assertIn('62.12345678',json.dumps(self.transport.calls,default=str))
 async def test_home_is_not_current_presence_or_gym_exact_address(self):
  r=await self.ask('The gymnastics building is in Ulsteinvik, can you check driving time from the house to Ulsteinvik?')
  self.assertIn('exact gym entrance',r['message']);self.assertNotIn('you are home',r['message']);self.assertNotIn('arranged',r['message'])
 async def test_unknown_origin_requires_one_question_without_guessing_home(self):
  self.provider.result['origin_quote']='';r=await self.ask('How long is the drive to Ulsteinvik?');self.assertEqual(r['status'],'clarification_required');self.assertEqual(self.home.await_count,0);self.assertEqual(self.transport.calls,[])
 async def test_partial_route_can_be_completed_without_repeating_home(self):
  self.provider.result['destination_quote']='';r=await self.ask('How long is the drive from the house?');self.assertIn('Where',r['message'])
  self.provider.result.update(origin_quote='',destination_quote='Ulsteinvik');r=await self.ask('Ulsteinvik');self.assertEqual(r['status'],'success')
 async def test_model_cannot_invent_city_or_url(self):
  for value in ('Oslo','https://example.com/private'):
   self.provider.result['destination_quote']=value;r=await self.ask();self.assertEqual(r['status'],'unavailable')
  self.assertEqual(self.transport.calls,[])
 async def test_failed_source_never_estimates_minutes(self):
  self.transport.fail=True;r=await self.ask();self.assertEqual(r['status'],'unavailable');self.assertNotIn('driving_minutes',r);self.assertNotIn('18',r['message'])
 async def test_invalid_duration_never_reaches_user(self):
  for value in (-1,float('nan'),True,2000):
   self.transport.minutes=value;r=await self.ask();self.assertEqual(r['status'],'unavailable')
 async def test_reverse_is_explicit_and_requeries(self):
  await self.ask();self.provider.result.update(origin_quote='',destination_quote='',reverse=True)
  r=await self.ask('And back?');self.assertEqual(r['status'],'success');self.assertIn('to home',r['message']);self.assertEqual(self.transport.calls[-1][2]['latitude'],62.12345678)
 async def test_expired_route_is_not_silently_reused(self):
  await self.ask();self.clock[0]=400;self.provider.result.update(origin_quote='',destination_quote='Ulsteinvik');r=await self.ask('And to Ulsteinvik?');self.assertEqual(r['status'],'clarification_required')
 async def test_read_permission_is_required_no_write_permission_needed(self):
  r=await self.ask(read=False);self.assertEqual(r['status'],'forbidden');self.assertEqual(self.provider.calls,[])
  r=await self.ask();self.assertEqual(r['status'],'success')
 async def test_no_bus_time_is_invented(self):
  self.provider.result['mode']='public_transport';r=await self.ask();self.assertEqual(r['status'],'unavailable');self.assertEqual(self.transport.calls,[])
 async def test_source_ambiguity_stays_explicit(self):
  self.transport.place=lambda name:(_ for _ in ()).throw(ValueError('Ambiguous town'))
  r=await self.ask();self.assertEqual(r['status'],'unavailable');self.assertNotIn('driving_minutes',r)
 async def test_meal_comparison_rereads_and_qualifies_home_assumption(self):
  evidence={'people':{'mia':'Mia'},'facts':[{'id':'E1','kind':'appointment','owners':['mia'],'text':'Band','start':'2026-10-29T15:40:00+01:00','end':'2026-10-29T16:00:00+01:00','local_start':'15:40','local_end':'16:00','date':'2026-10-29','date_label':'Thursday 29 October','all_day':False},{'id':'E2','kind':'appointment','owners':['mia'],'text':'Gymnastics','start':'2026-10-29T17:00:00+01:00','end':'2026-10-29T18:30:00+01:00','local_start':'17:00','local_end':'18:30','date':'2026-10-29','date_label':'Thursday 29 October','all_day':False}], 'source_failures':[],'truncated':False,'start':'2026-10-29','end_exclusive':'2026-10-30'}
  reader=SimpleNamespace(handle=AsyncMock(return_value={'status':'success','evidence':evidence}));self.owner.container.household_thinking=SimpleNamespace(reader=reader)
  self.state['read_focus']={'purpose':'availability','between':True,'duration_minutes':45,'subjects':['mia'],'start':'2026-10-29','end':'2026-10-30'}
  r=await self.ask();self.assertIn('If dinner is at home',r['message']);self.assertIn('63 of the recorded 60-minute gap',r['message']);self.assertEqual(reader.handle.await_count,1)
class AgentRouteTests(unittest.IsolatedAsyncioTestCase):
 setUp=agent_fixture.AgentTests.setUp
 say=agent_fixture.AgentTests.say
 async def test_selected_route_uses_fixed_executor_without_original_router(self):
  calls=[]
  async def handle(text,key,state):calls.append(text);return {'status':'success','message':'A verified routing estimate.'}
  self.container.companion_routing=SimpleNamespace(handle=handle)
  r=await self.say('Check the drive from home to Ulsteinvik',plan('route'))
  self.assertEqual(calls,['Check the drive from home to Ulsteinvik']);self.assertEqual(self.original_calls,[]);self.assertEqual(r['agent_tool'],'route')
class DepartRoutingTests(unittest.TestCase):
 def test_depart_now_query_and_validation_are_separate_from_arrive_by(self):
  from jarvis.companion_transport import EnturTransport
  calls=[]
  def http(url,payload):
   calls.append(payload)
   return {'data':{'trip':{'routingErrors':[],'tripPatterns':[{'expectedStartTime':NOW.isoformat(),'expectedEndTime':(NOW+timedelta(minutes=18)).isoformat(),'duration':1080,'legs':[{'mode':'car'}]}]}}}
  c=EnturTransport(http=http);a={'latitude':62.2,'longitude':6.0};b={'latitude':62.34,'longitude':5.85}
  self.assertEqual(c.route(a,b,NOW,'driving',depart_after=True)['options'][0]['duration_minutes'],18)
  self.assertIn('arriveBy:false',calls[-1]['query']);self.assertIn('depart_after',c.route(a,b,NOW,'driving',depart_after=True))
  self.assertEqual(c.route(a,b,NOW,'driving')['options'],[]);self.assertIn('arriveBy:true',calls[-1]['query'])
if __name__=='__main__':unittest.main()
