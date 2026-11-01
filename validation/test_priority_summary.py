"""Weekly preparation summaries: source coverage, timing and useful known kit."""
import unittest,re
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
import test_memory_followthrough as fixtures
from test_companion_memory import NOW,store_record
from jarvis.assistant_priorities import fallback,next_steps,compose,preparation_groups

class PriorityTests(unittest.IsolatedAsyncioTestCase):
 setUpBase=fixtures.FollowthroughTests.setUpBase
 setUp=fixtures.FollowthroughTests.setUp
 model=fixtures.FollowthroughTests.model
 opened=fixtures.FollowthroughTests.opened
 prepared=fixtures.FollowthroughTests.prepared
 async def test_settled_status_names_reported_ready_items_without_new_packing_advice(self):
  item=await self.prepared()
  for step in item['checklist']:step['ready']=True
  item['followthrough']=next_steps(item,NOW)
  with patch('jarvis.assistant_priorities.local_json') as model:answer,composed=await compose(self.a,'What is already ready?',[item])
  model.assert_not_awaited();self.assertFalse(composed);self.assertIn('reported',answer);self.assertIn('instrument',answer);self.assertNotIn('Check instrument',answer)
 async def test_missing_model_coverage_cannot_silently_drop_weekly_preparations(self):
  item=await self.prepared()
  with patch('jarvis.companion_memory.local_json',return_value={'selection':[item['id']],'view':'remaining'}):
   with self.assertRaises(ValueError):await self.f.native_read('What should the household prepare in the next seven days?',[])
 def test_focused_recall_drops_unrelated_same_person_records(self):
  target=store_record(self.store,'Benny values high fidelity music.',topic='audio',tags=['music'])
  store_record(self.store,'Benny likes fictional colours.',topic='colours',tags=['colours'])
  self.assertEqual([r['id'] for r in self.store.relevant('What does Benny prefer for music?',['benny'])],[target])
 def test_broad_preference_lookup_still_keeps_different_topics(self):
  first=store_record(self.store,'Benny values music.',topic='audio',tags=['music']);second=store_record(self.store,'Benny likes colours.',topic='colours',tags=['colours'])
  self.assertEqual({r['id'] for r in self.store.relevant('What does Benny prefer?',['benny'])},{first,second})
 async def test_composition_retries_a_generic_draft_using_the_checked_facts(self):
  item=await self.prepared()
  drafts=[{'answer':'The next actionable step is to gather required information.','item_ids':[item['id']],'memory_ids':[]},{'answer':'Have her instrument and sheet music ready for the rehearsal tomorrow.','item_ids':[item['id']],'memory_ids':[]},{'supported':True}]
  with patch('jarvis.assistant_priorities.local_json',side_effect=drafts):answer,model=await compose(self.a,'What needs preparing?',[item])
  self.assertTrue(model);self.assertIn('sheet music',answer);self.assertNotIn('next actionable',answer)
 async def test_weekly_scope_keeps_known_kit_when_model_only_selects_a_missing_venue(self):
  item=await self.prepared();self.c.events['calendar.familiekalender'][1]['location']='';await self.f.refresh();unknown=next(i for i in self.f.items.values() if i['id']!=item['id'])
  async def select(*a,**kw):return {'selection':[unknown['id']],'view':'remaining','coverage':'period'}
  with patch('jarvis.companion_memory.local_json',side_effect=select),patch('jarvis.assistant_priorities.compose',return_value=('Have the instrument and sheet music ready, then check the other venue.',True)) as model:
   result=await self.f.native_read('What should the household focus on preparing the next seven days?',[])
  self.assertEqual(set(result['priority_items']),{item['id'],unknown['id']});self.assertEqual(len(model.call_args.args[2]),2)
 async def test_today_query_cannot_include_tomorrows_preparations(self):
  await self.prepared()
  with patch('jarvis.companion_memory.local_json',return_value={'selection':['none'],'view':'remaining','coverage':'period'}),patch('jarvis.assistant_priorities.compose') as model:
   result=await self.f.native_read('What should the household prepare today?',[])
  self.assertEqual(result['priority_items'],[]);model.assert_not_awaited();self.assertNotIn('instrument',result['message'])
 async def test_started_training_is_not_a_future_before_event_task(self):
  self.a.now=lambda:NOW+timedelta(days=1,hours=2,minutes=45)
  await self.f.refresh();ongoing=next(i for i in self.f.items.values() if i['title']=='Band rehearsal');self.assertTrue(ongoing['followthrough']['in_progress'])
  with patch('jarvis.companion_memory.local_json',return_value={'selection':[ongoing['id']],'view':'remaining','coverage':'period'}),patch('jarvis.assistant_priorities.compose',return_value=('Prepare for the later activity.',True)):
   result=await self.f.native_read('What needs attention in the next seven days?',[])
  self.assertNotIn(ongoing['id'],result['priority_items'])
 async def test_status_can_still_inspect_an_ongoing_appointment(self):
  self.a.now=lambda:NOW+timedelta(days=1,hours=2,minutes=45);await self.f.refresh();ongoing=next(i for i in self.f.items.values() if i['title']=='Band rehearsal')
  with patch('jarvis.companion_memory.local_json',return_value={'selection':[ongoing['id']],'view':'status','coverage':'selected'}),patch('jarvis.assistant_priorities.compose',return_value=('No preparation has been reported ready.',True)):
   result=await self.f.native_read('What is already reported ready for band rehearsal?',['mia'])
  self.assertIn(ongoing['id'],result['priority_items'])
 async def test_clock_phase_change_withdraws_cached_brief_without_a_source_change(self):
  await self.prepared()
  with patch('jarvis.assistant_priorities.compose',return_value=('Check the sheet music.',True)):await self.f.prepare_brief()
  self.assertTrue(self.f.project()['summary'])
  self.a.now=lambda:NOW+timedelta(days=1,hours=2,minutes=39);await self.f.refresh()
  with patch('jarvis.assistant_priorities.compose',return_value=('Check the sheet music.',True)):await self.f.prepare_brief()
  self.assertTrue(self.f.project()['summary']);self.a.now=lambda:NOW+timedelta(days=1,hours=2,minutes=41)
  self.assertIsNone(self.f.project()['summary'])
 async def test_start_passing_during_composition_withdraws_future_advice(self):
  self.a.now=lambda:NOW+timedelta(days=1,hours=2,minutes=39);await self.f.refresh();item=next(i for i in self.f.items.values() if i['title']=='Band rehearsal')
  async def changed(*a,**kw):self.a.now=lambda:NOW+timedelta(days=1,hours=2,minutes=41);return ('Prepare before the rehearsal starts.',True)
  with patch('jarvis.companion_memory.local_json',return_value={'selection':[item['id']],'view':'remaining','coverage':'selected'}),patch('jarvis.assistant_priorities.compose',side_effect=changed):
   result=await self.f.native_read('What still needs preparing for the band rehearsal?',['mia'])
  self.assertEqual(result['status'],'unavailable');self.assertNotIn('Prepare before',result['message'])
 async def test_unmapped_title_does_not_inherit_another_rehearsals_venue(self):
  item=await self.prepared();raw=deepcopy(item['_event']);raw['title']='Different rehearsal';raw['location']=''
  self.p._data['activity_profiles']=[{'person':'mia','source':'family','title':'Band rehearsal','activity':'band rehearsal','equipment':['instrument','sheet music'],'preparation':None,'usual_venue':'Elm School'}]
  unknown=self.f.build(raw,'mia');self.assertEqual(unknown['venue'],'');self.assertIn('venue',unknown['gaps']);self.assertIsNone(unknown['_usual'])
 async def test_fallback_groups_identical_kit_and_avoids_raw_iso_or_check_review(self):
  item=await self.prepared();second=deepcopy(item);second['id']='second';second['date']='2026-10-30';second['start']='2026-10-30T15:40:00+01:00';second['followthrough']=next_steps(second,NOW)
  answer=fallback([item,second]);self.assertEqual(answer.count('sheet music'),1);self.assertNotRegex(answer,r'\b20\d\d-\d\d-\d\d\b');self.assertEqual(len(preparation_groups([item,second])),1)
  item['checklist'].append({'text':'Review the organiser notes','kind':'organiser','ready':False});self.assertNotIn('Check Review',str(next_steps(item,NOW)))
 async def test_model_cannot_return_a_venue_only_answer_when_known_kit_is_available(self):
  known=await self.prepared();unknown=deepcopy(known);unknown['id']='unknown';unknown['checklist']=[];unknown['gaps']=['venue'];unknown['followthrough']=next_steps(unknown,NOW)
  with patch('jarvis.assistant_priorities.local_json',return_value={'answer':'Confirm the venue.','item_ids':['unknown'],'memory_ids':[]}):answer,model=await compose(self.a,'What should the household prepare this week?',[known,unknown])
  self.assertFalse(model);self.assertIn('instrument',answer);self.assertIn('sheet music',answer)

if __name__=='__main__':unittest.main()
