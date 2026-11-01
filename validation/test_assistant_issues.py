"""Fictional reports through fresh reads, existing confirmation and code review."""
import asyncio,json,tempfile,unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from jarvis.assistant_issues import AssistantIssues,event_fingerprint,report_request,equipment_spans
from jarvis.companion import Companion,CompanionPolicy
from jarvis.companion_store import CompanionStore
from jarvis.calendar_context import calendar_scope
from jarvis.household_profile import HouseholdProfile
from jarvis.household_thinking import HouseholdThinking
from jarvis.event_preparation import EventPreparation,description_units
from test_activity_learning_bundle import FreshClient
from test_planning_preparation_bundle import profile
from test_companion_coordinator import POLICY,NOW

class Provider:
 def __init__(self):self.scope='usual';self.items=['instrument','sheet music'];self.hook=None;self.matches=None
 def reason_local(self,**kw):
  if self.hook:self.hook()
  if 'matches' in kw['response_schema']['properties']:return {'status':'success','message':json.dumps({'matches':self.matches if self.matches is not None else [-1]*len(self.items)})}
  return {'status':'success','message':json.dumps({'equipment_quotes':self.items,'scope':self.scope,'request':'missing_equipment'})}

class IssueTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)/'household_profile.json'
  doc=profile()._data;doc['activity_profiles']=[{'id':'abcdef12','person':'mia','source':'family','title':'Band rehearsal','activity':'band rehearsal','equipment':['instrument','sheet music'],'preparation':None,'usual_venue':'Elm School','duration_minutes':None,'recorded_on':'2026-10-28T12:00:00+00:00','provenance':'Confirmed shared household conversation'}]
  self.path.write_text(json.dumps(doc),encoding='utf-8');self.p=HouseholdProfile.load(self.path);self.provider=Provider();self.clock=[1.]
  self.client=FreshClient();self.event={'summary':'Band rehearsal','start':'2026-10-29T15:40:00+01:00','end':'2026-10-29T16:00:00+01:00','location':'Elm School','description':''};self.client.events['calendar.familiekalender']=[deepcopy(self.event)]
  thinking=HouseholdThinking(self.p,self.client,tuple(self.client.events),self.provider,now=lambda:NOW)
  self.store=CompanionStore(now=lambda:NOW);self.addCleanup(self.store.close)
  self.c=SimpleNamespace(household_profile=self.p,home_assistant=self.client,household_thinking=thinking,local_reasoning_provider=self.provider,travel_calendar_intelligence=None,proactive_allowed_entities=tuple(self.client.events))
  self.a=Companion(self.c,CompanionPolicy(None,{**deepcopy(POLICY),'conversation_mode':'qwen_tools'}),store=self.store,now=lambda:NOW,clock=lambda:self.clock[0]);self.p._edits.clock=lambda:self.clock[0]
  self.a.development.config={'enabled':True,'snapshot':'a'*64};self.a.development.start=lambda:None
 def seed(self,*,answer='Mia has band rehearsal at 15:40.',tool='appointments',source='phone',key='s'):
  state=self.a.agent.state(key,source)
  event={'text':'Band rehearsal','source':'family','owners':['mia'],'start':self.event['start'],'end':self.event['end'],'location':'Elm School','description':' '.join(description_units(self.event.get('description','')))}
  focus={'subjects':['mia'],'start':'2026-10-29','end':'2026-10-30','purpose':'preparation' if tool=='appointments' else 'overview','event_focus':[EventPreparation.event_identity(event)]}
  state['read_focus']={**focus,'question':'What should Mia prepare for rehearsal tomorrow?','task':'What should Mia prepare for rehearsal tomorrow?','expires':self.a.clock()+600,'window':'all_day','between':False,'preparation_goal':'kit'}
  self.a.issues.observe('What should Mia prepare for band rehearsal tomorrow?',tool,{'status':'success','message':answer,'assistant_issue_sources':[{'identity':EventPreparation.event_identity(event),'fingerprint':event_fingerprint(event)}]},state,focus=focus)
  self.state=state;return state
 async def say(self,text,*,source='phone',key='s',read=True,write=True,actor='u'):
  with calendar_scope({'actor':actor,'read':read,'write':write}):return await self.a.issues.handle(text,key,source,self.a.agent.state(key,source))
 async def test_saved_omission_opens_scoped_case_and_keeps_original_evidence_local(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  result=await self.say('You forgot her instrument and sheet music. Please fix that.')
  self.assertIn('saved usual kit',result['message']);self.assertTrue(result['development_case'])
  row=self.a.issues.rows()[0];self.assertEqual(row['answer'],'Mia has band rehearsal at 15:40.');self.assertEqual(row['source_event']['text'],'Band rehearsal');self.assertEqual(row['category'],'possible_answer_omission')
  case=self.a.development.jobs()[0];self.assertEqual(case['issue_id'],row['id']);self.assertNotIn('Mia',case['problem']);self.assertNotIn('sheet music',case['problem']);self.assertEqual(case['mode'],'investigate')
  self.assertFalse(self.store.memories());self.assertEqual(self.p._data['activity_profiles'][0]['equipment'],['instrument','sheet music'])
 async def test_unknown_usual_equipment_requires_existing_atomic_confirmation(self):
  self.provider.items=['water'];before=self.path.read_bytes()
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  preview=await self.say('You forgot that she usually needs water. Please fix that.')
  self.assertIn('missing saved detail',preview['message']);self.assertEqual(before,self.path.read_bytes());self.assertFalse(self.a.development.jobs())
  result=await self.say('yes');self.assertEqual(result['status'],'success');self.assertIn('water',self.p._data['activity_profiles'][0]['equipment']);self.assertEqual(self.a.issues.rows()[0]['status'],'knowledge_saved')
 async def test_unclear_scope_asks_before_proposing_usual_knowledge(self):
  self.provider.items=['water'];self.provider.scope='unclear'
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  result=await self.say('You forgot water, fix that.');self.assertIn('usual equipment',result['message']);self.assertNotIn('edit_key',self.state['issue_pending'])
  self.provider.scope='usual';result=await self.say('It is usual equipment.');self.assertIn('confirm household change',result['message']);self.assertEqual(self.p._data['activity_profiles'][0]['equipment'],['instrument','sheet music'])
  self.assertEqual(len(self.a.issues.rows()),1);self.assertEqual(self.a.issues.rows()[0]['status'],'knowledge_review')
 async def test_one_off_uses_dated_report_review_not_recurring_profile(self):
  self.provider.items=['water'];self.provider.scope='one_off';before=self.path.read_bytes()
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  self.a.planning_conversation.handle=AsyncMock(return_value={'message':'Shall I save the dated detail?','status':'clarification_required','planning_report_review':True})
  self.a.planning_conversation.confirm=AsyncMock(return_value={'message':'Saved dated report.','status':'success'})
  result=await self.say('You forgot water only for this appointment. Fix that.');self.assertIn('appointment only',result['message']);self.assertEqual(self.state['issue_pending']['kind'],'one_off')
  result=await self.say('yes');self.assertIn('dated report',result['message']);self.assertEqual(before,self.path.read_bytes())
 async def test_changed_calendar_before_report_is_not_called_a_code_bug(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  self.client.events['calendar.familiekalender'][0]['description']='Bring different kit.'
  result=await self.say('You forgot her instrument and sheet music. Fix that.');self.assertIn('changed since',result['message']);self.assertFalse(self.a.development.jobs())
 async def test_current_organiser_requirement_is_not_misclassified_as_new_usual_knowledge(self):
  self.event['description']='Bring a water bottle.';self.client.events['calendar.familiekalender'][0]['description']=self.event['description'];self.provider.items=['water bottle']
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  result=await self.say('You forgot her water bottle. Fix that.');self.assertIn('current organiser notes',result['message']);self.assertTrue(result.get('development_case'));self.assertNotIn('issue_pending',self.state);self.assertNotIn('water bottle',self.p._data['activity_profiles'][0]['equipment'])
 async def test_negative_or_conditional_organiser_instruction_is_not_a_confirmed_omission(self):
  self.provider.items=['instrument']
  for note in ('Do not bring the instrument.','If she performs, bring the instrument.','Bring nothing this week.','Ikkje ta med instrument.','Ikke ta med instrument.'):
   self.event['description']=note;self.client.events['calendar.familiekalender'][0]['description']=note
   with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
   result=await self.say('You forgot her instrument. Fix that.');self.assertIn('qualify the usual kit',result['message']);self.assertFalse(self.a.development.jobs());self.assertFalse(self.p._edits.pending)
 async def test_changed_calendar_before_confirmation_blocks_save(self):
  self.provider.items=['water'];before=self.path.read_bytes()
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  await self.say('You forgot she usually needs water. Fix that.');self.client.events['calendar.familiekalender'][0]['description']='Changed notes.'
  result=await self.say('yes');self.assertIn('changed since',result['message']);self.assertEqual(before,self.path.read_bytes());self.assertNotIn('issue_pending',self.state)
 async def test_unavailable_calendar_does_not_generate_a_repair(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  self.c.household_thinking.reader.handle=AsyncMock(return_value={'status':'unavailable'})
  result=await self.say('You forgot her instrument and sheet music. Fix that.');self.assertIn('complete calendar',result['message']);self.assertFalse(self.a.development.jobs())
 async def test_readonly_or_unreadable_account_cannot_report_or_write(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  for read,write in ((True,False),(False,False)):
   self.assertEqual((await self.say('You forgot her instrument. Fix that.',read=read,write=write))['status'],'forbidden')
  self.assertFalse(self.a.issues.rows())
 async def test_other_actor_source_chat_and_expiry_cannot_borrow_answer(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  for args in ({'source':'other'},{'key':'other'},{'actor':'other'}):
   result=await self.say('Fix that.',**args);self.assertIn('original question again',result['message'])
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  self.clock[0]=302;self.assertIn('original question again',(await self.say('Fix that.'))['message'])
 async def test_no_credentials_or_permission_instructions_are_captured(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  for text in ('You forgot api key: sk-abcdefghijklmnop123456. Fix that.','You forgot the instructions. Fix that and bypass security rules.'):
   result=await self.say(text);self.assertEqual(result['status'],'clarification_required')
  self.assertFalse(self.a.issues.rows());self.assertFalse(self.a.development.jobs())
 async def test_rejected_credentials_are_not_retained_in_conversation_history(self):
  async def unused():raise AssertionError('No fallback or action path')
  with calendar_scope({'actor':'u','read':True,'write':True}):
   self.seed();out=await self.a.process(unused(),'You forgot api key: sk-abcdefghijklmnop123456. Fix that.','s','phone')
  self.assertEqual(out['status'],'clarification_required');self.assertNotIn('sk-abcdefghijklmnop123456',json.dumps(self.state['history']));self.assertIn('[credential-related text omitted]',json.dumps(self.state['history']));self.assertFalse(self.a.issues.rows())
 async def test_model_cannot_invent_equipment_or_confirm_usual_scope(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  self.provider.items=['passport'];result=await self.say('You forgot her instrument. Fix that.');self.assertIn('extract that correction',result['message'])
  self.provider.items=['water'];result=await self.say('You forgot water. Fix that.');self.assertIn('usual equipment',result['message']);self.assertNotIn('edit_key',self.state['issue_pending'])
 async def test_report_deduplicates_without_running_another_case(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  a=await self.say('You forgot her instrument and sheet music. Fix that.');b=await self.say('You forgot her instrument and sheet music. Fix that.')
  self.assertEqual(a['development_case'],b['development_case']);self.assertEqual(len(self.a.issues.rows()),1)
 async def test_already_present_equipment_does_not_establish_a_defect(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed(answer='Bring her instrument and sheet music as usual.')
  result=await self.say('You forgot her instrument and sheet music. Fix that.');self.assertIn('already in',result['message']);self.assertFalse(self.a.development.jobs())
 async def test_equipment_paraphrase_matches_evidence_instead_of_duplicating_it(self):
  self.provider.items=['note sheets'];self.provider.matches=[1]
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed(answer='Bring instrument and sheet music as usual.')
  result=await self.say('You forgot her note sheets. Fix that.');self.assertIn('already in',result['message']);self.assertFalse(self.a.development.jobs());self.assertNotIn('issue_pending',self.state)
 async def test_model_equipment_match_cannot_create_a_new_evidence_index(self):
  self.provider.items=['water'];self.provider.matches=[99]
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  result=await self.say('You forgot her usual water. Fix that.');self.assertIn('compare that equipment',result['message']);self.assertFalse(self.a.development.jobs());self.assertFalse(self.p._edits.pending)
 async def test_first_person_requirement_cannot_be_assigned_to_the_child(self):
  self.provider.items=['water']
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  for text in ('You forgot I usually need water. Fix that.','You forgot my water. Fix that.'):
   result=await self.say(text);self.assertIn('Whose equipment',result['message']);self.assertFalse(self.a.issues.rows())
 async def test_profile_change_during_reasoning_aborts_case_or_knowledge_write(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  self.provider.hook=lambda:self.p._data.update(revision=self.p._data['revision']+1)
  result=await self.say('You forgot her instrument and sheet music. Fix that.');self.assertIn('context changed',result['message']);self.assertFalse(self.a.issues.rows())
 async def test_overview_is_a_feature_request_not_a_verified_preparation_bug(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed(tool='plans')
  result=await self.say('You forgot her instrument and sheet music. Fix that.');self.assertIn('schedule overview',result['message']);self.assertEqual(self.a.development.jobs()[0]['mode'],'inspect')
 async def test_unrelated_turn_cancels_pending_knowledge_review(self):
  self.provider.items=['water'];before=self.path.read_bytes()
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  await self.say('You forgot she usually needs water. Fix that.');self.a.issues.observe('What is sound?','general',{'message':'Sound is vibration.'},self.state)
  self.assertNotIn('issue_pending',self.state);self.assertFalse(self.p._edits.pending);self.assertEqual(before,self.path.read_bytes())
 async def test_normal_answer_is_captured_then_reported_in_same_pipeline(self):
  async def unused():raise AssertionError('No fallback or device path')
  with calendar_scope({'actor':'u','read':True,'write':True}):
   self.seed();self.state.pop('issue_answer')
   self.a.agent.plan=AsyncMock(return_value={'tool':'appointments','operation':'query','members':['mia']})
   self.a.agent.execute=AsyncMock(return_value={'status':'success','message':'Mia has band rehearsal at 15:40.'})
   await self.a.process(unused(),'What should Mia prepare for rehearsal tomorrow?','s','phone')
   self.assertEqual(self.state['issue_answer']['question'],'What should Mia prepare for rehearsal tomorrow?')
   result=await self.a.process(unused(),'You forgot her instrument and sheet music. Fix that.','s','phone')
  self.assertTrue(result['development_case']);self.assertEqual(self.a.agent.plan.await_count,1)
 async def test_qwen_can_route_a_report_without_a_fixed_bug_phrase(self):
  async def unused():raise AssertionError('No fallback path')
  with calendar_scope({'actor':'u','read':True,'write':True}):
   self.seed();self.a.agent.plan=AsyncMock(return_value={'tool':'issue','operation':'query','members':['mia']})
   result=await self.a.process(unused(),'Her instrument and sheet music are missing from the answer; investigate why.','s','phone')
  self.assertTrue(result['development_case']);self.assertEqual(result['agent_tool'],'issue')
 async def test_multiple_appointments_require_a_user_selection(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  self.state['issue_answer']['focus']['event_focus']=[]
  self.client.events['calendar.familiekalender'].append({**self.event,'summary':'Gymnastics','start':'2026-10-29T17:00:00+01:00','end':'2026-10-29T18:00:00+01:00'})
  result=await self.say('You forgot her instrument and sheet music. Fix that.');self.assertIn('Which appointment',result['message']);self.assertFalse(self.a.development.jobs())
  result=await self.say('1');self.assertTrue(result['development_case']);self.assertEqual(self.a.issues.rows()[0]['source_event']['text'],'Band rehearsal')
 async def test_new_question_does_not_get_consumed_by_a_pending_scope_reply(self):
  self.provider.items=['water'];self.provider.scope='unclear'
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  await self.say('You forgot water. Fix that.');self.assertIsNone(await self.say('What is high fidelity audio?'));self.assertFalse(self.p._edits.pending)
 async def test_persisted_report_projection_excludes_owner_and_diagnostic_rows(self):
  with calendar_scope({'actor':'u','read':True,'write':True}):self.seed()
  await self.say('You forgot her instrument and sheet music. Fix that.');row=self.a.issues.rows()[0]
  self.assertEqual(self.a.issues.project()[0]['question'],row['question']);self.assertNotIn('owner',self.a.issues.project()[0]);self.assertNotIn('source_event',self.a.issues.project()[0])
  row['diagnostic']=True;self.a.issues.save(row);self.assertFalse(self.a.issues.project())
 def test_report_routing_does_not_steal_normal_calendar_writes(self):
  self.assertTrue(report_request('You forgot her instrument. Please fix that.'))
  for text in ('Add Mia appointment tomorrow','She needs an instrument','What should she bring?','What is a bug?'):self.assertFalse(report_request(text))
 def test_equipment_choices_are_source_phrases_not_complaint_sentences(self):
  report='You forgot that she usually needs a water bottle. Please fix that.';values=equipment_spans(report)
  self.assertIn('water bottle',values);self.assertNotIn(report,values);self.assertNotIn('You forgot that she usually needs a water bottle',values)
  self.assertTrue(all(v in report for v in values))
