"""Fictional activity learning, persistence and route planning. No real writes."""
import asyncio,json,tempfile,unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from jarvis.activity_conversation import ActivityConversation
from jarvis.household_profile import HouseholdProfile
from jarvis.household_thinking import HouseholdThinking
from jarvis.companion import Companion,CompanionPolicy
from jarvis.companion_store import CompanionStore
from jarvis.companion_routing import CompanionRouting
from jarvis.calendar_context import calendar_scope
from test_companion_coordinator import POLICY,NOW
from test_planning_preparation_bundle import profile,Client
from test_companion_routing import Transport

class Provider:
 def __init__(self):self.calls=[];self.change={};self.target='Band rehearsal'
 def reason_local(self,**kw):
  self.calls.append(kw);s=kw['response_schema']['properties'];data=json.loads(kw['input_messages'][0]['content'])
  if 'target' in s:
   target=next((v['key'] for v in data['candidates'] if v['title']==self.target),'')
   f={'intent':'update','read_field':'all','target':target,'scope':'usual','meaning_quote':'band rehearsal','venue_operation':'set','venue_quote':'Elm School','equipment_operation':'append','equipment_quotes':['instrument','sheet music'],'preparation_operation':'keep','preparation_quote':'','travel_operation':'set','travel_quote':'two minutes','question':''};f.update(self.change)
  elif 'meal_location' in s:f={'meal_location':'home'}
  else:raise ValueError('Unexpected fictional model call')
  return {'status':'success','message':json.dumps(f)}
class FreshClient(Client):
 async def get_home_location(self):return {'latitude':62.12345678,'longitude':5.23456789}
 async def get_household_today(self,*a,**kw):
  r=await super().get_household_today(*a,**kw);r['planning']['generated_on']='2026-10-28';return r

class LearningTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)/'household_profile.json';self.path.write_text(json.dumps(profile()._data));self.p=HouseholdProfile.load(self.path);self.provider=Provider();self.c=FreshClient();self.clock=[1.]
  self.c.events['calendar.familiekalender']=[{'summary':'Band rehearsal','start':'2026-10-29T15:40:00+01:00','end':'2026-10-29T16:00:00+01:00','location':''},{'summary':'Gruppe 1','start':'2026-10-29T17:00:00+01:00','end':'2026-10-29T18:30:00+01:00','location':'Sports Hall'}]
  self.store=CompanionStore(now=lambda:NOW);self.addCleanup(self.store.close);self.container=SimpleNamespace(household_profile=self.p,home_assistant=self.c,household_thinking=HouseholdThinking(self.p,self.c,tuple(self.c.events),self.provider,now=lambda:NOW),local_reasoning_provider=self.provider,travel_calendar_intelligence=None)
  policy={**deepcopy(POLICY),'conversation_mode':'qwen_tools','interactive_home_routing':{'enabled':True,'approval_source':'Fictional approval','recorded_on':'2026-10-28'}}
  self.a=Companion(self.container,CompanionPolicy(None,policy),store=self.store,now=lambda:NOW,clock=lambda:self.clock[0]);self.knowledge=ActivityConversation(self.a);self.state={};self.p._edits.clock=lambda:self.clock[0]
  self.text="Mia's band rehearsal is at Elm School. She needs instrument and sheet music. It is two minutes from home."
 async def say(self,text=None,*,key='s',state=None,write=True,read=True):
  with calendar_scope({'actor':'fixture','read':read,'write':write}):return await self.knowledge.handle(text or self.text,key,'fixture',self.state if state is None else state,['mia'])
 async def save(self):
  r=await self.say();self.assertEqual(r['status'],'clarification_required',r)
  r=await self.say('yes');self.assertEqual(r['status'],'success',r);return self.p._data['activity_profiles'][0]
 async def test_pronoun_profile_topic_cannot_switch_established_member(self):
  provider=SimpleNamespace(reason_local=lambda **kw:{'status':'success','message':json.dumps({'tool':'household_facts','members':['linda']})})
  self.a.agent.provider=provider
  with calendar_scope({'actor':'fixture','read':True,'write':True}):
   state=self.a.agent.state('subject','fixture');state['history']=[{'role':'user','text':'What does Mia have tomorrow?'},{'role':'assistant','text':'Mia has rehearsal.'}]
   with self.assertRaises(ValueError):await self.a.agent.plan('And her birthday?','subject','fixture',state)
 async def test_explicit_new_activity_command_keeps_typed_review_route(self):
  captured=[]
  def decide(**kw):
   captured.append(kw);return {'status':'success','message':json.dumps({'tool':'profile_editor','members':['mia']})}
  self.a.agent.provider=SimpleNamespace(reason_local=decide)
  for tail in ('means "band rehearsal"','usually needs "instrument, sheet music"','usually takes place at "Elm School"'):
   text='Remember Mia'+chr(39)+'s activity "New rehearsal" in the family calendar '+tail
   with calendar_scope({'actor':'fixture','read':True,'write':True}):
    state=self.a.agent.state('typed','fixture');result=await self.a.agent.plan(text,'typed','fixture',state)
   self.assertEqual(result['tool'],'household_update');self.assertEqual(captured[-1]['response_schema']['properties']['tool']['enum'],['profile_editor'])
  self.assertEqual(self.p._data.get('activity_profiles',[]),[])
 def test_tool_prompt_fits_actual_adapter_system_budget(self):
  from jarvis.companion_agent import PROMPT
  from jarvis.providers.local_first_provider import LocalReasoningPolicy
  self.assertLessEqual(len(PROMPT),LocalReasoningPolicy().maximum_input_characters//2)
 async def test_propose_atomic_confirm_reload_and_new_conversation(self):
  before=self.path.read_bytes();r=await self.say();self.assertEqual(self.path.read_bytes(),before);self.assertIn('usual venue Elm School',r['message']);self.assertNotIn('activity_profiles',self.p._data)
  await self.say('yes');new=HouseholdProfile.load(self.path);r=new._data['activity_profiles'][0]
  self.assertEqual(r['usual_venue'],'Elm School');self.assertEqual(r['equipment'],['instrument','sheet music']);self.assertEqual(r['home_journey']['minutes'],2);self.assertEqual(r['home_journey']['venue'],'Elm School');self.assertEqual(r['learning_quote'],self.text)
  self.assertTrue((self.path.parent/(self.path.name+'.history')).is_dir());self.assertFalse(self.store.memories());self.assertEqual(self.store.job_counts(),{})
 async def test_saved_details_are_exact_scoped_for_prep_and_routing(self):
  row=await self.save();from jarvis.household_activities import match,notes
  f={'text':'Band rehearsal','owners':['mia'],'source':'family','description_units':[],'location':'','all_day':False,'id':'E1','owner_name':'Mia'}
  self.assertEqual(match(self.p._data,f)['id'],row['id']);f['activity_profile']=row
  prose=notes([f],'requirements')[0]['text'];self.assertIn('instrument',prose);self.assertIn('Elm School',prose)
  for owners,source,title in ((['emrik'],'family','Band rehearsal'),(['mia'],'work','Band rehearsal'),(['mia'],'family','Other rehearsal')):
   self.assertIsNone(match(self.p._data,{**f,'owners':owners,'source':source,'text':title}))
 async def test_new_venue_clears_old_home_estimate_and_keeps_unrelated_fields(self):
  await self.save();self.provider.change={'meaning_quote':'','venue_quote':'Oak Hall','equipment_operation':'keep','equipment_quotes':[],'travel_operation':'keep','travel_quote':''}
  await self.say("Mia's band rehearsal has moved to Oak Hall");await self.say('yes');r=self.p._data['activity_profiles'][0]
  self.assertEqual(r['usual_venue'],'Oak Hall');self.assertNotIn('home_journey',r);self.assertEqual(r['equipment'],['instrument','sheet music'])
 async def test_update_travel_and_venue_in_one_confirmation(self):
  await self.save();self.provider.change={'meaning_quote':'','venue_quote':'Oak Hall','equipment_operation':'keep','equipment_quotes':[],'travel_quote':'five minutes'}
  await self.say("Mia's band rehearsal is now at Oak Hall, five minutes from home");await self.say('yes');r=self.p._data['activity_profiles'][0]
  self.assertEqual(r['home_journey']['minutes'],5);self.assertEqual(r['home_journey']['venue'],'Oak Hall')
 async def test_equipment_removal_is_reviewed(self):
  await self.save();self.provider.change={'meaning_quote':'','venue_operation':'keep','venue_quote':'','equipment_operation':'remove','equipment_quotes':['sheet music'],'travel_operation':'keep','travel_quote':''}
  before=self.path.read_bytes();await self.say("Mia's band rehearsal no longer needs sheet music");self.assertEqual(before,self.path.read_bytes());await self.say('yes');self.assertEqual(self.p._data['activity_profiles'][0]['equipment'],['instrument'])
 async def test_unstated_model_venue_or_kit_cannot_be_saved(self):
  for change in ({'venue_quote':'Invented Hall'},{'equipment_quotes':['invented bag']},{'travel_quote':'seven minutes'}):
   self.provider.change=change;r=await self.say();self.assertEqual(r['status'],'clarification_required');self.assertFalse(self.p._edits.pending);self.assertNotIn('activity_profiles',self.p._data)
 async def test_one_off_detail_is_not_a_new_usual(self):
  self.provider.change={'scope':'one_off'};r=await self.say("Mia's band rehearsal is at Elm School just tomorrow");self.assertIn('one appointment',r['message']);self.assertFalse(self.p._edits.pending)
 async def test_unknown_person_asks_without_guessing_mia(self):
  r=await self.say('Band rehearsal is at Elm School');self.assertIn('Whose',r['message']);self.assertFalse(self.provider.calls)
 async def test_unknown_self_reference_does_not_guess_shared_login(self):
  r=await self.say('My band rehearsal is at Elm School');self.assertIn('Whose',r['message']);self.assertFalse(self.provider.calls)
 async def test_write_and_read_permissions_are_enforced(self):
  for write,read in ((False,True),(False,False)):
   r=await self.say(write=write,read=read);self.assertEqual(r['status'],'forbidden');self.assertFalse(self.p._edits.pending)
 async def test_cancel_expiry_wrong_conversation_and_changed_file(self):
  await self.say();await self.say('cancel household change');self.assertFalse(self.p._edits.pending);self.assertNotIn('activity_profiles',self.p._data)
  await self.say();r=await self.say('yes',key='other');self.assertNotEqual(r['status'],'success');self.assertNotIn('activity_profiles',self.p._data)
  self.clock[0]=400;r=await self.say('confirm household change');self.assertNotEqual(r['status'],'success');self.assertNotIn('activity_profiles',self.p._data)
  await self.say();self.path.write_text(self.path.read_text()+' ');r=await self.say('yes');self.assertIn('changed since',r['message']);self.assertNotIn('activity_profiles',self.p._data)
 async def test_undo_restores_previous_profile(self):
  await self.save()
  with calendar_scope({'actor':'fixture','read':True,'write':True}):
   self.p.edit_request('undo last household change','undo');r=self.p.edit_request('confirm household change','undo')
  self.assertEqual(r['status'],'success');self.assertFalse(self.p._data.get('activity_profiles'))
 async def test_fresh_read_shows_saved_detail_and_clears_old_review(self):
  await self.save();self.provider.change={'intent':'read','read_field':'venue'}
  r=await self.say("Where does Mia's band rehearsal usually take place?",key='new',state={});self.assertIn('usually takes place at Elm School',r['message'])
  self.provider.change={'meaning_quote':'','venue_quote':'Oak Hall','equipment_operation':'keep','travel_operation':'keep','travel_quote':''}
  await self.say("Mia's band rehearsal has moved to Oak Hall");self.assertTrue(self.p._edits.pending)
  self.provider.change={'intent':'read','read_field':'venue'};await self.say("Where does Mia's band rehearsal usually take place?");self.assertFalse(self.p._edits.pending)
  r=await self.say('yes');self.assertNotIn('Saved household change',r['message'])
 async def test_activity_focus_survives_own_confirm_for_pronoun_correction(self):
  await self.save();self.provider.change={'meaning_quote':'','venue_operation':'keep','venue_quote':'','equipment_operation':'append','equipment_quotes':['small towel'],'travel_operation':'keep','travel_quote':''}
  r=await self.say('She also needs a small towel');self.assertEqual(r['status'],'clarification_required');await self.say('yes');self.assertIn('small towel',self.p._data['activity_profiles'][0]['equipment'])
 async def test_repeat_does_not_write_or_leave_review(self):
  await self.save();before=self.path.read_bytes();r=await self.say();self.assertIn('already saved',r['message']);self.assertEqual(before,self.path.read_bytes());self.assertFalse(self.p._edits.pending)
 async def test_keep_fields_do_not_apply_model_copies_of_old_quotations(self):
  await self.save();self.provider.change={'meaning_quote':'made up type','venue_quote':'Oak Hall','equipment_operation':'keep','equipment_quotes':['invented kit'],'travel_operation':'keep','travel_quote':''}
  r=await self.say("Mia's band rehearsal has moved to Oak Hall");self.assertEqual(r['status'],'clarification_required');self.assertIn('clear the old home journey',r['message']);await self.say('yes')
  row=self.p._data['activity_profiles'][0];self.assertEqual(row['activity'],'band rehearsal');self.assertEqual(row['equipment'],['instrument','sheet music'])
 async def test_current_concrete_calendar_venue_wins_over_saved_usual_time(self):
  await self.save();router=CompanionRouting(self.a,transport=Transport())
  f={'text':'Band rehearsal','source':'family','owners':['mia'],'description':'','location':'Different Hall'}
  v=router.venue(f);self.assertEqual(v['current_venue'],'Different Hall');self.assertIsNone(v['usual_home_journey'])
  f['location']='Elm School';self.assertEqual(router.venue(f)['usual_home_journey']['minutes'],2)
 async def test_usual_estimate_fallback_is_used_after_geocoder_failure(self):
  await self.save();transport=Transport();transport.place=lambda name:None if name=='Elm School' else {'label':'Sports Hall','coordinates':{'latitude':62.34,'longitude':5.85}};transport.minutes=9
  router=CompanionRouting(self.a,transport=transport);self.state['read_focus']={'subjects':['mia'],'start':'2026-10-29','end':'2026-10-30','purpose':'availability','between':True,'duration_minutes':45,'task':'dinner','expires':self.clock[0]+300}
  with calendar_scope({'actor':'fixture','read':True,'write':False}):r=await router.meal_plan('45 minutes','s',self.state,{'status':'success','message':'Old'})
  self.assertEqual(r['meal_budget']['remaining_minutes'],4);self.assertEqual(r['meal_budget']['estimate_sources'],['saved_user_estimate','Entur']);self.assertIn('saved usual 2-minute estimate',r['message'])
 async def test_fresh_route_precedes_saved_usual_estimate(self):
  await self.save();transport=Transport();transport.minutes=9;router=CompanionRouting(self.a,transport=transport);self.state['read_focus']={'subjects':['mia'],'start':'2026-10-29','end':'2026-10-30','purpose':'availability','between':True,'duration_minutes':45,'task':'dinner','expires':self.clock[0]+300}
  with calendar_scope({'actor':'fixture','read':True,'write':False}):r=await router.meal_plan('45 minutes','s',self.state,{'status':'success','message':'Old'})
  self.assertEqual(r['meal_budget']['estimate_sources'],['Entur','Entur']);self.assertEqual(r['meal_budget']['remaining_minutes'],-3)

class DepartureTests(unittest.IsolatedAsyncioTestCase):
 setUp=LearningTests.setUp
 say=LearningTests.say
 save=LearningTests.save
 # Only the departure-specific tests below are loaded by the suite builder.
 async def scenario(self,*,include=False,buffer='',route_ok=True,current=''):
  await self.save();f={'id':'E1','kind':'appointment','owners':['mia'],'source':'family','text':'Band rehearsal','start':'2026-10-29T15:40:00+01:00','end':'2026-10-29T16:00:00+01:00','local_start':'15:40','local_end':'16:00','date':'2026-10-29','all_day':False,'location':current,'description':''}
  from jarvis.event_preparation import EventPreparation
  resolved={'subjects':('mia',),'start':'2026-10-29','end':'2026-10-30','purpose':'preparation','question':'When should Mia leave?'}
  self.a.agent.reads.resolve=AsyncMock(return_value=resolved)
  prep=SimpleNamespace(handle=AsyncMock(return_value={'status':'success','message':'Bring the instrument and sheet music.'}),sessions={'s':{'source_focus':[EventPreparation.event_identity(f)]}});self.container.event_preparation=prep
  self.container.household_thinking.reader.handle=AsyncMock(return_value={'evidence':{'facts':[f],'source_failures':[],'truncated':False}})
  transport=Transport();transport.minutes=9
  if not route_ok:transport.place=lambda name:None
  self.container.companion_routing=CompanionRouting(self.a,transport=transport)
  from jarvis.activity_departure import departure
  with calendar_scope({'actor':'fixture','read':True,'write':False}),patch('jarvis.activity_departure.local_json',new=AsyncMock(return_value={'include_preparation':include,'arrival_allowance_quote':buffer})):
   return await departure(self.a,'What should Mia prepare and when should we leave tomorrow, arrive 5 minutes early?' if buffer else 'When should we leave for Mia band rehearsal tomorrow?','s','fixture',self.state,['mia'])
 async def test_departure_checked_route_and_labelled_default_buffer(self):
  r=await self.scenario();self.assertEqual(r['departure']['leave_home_at'],'2026-10-29T15:21:00+01:00');self.assertEqual(r['departure']['basis'],'Entur');self.assertIn('planning allowance',r['message'])
 async def test_departure_saved_estimate_and_preparation(self):
  r=await self.scenario(route_ok=False,include=True);self.assertEqual(r['departure']['leave_home_at'],'2026-10-29T15:28:00+01:00');self.assertEqual(r['departure']['basis'],'saved_user_estimate');self.assertIn('instrument',r['message']);self.assertIn('saved usual',r['message'])
 async def test_explicit_arrival_allowance_is_calculated(self):
  r=await self.scenario(buffer='5 minutes');self.assertEqual(r['departure']['leave_home_at'],'2026-10-29T15:26:00+01:00');self.assertEqual(r['departure']['arrival_allowance_minutes'],5)
 async def test_changed_current_venue_cannot_fall_back_to_old_usual(self):
  r=await self.scenario(route_ok=False,current='Different Hall');self.assertNotIn('departure',r);self.assertEqual(r['status'],'clarification_required')

if __name__=='__main__':unittest.main()
