"""Fictional weeks-old recall, corrections, priorities and invalidation."""
import asyncio,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from datetime import timedelta
from copy import deepcopy
from unittest.mock import patch
from jarvis.companion_store import CompanionStore
from jarvis.companion_memory import search_memories,answer_memory
from jarvis.assistant_priorities import compose,next_steps,priority_key
from test_companion_memory import NOW,store_record,context,record,model_item
import test_planning_followthrough as followtests

class RetrievalTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):self.s=CompanionStore(now=lambda:NOW);self.addCleanup(self.s.close)
 async def test_semantic_search_reaches_old_detail_beyond_eight_recent_owner_matches(self):
  old=store_record(self.s,'Benny values high fidelity when listening to music.',topic='sound quality',tags=['music','audio'])
  for n in range(24):store_record(self.s,'Benny likes fictional item '+str(n)+'.',topic='unrelated',tags=['unrelated'])
  provider=SimpleNamespace(reason_local=lambda **k:{'status':'success','message':json.dumps({'terms':['audio','sound quality','music'],'history':False})})
  rows=await search_memories(provider,self.s,'What matters to Benny about sound reproduction?',['benny'])
  self.assertEqual(rows[0]['id'],old);self.assertLessEqual(len(rows),8)
 async def test_expansion_is_not_evidence_and_is_never_saved(self):
  store_record(self.s,'Benny likes music.',topic='music',tags=['music'])
  before=self.s.db.iterdump();before='\n'.join(before)
  provider=SimpleNamespace(reason_local=lambda **k:{'status':'success','message':json.dumps({'terms':['imaginary audio gear'],'history':False})})
  await search_memories(provider,self.s,'What does Benny like?',['benny'])
  self.assertEqual(before,'\n'.join(self.s.db.iterdump()))
 async def test_malformed_or_slow_expansion_keeps_lexical_retrieval(self):
  identifier=store_record(self.s,'Mia likes music.',subjects=['mia'],topic='music',tags=['music'])
  for output in ({'terms':['password is example'],'history':False},{'terms':'music','history':False},{}):
   provider=SimpleNamespace(reason_local=lambda **k:{'status':'success','message':json.dumps(output)})
   self.assertEqual((await search_memories(provider,self.s,'Mia music',['mia']))[0]['id'],identifier)
 async def test_history_must_be_explicit_and_is_labelled_in_answer(self):
  identifier=store_record(self.s,'Benny prefers driving to the airport.')
  self.s.db.execute("update assistant_memories set status='superseded' where id=?",(identifier,));self.s.db.commit()
  provider=SimpleNamespace(reason_local=lambda **k:{'status':'success','message':json.dumps({'terms':['airport'],'history':True})})
  self.assertEqual(await search_memories(provider,self.s,'What transport does Benny prefer?',['benny']),[])
  rows=await search_memories(provider,self.s,'What did Benny previously prefer for airport transport?',['benny']);self.assertEqual(rows[0]['id'],identifier)
  bad=SimpleNamespace(reason_local=lambda **k:{'status':'success','message':json.dumps({'answer':'Benny prefers driving to the airport.','memory_ids':[identifier]})})
  with self.assertRaises(ValueError):await answer_memory(bad,'What did he previously prefer?',rows,{'benny':'Benny'})
 async def test_question_is_not_evidence_for_a_new_remembered_fact(self):
  identifier=store_record(self.s,'Benny prefers driving to the airport.');rows=self.s.relevant('airport',['benny'])
  def model(**kw):
   out={'supported':False} if 'supported' in kw['response_schema']['properties'] else {'answer':'Benny prefers the train to the airport.','memory_ids':[identifier]}
   return {'status':'success','message':json.dumps(out)}
  with self.assertRaises(ValueError):await answer_memory(SimpleNamespace(reason_local=model),'Does Benny now prefer trains?',rows,{'benny':'Benny'})
 def test_revision_changes_for_new_correction_and_forget_not_duplicate(self):
  self.assertEqual(self.s.revision,0);identifier=store_record(self.s,'Benny prefers driving.');self.assertEqual(self.s.revision,1)
  self.s.enqueue('Benny prefers driving.',context(conversation='repeat'));self.s.finish(self.s.next_job(),[record('Benny prefers driving.')]);self.assertEqual(self.s.revision,1)
  text='Benny prefers trains.';self.s.enqueue(text,context(correct_memory=identifier,conversation='fix'));self.s.finish(self.s.next_job(),[record(text)]);self.assertEqual(self.s.revision,2)
  self.s.forget([identifier]);self.assertEqual(self.s.revision,3)
 def test_weeks_and_reopen_do_not_expire_stable_detail_or_revision(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'test.db';s=CompanionStore(path,now=lambda:NOW);identifier=store_record(s,'Benny likes high fidelity music.');s.close()
   s=CompanionStore(path,now=lambda:NOW+timedelta(weeks=9))
   try:self.assertEqual(s.relevant('music',['benny'])[0]['id'],identifier);self.assertEqual(s.revision,1)
   finally:s.close()
 def test_explicit_change_back_reactivates_quote_but_delayed_duplicate_does_not(self):
  first='Benny prefers driving.';first_id=store_record(self.s,first)
  second='Benny prefers trains.';self.s.enqueue(second,context(explicit_correction=True));second_id=self.s.finish(self.s.next_job(),[record(second,supersedes=first_id)])[0]
  self.s.enqueue(first,context(conversation='late'));self.s.finish(self.s.next_job(),[record(first)])
  self.assertEqual({m['id'] for m in self.s.memories()},{second_id})
  self.s.enqueue(first,context(conversation='change-back',explicit_correction=True));self.s.finish(self.s.next_job(),[record(first,supersedes=second_id)])
  self.assertEqual({m['id'] for m in self.s.memories()},{first_id})
 def test_inflight_manual_correction_cannot_overwrite_newer_revision(self):
  identifier=store_record(self.s,'Benny prefers driving.')
  self.s.enqueue('Benny prefers trains.',context(correct_memory=identifier,conversation='older'));older=self.s.next_job()
  self.s.enqueue('Benny prefers buses.',context(correct_memory=identifier,conversation='newer'));newer=self.s.next_job()
  self.s.finish(newer,[record('Benny prefers buses.')])
  with self.assertRaises(ValueError):self.s.finish(older,[record('Benny prefers trains.')])
  self.assertEqual(self.s.memories()[0]['quote'],'Benny prefers buses.')

class FollowthroughTests(unittest.IsolatedAsyncioTestCase):
 setUpBase=followtests.FollowupTests.setUpBase
 setUp=followtests.FollowupTests.setUp
 model=followtests.FollowupTests.model
 opened=followtests.FollowupTests.opened
 async def prepared(self):
  item,session=await self.opened();self.f.reports.save(item,{'venue':'Elm School','equipment':['instrument','sheet music']},[],'Mia needs instrument and sheet music at Elm School','fixture');await self.f.refresh();return self.f.items[item['id']]
 async def test_partial_readiness_has_only_remaining_steps(self):
  item=await self.prepared();instrument=item['checklist'][0]['id'];self.f.reports.save(item,{'venue':'Elm School','equipment':['instrument','sheet music']},[instrument],'Instrument packed','fixture');await self.f.refresh();item=self.f.items[item['id']]
  self.assertEqual(item['followthrough']['remaining'],['sheet music']);self.assertEqual(item['followthrough']['reported_ready'],['instrument']);self.assertTrue(item['followthrough']['actionable'])
 async def test_all_recorded_ready_is_not_unfinished_or_attendance(self):
  item=await self.prepared();self.f.reports.save(item,{'venue':'Elm School','equipment':['instrument','sheet music']},[s['id'] for s in item['checklist']],'Both packed','fixture');await self.f.refresh();item=self.f.items[item['id']]
  self.assertEqual(item['state'],'reported_ready');self.assertFalse(item['followthrough']['actionable']);self.assertEqual(item['followthrough']['next_actions'],[])
 async def test_priority_summary_withdrawn_after_memory_report_or_source_change(self):
  await self.prepared()
  with patch('jarvis.assistant_priorities.compose',return_value=('Check the sheet music.',True)):await self.f.prepare_brief()
  self.assertEqual(self.f.project()['summary'],'Check the sheet music.')
  store_record(self.store,'Mia likes music.',subjects=['mia']);self.assertIsNone(self.f.project()['summary']);self.assertEqual(self.f.project()['items'],[])
  await self.f.refresh()
  with patch('jarvis.assistant_priorities.compose',return_value=('Check the venue.',True)):await self.f.prepare_brief()
  self.c.events['calendar.familiekalender']=[];await self.f.refresh();self.assertIsNone(self.f.project()['summary'])
 async def test_memory_change_invalidates_day_agenda(self):
  binding=self.a.agenda.binding();store_record(self.store,'Mia likes music.',subjects=['mia']);self.assertNotEqual(binding,self.a.agenda.binding())
 async def test_explicit_natural_correction_passes_supersession_target(self):
  identifier=store_record(self.store,'Benny prefers driving to the airport.');store_record(self.store,'Benny values music.')
  text='Actually Benny now prefers trains to the airport.'
  replacement=model_item(text,supersedes=identifier)
  async def model(provider,prompt,data,schema,**kw):return {'same_detail':True} if 'same_detail' in schema['properties'] else {'items':[replacement]}
  with patch('jarvis.companion_memory.local_json',side_effect=model):r=await self.a.preference_intake(text,'fix','fictional',intent='remember')
  self.assertEqual(r['status'],'success');self.assertNotIn(identifier,{m['id'] for m in self.store.memories()});self.assertTrue(any('music' in m['quote'] for m in self.store.memories()))
 async def test_ordinary_preference_cannot_supersede_unrelated_memory(self):
  identifier=store_record(self.store,'Benny likes music.');text='Benny likes trains.'
  with patch('jarvis.companion_memory.local_json',return_value={'items':[model_item(text,supersedes=identifier)]}):r=await self.a.preference_intake(text,'other','fictional',intent='remember')
  self.assertIsNone(r);self.assertIn(identifier,{m['id'] for m in self.store.memories()})
 async def test_actually_does_not_authorise_replacing_a_different_preference(self):
  identifier=store_record(self.store,'Benny likes music.');text='Actually Benny prefers trains to the airport.'
  async def model(provider,prompt,data,schema,**kw):return {'same_detail':False} if 'same_detail' in schema['properties'] else {'items':[model_item(text,supersedes=identifier)]}
  with patch('jarvis.companion_memory.local_json',side_effect=model):r=await self.a.preference_intake(text,'wrong','fictional',intent='remember')
  self.assertIsNone(r);self.assertIn(identifier,{m['id'] for m in self.store.memories()})
 async def test_unrelated_model_reply_or_false_readiness_uses_checked_fallback(self):
  item=await self.prepared()
  async def fake(provider,instructions,data,schema,**kw):
   if 'supported' in schema['properties']:return {'supported':False}
   return {'answer':'Mia has already packed everything.','item_ids':[item['id']],'memory_ids':[]}
  with patch('jarvis.assistant_priorities.local_json',side_effect=fake):answer,model=await compose(self.a,'What needs attention?',[item])
  self.assertFalse(model);self.assertIn('sheet music',answer);self.assertNotIn('already packed',answer)
 async def test_native_read_rechecks_after_composition_and_never_writes(self):
  item=await self.prepared();before='\n'.join(self.store.db.iterdump())
  async def fake(*args,**kw):return {'selection':[item['id']],'view':'remaining'}
  with patch('jarvis.companion_memory.local_json',side_effect=fake),patch('jarvis.assistant_priorities.compose',return_value=('Check the sheet music for rehearsal.',True)):
   result=await self.f.native_read('What should Mia focus on this week?',['mia'])
  self.assertEqual(result['status'],'success');self.assertEqual(result['message'],'Check the sheet music for rehearsal.');self.assertEqual(before,'\n'.join(self.store.db.iterdump()))
  async def cancelled(*args,**kw):self.c.events['calendar.familiekalender']=[];return ('Old advice',True)
  with patch('jarvis.companion_memory.local_json',side_effect=fake),patch('jarvis.assistant_priorities.compose',side_effect=cancelled):
   with self.assertRaises(ValueError):await self.f.native_read('What should Mia focus on this week?',['mia'])
 async def test_background_change_during_draft_withholds_summary(self):
  await self.prepared()
  async def changed(*args,**kw):store_record(self.store,'Mia likes music.',subjects=['mia']);return ('Old advice',True)
  with patch('jarvis.assistant_priorities.compose',side_effect=changed):await self.f.prepare_brief()
  self.assertIsNone(self.f.project()['summary'])

if __name__=='__main__':unittest.main()
