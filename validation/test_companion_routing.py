"""Interactive routing: exact places, private home, failures and no actions."""
import json,unittest
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from jarvis.companion_routing import CompanionRouting
from jarvis.calendar_context import calendar_scope
from test_companion_coordinator import NOW
from test_planning_preparation_bundle import profile
from test_companion_agent import plan
import test_companion_agent as agent_fixture
class Provider:
 def __init__(self):self.calls=[];self.result={'origin_quote':'the house','destination_quote':'Ulsteinvik','mode':'driving','reverse':False}
 def reason_local(self,**kw):
  self.calls.append(kw);schema=kw['response_schema']['properties']
  value={'meal_location':getattr(self,'meal_location','unspecified')} if 'meal_location' in schema else {'kind':'place_reply','place_quote':getattr(self,'place_quote','School')} if 'place_quote' in schema else self.result
  return {'status':'success','message':json.dumps(value)}
class Transport:
 def __init__(self):self.calls=[];self.minutes=18;self.fail=False
 def place(self,name):self.calls.append(('place',name));return {'label':'Ulsteinvik, Ulstein','coordinates':{'latitude':62.34,'longitude':5.85}}
 def route(self,a,b,when,mode,**kw):
  self.calls.append(('route',deepcopy(a),deepcopy(b),when,mode,kw))
  return {'state':'source_error' if self.fail else 'available','options':[] if self.fail else [{'duration_minutes':self.minutes}]}
class RoutingTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.provider=Provider();self.transport=Transport();self.home=AsyncMock(return_value={'latitude':62.12345678,'longitude':5.23456789});self.clock=[1]
  self.owner=SimpleNamespace(profile=profile(),policy=SimpleNamespace(data={'interactive_home_routing':{'enabled':True,'approval_source':'Fictional explicit approval','recorded_on':'2026-10-28'}}),provider=self.provider,container=SimpleNamespace(home_assistant=SimpleNamespace(get_home_location=self.home),household_thinking=None),now=lambda:NOW,clock=lambda:self.clock[0])
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
  r=await self.ask();self.assertIn('If dinner is at home',r['message']);self.assertIn('63 of the recorded 60-minute gap',r['message']);self.assertGreaterEqual(reader.handle.await_count,1)
class RouteFollowupTests(unittest.IsolatedAsyncioTestCase):
 setUp=RoutingTests.setUp
 ask=RoutingTests.ask
 async def test_short_mode_keeps_previously_supplied_endpoints(self):
  await self.ask();self.provider.result.update(origin_quote='home',destination_quote='Ulsteinvik',mode='driving')
  r=await self.ask('driving');self.assertEqual(r['status'],'success');self.assertEqual(r['driving_minutes'],18)
 async def test_pending_origin_and_destination_survive_mode_question(self):
  self.provider.result.update(mode='unknown');r=await self.ask();self.assertIn('driving or public',r['message'])
  self.provider.result.update(origin_quote='the house',destination_quote='Ulsteinvik',mode='driving')
  r=await self.ask('driving');self.assertEqual(r['status'],'success')
 async def test_dinner_origin_and_configured_driving_default_are_explicit_planning_assumptions(self):
  self.owner.policy.data['transport_preference']='driving_first'
  self.state['read_focus']={'subjects':['mia'],'start':'2026-10-29','end':'2026-10-30','task':'Can we fit dinner between those appointments?','purpose':'availability','between':True,'duration_minutes':45}
  self.provider.result.update(origin_quote='',mode='unknown')
  r=await self.ask('What is the travel time to Ulsteinvik?');self.assertEqual(r['status'],'success');self.assertIn('saved home location',r['message']);self.assertFalse('you are home' in r['message'])
 async def test_new_person_or_date_drops_route_draft(self):
  self.state['read_focus']={'subjects':['mia'],'start':'2026-10-29','end':'2026-10-30','task':'dinner'}
  await self.ask();self.state['read_focus']['start']='2026-10-30';self.state['read_focus']['end']='2026-10-31'
  self.provider.result.update(origin_quote='',destination_quote='',mode='unknown');r=await self.ask('What is the travel time?')
  self.assertEqual(r['status'],'clarification_required');self.assertEqual(self.state['route_pending']['destination'],'')
 async def test_source_venue_can_supply_destination_but_not_invented_places(self):
  self.router.context_venues=AsyncMock(return_value=[{'event':'Gymnastics','current_venue':'Turnhallen','usual_venue':'Gymnastics Building in Ulsteinvik'}])
  self.provider.result.update(origin_quote='home',destination_quote='Ulsteinvik')
  r=await self.ask('What is the travel time from home?');self.assertEqual(r['status'],'success');self.assertTrue(self.state['route_focus']['destination_from_context'])
  self.provider.result['destination_quote']='Bergen';self.assertEqual((await self.ask('What is the travel time?'))['status'],'unavailable')
 async def test_full_usual_venue_is_a_labelled_town_estimate_not_an_unresolvable_building(self):
  self.router.context_venues=AsyncMock(return_value=[{'event':'Gymnastics','current_venue':'','usual_venue':'Gymnastics Building in Ulsteinvik'}])
  self.provider.result.update(origin_quote='home',destination_quote='Gymnastics Building in Ulsteinvik')
  r=await self.ask('What is the travel time from home?')
  self.assertEqual(r['status'],'success');self.assertEqual(self.state['route_focus']['destination'],'Ulsteinvik');self.assertIn('town-level',r['message'])
 async def test_new_concrete_calendar_venue_withdraws_old_context_destination(self):
  self.router.context_venues=AsyncMock(return_value=[{'event':'Gymnastics','current_venue':'Turnhallen','usual_venue':'Gymnastics Building in Ulsteinvik'}])
  await self.ask();self.state['route_focus']['destination_from_context']=True
  self.router.context_venues=AsyncMock(return_value=[{'event':'Gymnastics','current_venue':'Bergen sports centre','usual_venue':''}])
  self.provider.result.update(origin_quote='home',destination_quote='Bergen')
  r=await self.ask('And the travel time?');self.assertEqual(r['status'],'success');self.assertEqual(self.state['route_focus']['destination'],'Bergen')

class FreshVenueTests(unittest.IsolatedAsyncioTestCase):
 setUp=RoutingTests.setUp
 async def venues(self):
  with calendar_scope({'actor':'u','read':True,'write':False}):return await self.router.context_venues(self.state)
 def setup_calendar(self):
  from test_planning_preparation_bundle import Client
  from jarvis.household_thinking import HouseholdThinking
  self.owner.profile._data['activity_profiles']=[{'id':'12345678','person':'mia','source':'family','title':'Gruppe 1','activity':'Gymnastics','usual_venue':'Gymnastics Building in Ulsteinvik','equipment':[],'preparation':None,'duration_minutes':None,'recorded_on':'2026-10-28T12:00:00+00:00','provenance':'Confirmed shared household conversation'}]
  class FreshClient(Client):
   async def get_household_today(self,*args,**kw):
    data=await super().get_household_today(*args,**kw);data['planning']['generated_on']='2026-10-28';return data
  self.client=FreshClient();self.client.events['calendar.familiekalender']=[{'summary':'Band rehearsal','start':'2026-10-29T15:40:00+01:00','end':'2026-10-29T16:00:00+01:00','location':'School'},{'summary':'Gruppe 1','start':'2026-10-29T17:00:00+01:00','end':'2026-10-29T18:30:00+01:00','location':'Turnhallen'}]
  self.owner.container.household_thinking=HouseholdThinking(self.owner.profile,self.client,tuple(self.client.events),self.provider,now=lambda:NOW)
  self.state['read_focus']={'subjects':['mia'],'start':'2026-10-29','end':'2026-10-30','task':'dinner','purpose':'availability','between':True,'duration_minutes':45}
 async def test_dinner_destination_is_following_appointment_not_first(self):
  self.setup_calendar();venues=await self.venues()
  self.assertEqual(len(venues),1);self.assertEqual(venues[0]['event'],'Gruppe 1');self.assertEqual(venues[0]['usual_venue'],'Gymnastics Building in Ulsteinvik');self.assertEqual(venues[0]['planning_place_quote'],'Ulsteinvik')
 async def test_changed_specific_venue_wins_over_usual_and_is_reread(self):
  self.setup_calendar();await self.venues()
  self.client.events['calendar.familiekalender'][1]['location']='Bergen sports centre'
  venues=await self.venues()
  self.assertEqual(venues[0]['current_venue'],'Bergen sports centre');self.assertEqual(venues[0]['usual_venue'],'')
 async def test_unknown_title_cannot_borrow_another_activity_venue(self):
  self.setup_calendar();self.client.events['calendar.familiekalender'][1].update(summary='Unknown appointment',location='')
  self.assertEqual(await self.venues(),[])
 async def test_ambiguous_following_appointments_do_not_choose_one(self):
  self.setup_calendar();self.client.events['calendar.familiekalender'].append({'summary':'Other appointment','start':'2026-10-29T17:00:00+01:00','end':'2026-10-29T18:00:00+01:00','location':'Bergen'})
  self.assertEqual(await self.venues(),[])
 async def test_source_failure_cannot_reuse_a_remembered_destination(self):
  self.setup_calendar();await self.venues()
  self.owner.container.household_thinking.reader.handle=AsyncMock(return_value={'evidence':{'source_failures':['family'],'truncated':False}})
  self.assertEqual(await self.venues(),[])

class AutomaticMealTests(unittest.IsolatedAsyncioTestCase):
 setUp=RoutingTests.setUp
 setup_calendar=FreshVenueTests.setup_calendar
 async def check(self,minutes=45):
  self.setup_calendar();self.state['read_focus']['duration_minutes']=minutes;self.owner.policy.data['transport_preference']='driving_first'
  with calendar_scope({'actor':'u','read':True,'write':False}):return await self.router.meal_plan('about '+str(minutes)+' minutes','s',self.state,{'status':'success','message':'A calendar-only answer.'})
 async def test_both_drives_automatically_count_and_overshoot_is_clear(self):
  r=await self.check();self.assertTrue(r['meal_budget']['complete']);self.assertEqual(r['meal_budget']['checked_travel_minutes'],36);self.assertEqual(r['meal_budget']['remaining_minutes'],-21);self.assertIn('81 minutes',r['message']);self.assertIn('21 minutes longer',r['message']);self.assertEqual(len([c for c in self.transport.calls if c[0]=='route']),2)
  routes=[c for c in self.transport.calls if c[0]=='route'];incoming=next(c for c in routes if c[2]['latitude']==62.12345678);outgoing=next(c for c in routes if c[1]['latitude']==62.12345678)
  self.assertTrue(incoming[-1]['depart_after']);self.assertFalse(outgoing[-1]['depart_after'])
 async def test_asymmetric_journeys_use_both_directions(self):
  old=self.transport.route
  def route(a,b,*args,**kw):
   self.transport.minutes=10 if b['latitude']==62.12345678 else 9
   return old(a,b,*args,**kw)
  self.transport.route=route;r=await self.check()
  self.assertEqual(r['meal_budget']['to_meal_minutes'],10);self.assertEqual(r['meal_budget']['to_next_minutes'],9);self.assertEqual(r['meal_budget']['remaining_minutes'],-4)
 async def test_drives_alone_can_exceed_gap_before_meal_duration_is_given(self):
  self.transport.minutes=40;r=await self.check(None)
  self.assertIn('exceeding the 60-minute gap by 20',r['message']);self.assertNotIn('leaving 0',r['message'])
 async def test_read_access_is_required_for_automatic_journeys(self):
  self.setup_calendar();self.owner.policy.data['transport_preference']='driving_first'
  with calendar_scope({'actor':'u','read':False,'write':False}):r=await self.router.meal_plan('45 minutes','s',self.state,{'status':'success','message':'Old reply'})
  self.assertNotIn('meal_budget',r);self.home.assert_not_awaited();self.assertEqual(self.provider.calls,[])
 async def test_shorter_meal_shows_remaining_margin(self):
  r=await self.check(15);self.assertEqual(r['meal_budget']['remaining_minutes'],9);self.assertIn('leaving 9 minutes',r['message']);self.assertIn('tight margin',r['message'])
 async def test_unknown_duration_still_checks_drives_and_asks_once(self):
  r=await self.check(None);self.assertEqual(r['meal_budget']['checked_travel_minutes'],36);self.assertIn('24 of the 60 minutes',r['message']);self.assertIn('How long',r['message'])
 async def test_missing_previous_venue_never_says_whole_plan_fits(self):
  self.setup_calendar();self.client.events['calendar.familiekalender'][0]['location']='';self.owner.policy.data['transport_preference']='driving_first'
  with calendar_scope({'actor':'u','read':True,'write':False}):r=await self.router.meal_plan('45 minutes','s',self.state,{'status':'success','message':'Old reply'})
  self.assertFalse(r['meal_budget']['complete']);self.assertIsNone(r['meal_budget']['to_meal_minutes']);self.assertEqual(r['meal_budget']['remaining_minutes'],-3);self.assertIn('unchecked journey',r['message']);self.assertNotIn('would fit',r['message'])
 async def test_missing_home_consent_prevents_coordinate_loading(self):
  self.owner.policy.data.pop('interactive_home_routing');r=await self.check();self.assertNotIn('meal_budget',r);self.home.assert_not_awaited();self.assertEqual(self.transport.calls,[])
 async def test_elsewhere_meal_is_not_silently_routed_through_home(self):
  self.provider.meal_location='elsewhere';r=await self.check();self.assertNotIn('meal_budget',r);self.home.assert_not_awaited()
 async def test_non_meal_gap_does_not_trigger_routing(self):
  self.setup_calendar();self.state['read_focus']['task']='Can we fit homework between those appointments?';self.owner.policy.data['transport_preference']='driving_first'
  with calendar_scope({'actor':'u','read':True,'write':False}):r=await self.router.meal_plan('45 minutes','s',self.state,{'status':'success','message':'Homework'})
  self.assertEqual(r['message'],'Homework');self.assertEqual(self.transport.calls,[])
 async def test_one_route_failure_retains_other_leg_without_inventing_total(self):
  old=self.transport.place
  self.transport.place=lambda name:None if name=='School' else old(name)
  r=await self.check(30);self.assertFalse(r['meal_budget']['complete']);self.assertEqual(r['meal_budget']['to_next_minutes'],18);self.assertEqual(r['meal_budget']['remaining_minutes'],12);self.assertIn('Where is Band rehearsal',r['message']);self.assertNotIn('both drives would',r['message'])
 async def test_missing_venue_reply_completes_plan_without_saving_profile(self):
  self.setup_calendar();self.client.events['calendar.familiekalender'][0]['location']='';self.owner.policy.data['transport_preference']='driving_first';before=deepcopy(self.owner.profile._data)
  with calendar_scope({'actor':'u','read':True,'write':False}):
   first=await self.router.meal_plan('45 minutes','s',self.state,{'status':'success','message':'Old reply'})
   self.assertFalse(first['meal_budget']['complete'])
   second=await self.router.handle('School','s',self.state)
   self.assertTrue(second['meal_budget']['complete']);self.assertEqual(second['meal_budget']['remaining_minutes'],-21)
   self.state['read_focus']['duration_minutes']=15
   third=await self.router.meal_plan('15 minutes','s',self.state,{'status':'success','message':'Old reply'})
   self.assertTrue(third['meal_budget']['complete']);self.assertEqual(third['meal_budget']['remaining_minutes'],9)
  self.assertEqual(before,self.owner.profile._data)
 async def test_venue_reply_cannot_cross_scope_or_source_change(self):
  self.setup_calendar();self.client.events['calendar.familiekalender'][0]['location']='';self.owner.policy.data['transport_preference']='driving_first'
  with calendar_scope({'actor':'u','read':True,'write':False}):
   await self.router.meal_plan('45 minutes','s',self.state,{'status':'success','message':'Old reply'})
   await self.router.handle('School','s',self.state)
   self.client.events['calendar.familiekalender'][0]['summary']='Replacement appointment'
   result=await self.router.meal_plan('45 minutes','s',self.state,{'status':'success','message':'Old reply'})
   self.assertFalse(result['meal_budget']['complete'])
   self.state['read_focus']['start']='2026-10-30';self.state['read_focus']['end']='2026-10-31'
   from jarvis.companion_routing import meal_draft
   self.assertIsNone(meal_draft(self.owner,self.state));self.assertNotIn('meal_venue_overrides',self.state)
 async def test_changed_event_notes_withdraw_temporary_venue(self):
  self.setup_calendar();self.client.events['calendar.familiekalender'][0]['location']='';self.owner.policy.data['transport_preference']='driving_first'
  with calendar_scope({'actor':'u','read':True,'write':False}):
   await self.router.meal_plan('45 minutes','s',self.state,{'status':'success','message':'Old reply'})
   await self.router.handle('School','s',self.state)
   self.client.events['calendar.familiekalender'][0]['description']='The rehearsal venue has changed.'
   r=await self.router.meal_plan('45 minutes','s',self.state,{'status':'success','message':'Old reply'})
   self.assertFalse(r['meal_budget']['complete']);self.assertIsNone(r['meal_budget']['to_meal_minutes'])
 async def test_coordinates_never_enter_model_or_reply_or_state(self):
  r=await self.check();data=json.dumps([self.provider.calls,r,self.state]);self.assertNotIn('62.12345678',data);self.assertNotIn('5.23456789',data)
 async def test_source_change_recalculates_instead_of_reusing_old_meal_budget(self):
  await self.check(15);self.client.events['calendar.familiekalender'][1]['start']='2026-10-29T16:30:00+01:00'
  with calendar_scope({'actor':'u','read':True,'write':False}):r=await self.router.meal_plan('15 minutes','s',self.state,{'status':'success','message':'Old reply'})
  self.assertEqual(r['meal_budget']['gap_minutes'],30);self.assertEqual(r['meal_budget']['remaining_minutes'],-21)

class AgentRouteTests(unittest.IsolatedAsyncioTestCase):
 setUp=agent_fixture.AgentTests.setUp
 say=agent_fixture.AgentTests.say
 async def test_literal_self_introduction_is_not_displaced_by_old_topic(self):
  r=await self.say('Hi Jarvis, this is Benny speaking',plan('identity','introduce',['benny'],'Benny'))
  self.assertIn('Hi Benny',r['message']);self.assertEqual(self.provider.calls[0]['response_schema']['properties']['tool']['enum'],['identity']);self.assertEqual(self.store.memories(),[])
 async def test_reported_introduction_does_not_narrow_identity_or_match_voice(self):
  await self.say('Linda said "Hi Jarvis, this is Benny speaking"',plan('general',answer='That is a reported statement.'))
  self.assertGreater(len(self.provider.calls[0]['response_schema']['properties']['tool']['enum']),1);self.assertIsNone(self.a.agent.sessions['chat']['introduced'])
 async def test_departure_preparation_stays_in_combined_home_calendar_weather_tool(self):
  self.container.connected_understanding=SimpleNamespace(handle=AsyncMock(return_value={'status':'success','message':'Fresh departure checks.'}))
  r=await self.say('What should we sort out before leaving tomorrow?',plan('connected'))
  self.assertEqual(r['agent_tool'],'connected');self.assertEqual(self.provider.calls[0]['response_schema']['properties']['tool']['enum'],['departure_brief'])
 async def test_failed_observation_read_returns_reply_instead_of_breaking_plans(self):
  self.a.observations=lambda *args:(_ for _ in ()).throw(RuntimeError('Fixture source failure'))
  r=await self.say('Can we fit dinner between Mia activities tomorrow?',plan('plans',members=['mia']))
  self.assertEqual(r['status'],'unavailable');self.assertNotIn('meal_budget',r)
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
