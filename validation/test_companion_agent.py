"""Qwen front-door tool dispatch; fake model/source boundaries only."""
import json,unittest
from copy import deepcopy
from types import SimpleNamespace
from jarvis.companion import Companion,CompanionPolicy
from jarvis.companion_agent import SCHEMA,DOMAINS,MEMORY_OPERATIONS,coded_backend_only
from jarvis.companion_store import CompanionStore
from jarvis.household_speaker import current_speaker,speaker_scope
from jarvis.calendar_context import calendar_scope,current_calendar_access
from test_planning_preparation_bundle import profile
from test_companion_coordinator import POLICY,NOW
from test_companion_memory import model_item

def plan(tool,operation='query',members=None,name_quote='',answer=''):
 return {'tool':tool,'operation':operation,'members':members or [],'name_quote':name_quote,'answer':answer}
class Provider:
 def __init__(self):self.plans=[];self.calls=[];self.fail=False
 def reason_local(self,**kw):
  self.calls.append(kw);schema=kw['response_schema'];data=json.loads(kw['input_messages'][0]['content'])
  if self.fail:return {'status':'unavailable'}
  if 'tool' in schema['properties']:
   self.current=self.plans.pop(0);reverse={v:k for k,v in DOMAINS.items()};domain=next((k for k,v in MEMORY_OPERATIONS.items() if v==self.current['operation']),None) if self.current['tool']=='memory' else reverse.get(self.current['tool'],self.current['tool']);out={'tool':domain,'members':self.current['members']}
  elif 'action' in schema['properties']:out={'action':self.current['operation'],'member':self.current['members'][0] if self.current['members'] else '', 'name_quote':self.current['name_quote']}
  elif 'operation' in schema['properties']:out={'operation':self.current['operation']}
  elif 'items' in schema['properties']:
   text=data['latest_user_statement'];names=[k for k,n in data['people'].items() if n in text];owner=names or ([data.get('conversation_speaker') or data.get('matched_speaker')] if data.get('conversation_speaker') or data.get('matched_speaker') else [])
   out={'items':[model_item(text,subjects=owner)]}
  elif 'memory_ids' in schema['properties']:out={'answer':'Benny prefers high fidelity music.','memory_ids':[data['memories'][0]['id']]}
  else:out={'answer':getattr(self,'current',{}).get('answer') or 'This source is a fictional household view.'}
  return {'status':'success','message':json.dumps(out)}
class AgentTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.profile=profile();self.profile._data['members'][0]['birth_date']={'status':'confirmed','value':'1985-09-27'}
  self.provider=Provider();self.store=CompanionStore(now=lambda:NOW);self.addCleanup(self.store.close);self.clock=[1];self.original_calls=[]
  self.container=SimpleNamespace(household_profile=self.profile,home_assistant=object(),travel_calendar_intelligence=None,local_reasoning_provider=self.provider,household_thinking=None)
  self.a=Companion(self.container,CompanionPolicy(None,{**deepcopy(POLICY),'conversation_mode':'qwen_tools'}),store=self.store,now=lambda:NOW,clock=lambda:self.clock[0])
 async def say(self,text,p,*,key='chat',source='phone',actor='user',write=True,read=True,speaker=None):
  self.provider.plans.append(p)
  async def original():
   self.original_calls.append((text,coded_backend_only.get(),current_calendar_access.get().write));return {'provider':'legacy-tool','status':'success','message':'Tool executed by fixture.'}
  with calendar_scope({'actor':actor,'read':read,'write':write} if actor else None),speaker_scope({'member_id':speaker,'basis':'voice_match' if speaker else 'unknown','conversation_id':key},self.profile,key):
   result=await self.a.process(original(),text,key,source)
   self.assertEqual(current_speaker.get().member_id,speaker)
   return result
 async def intro(self,**kw):return await self.say('Hi Jarvis, this is Benny speaking',plan('identity','introduce',['benny'],'Benny'),**kw)
 async def test_introduction_is_not_a_preference_and_does_not_call_old_biography(self):
  out=await self.intro();self.assertIn('Hi Benny',out['message']);self.assertNotIn('preference',out['message']);self.assertEqual(self.store.memories(),[]);self.assertEqual(self.original_calls,[])
 async def test_introduced_person_resolves_who_and_my_birthday_for_same_conversation(self):
  await self.intro();out=await self.say('Who am I?',plan('identity','identify'));self.assertIn('introduced yourself as Benny',out['message']);self.assertNotIn('voice',out['message'])
  out=await self.say('When is my birthday?',plan('profile','query',['benny']));self.assertIn('27 September',out['message'])
 async def test_compound_profile_question_retains_both_requested_facts(self):
  from unittest.mock import AsyncMock,patch
  from jarvis.household_reasoning import HouseholdReasoning
  self.profile._data['members'][0]['employment']={'status':'confirmed','role':'Test engineer','employer':'Fictional Works'}
  answer={'status':'success','message':'Benny is a Test engineer at Fictional Works. The office is upstairs.'}
  with patch.object(HouseholdReasoning,'handle',new=AsyncMock(return_value=answer)):
   out=await self.say("What is Benny's job and where is the office?",plan('profile','query',['benny']))
  self.assertIn('Test engineer',out['message']);self.assertIn('office is upstairs',out['message'])
 async def test_who_am_i_then_short_name_completes_identity(self):
  out=await self.say('Who am I?',plan('identity','identify'));self.assertEqual(out['status'],'clarification_required')
  out=await self.say('Benny',plan('identity','introduce',['benny'],'Benny'));self.assertIn('Hi Benny',out['message']);self.assertEqual(self.store.memories(),[])
 async def test_preference_name_reply_does_not_set_conversation_identity(self):
  out=await self.say('I prefer high fidelity music.',plan('memory','write'));self.assertIn('Whose',out['message'])
  out=await self.say('Benny',plan('memory','continue',['benny']));self.assertTrue(out['memory_saved'])
  out=await self.say('Who am I?',plan('identity','identify'));self.assertEqual(out['status'],'clarification_required')
 async def test_introduced_person_can_save_my_preference_without_another_identity_prompt(self):
  await self.intro();out=await self.say('I prefer high fidelity music.',plan('memory','write',['benny']));self.assertTrue(out['memory_saved'])
  row=self.store.memories()[0];self.assertEqual(row['subjects'],['benny']);self.assertEqual(row['source']['speaker_basis'],'self_reported_conversation')
 async def test_introductions_do_not_cross_chat_source_actor_revision_day_or_expiry(self):
  for kw in ({'key':'other'},{'source':'other'},{'actor':'other'}):
   await self.intro();out=await self.say('Who am I?',plan('identity','identify'),**kw);self.assertEqual(out['status'],'clarification_required')
  await self.intro();self.profile._data['revision']+=1;out=await self.say('Who am I?',plan('identity','identify'));self.assertEqual(out['status'],'clarification_required')
  await self.intro();self.clock[0]=2000;out=await self.say('Who am I?',plan('identity','identify'));self.assertEqual(out['status'],'clarification_required')
 async def test_voice_match_takes_precedence_and_is_not_rewritten_by_introduction(self):
  out=await self.say('I am Linda',plan('identity','introduce',['linda'],'Linda'),speaker='benny');self.assertEqual(out['status'],'clarification_required')
  out=await self.say('Who am I?',plan('identity','identify'),speaker='benny');self.assertIn('voice sounds like Benny',out['message'])
 async def test_negated_quoted_or_hypothetical_introduction_is_not_accepted_even_if_model_selects_it(self):
  for text in ("Linda said I am Benny",'Pretend I am Benny','I am not Benny'):
   out=await self.say(text,plan('identity','introduce',['benny'],'Benny'));self.assertNotIn('Hi Benny',out['message'])
  self.assertIsNone(self.a.agent.sessions['chat']['introduced'])
 async def test_clear_introduction_does_not_erase_memories_or_voice(self):
  await self.intro();await self.say('I prefer high fidelity music.',plan('memory','write'))
  await self.say('Forget who I am',plan('identity','clear'));out=await self.say('Who am I?',plan('identity','identify'));self.assertEqual(out['status'],'clarification_required');self.assertEqual(len(self.store.memories()),1)
 async def test_general_conversation_is_answered_by_qwen_without_any_coded_tool(self):
  out=await self.say('What is high fidelity audio?',plan('general','answer',answer='High fidelity aims to reproduce the original recording accurately.'))
  self.assertEqual(out['agent_planned_by'],'local_qwen');self.assertIn('reproduce',out['message']);self.assertEqual(self.original_calls,[]);self.assertEqual(len(self.provider.calls),2)
 async def test_home_and_research_delegate_original_request_with_authority_unchanged(self):
  for tool in ('home','research'):
   out=await self.say('Original request',plan(tool),write=False);self.assertEqual(out['provider'],'legacy-tool')
  self.assertEqual(self.original_calls,[('Original request',True,False)]*2)
 async def test_model_cannot_choose_python_or_supply_a_new_execution_endpoint(self):
  out=await self.say('Run something',plan('__import__'));self.assertEqual(out['status'],'unavailable');self.assertEqual(self.original_calls,[])
 async def test_model_cannot_claim_an_action_from_general_answer(self):
  out=await self.say('Hello',plan('general','answer',answer='I have booked a flight.'));self.assertEqual(out['status'],'unavailable')
 async def test_model_failure_is_not_hidden_by_legacy_routing(self):
  self.provider.fail=True;out=await self.say('Hi',plan('general','answer',answer='Hello'));self.assertEqual(out['status'],'unavailable');self.assertEqual(self.original_calls,[])
 async def test_memory_storage_still_requires_write_permission_after_introduction(self):
  await self.intro(write=False);out=await self.say('I prefer high fidelity music.',plan('memory','write'),write=False);self.assertEqual(self.store.memories(),[]);self.assertFalse(out.get('memory_saved'))
 async def test_confirmation_tool_gets_original_user_text_without_model_generated_confirmation(self):
  calls=[]
  async def handle(text,key,source,prior):calls.append(text);return {'message':'Review only','status':'clarification_required'}
  self.container.calendar_conversation=SimpleNamespace(handle=handle)
  out=await self.say('Find an appointment',plan('calendar'));self.assertEqual(calls,['Find an appointment']);self.assertEqual(out['message'],'Review only')
 async def test_no_calendar_read_does_not_grant_or_remove_home_tool_authority(self):
  await self.say('Read home state',plan('home'),read=False,write=False)
  self.assertEqual(self.original_calls,[('Read home state',True,False)])
  out=await self.say('What is Benny birthday?',plan('profile','query',['benny']),read=False,write=False);self.assertEqual(out['status'],'forbidden')
 async def test_actor_is_required_before_any_model_or_tool(self):
  out=await self.say('Hello',plan('general','answer',answer='Hello'),actor=None);self.assertEqual(out['status'],'forbidden');self.assertEqual(self.provider.calls,[])
 async def test_false_general_identity_is_not_accepted_as_household_evidence(self):
  out=await self.say('Who am I?',plan('general','answer',answer='You are Benny.'));self.assertNotIn('You are Benny',out['message']);self.assertIsNone(self.a.agent.sessions['chat']['introduced'])
 async def test_general_done_acknowledgement_is_not_a_confirmed_action(self):
  out=await self.say('Hello',plan('general','answer',answer='Done, the lights are off.'));self.assertEqual(out['status'],'unavailable')
if __name__=='__main__':unittest.main()
