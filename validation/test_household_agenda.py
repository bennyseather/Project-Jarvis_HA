"""Background plans: source changes, privacy boundaries and no household actions."""
import asyncio,unittest,json
from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock,patch
import test_activity_learning_bundle as learning
Transport=learning.Transport;NOW=learning.NOW
from jarvis.household_agenda import HouseholdAgenda,Superseded
from jarvis.companion_routing import CompanionRouting

APPROVAL={'schema_version':1,'enabled':True,'approval_source':'Fictional authorised planner','recorded_on':'2026-10-29'}
class AgendaTests(unittest.IsolatedAsyncioTestCase):
 setUpBase=learning.LearningTests.setUp
 def setUp(self):
  self.setUpBase();self.time=[NOW];self.a.now=lambda:self.time[0];self.container.proactive_allowed_entities=tuple(self.c.events)
  self.addCleanup(lambda:getattr(self.container,'household_planner',None) and self.container.household_planner.db.close())
  self.agenda=HouseholdAgenda(self.a,approval=deepcopy(APPROVAL));self.a.agenda=self.agenda
  t=Transport();t.minutes=9;self.container.companion_routing=CompanionRouting(self.a,transport=t)
  self.model_calls=0
  async def prose(*args,**kw):
   self.model_calls+=1;return {'status':'success','message':'Verified preparation advice.','local_model_interpretation':True}
  self.prep=patch('jarvis.event_preparation.EventPreparation.handle',new=prose);self.prep.start();self.addCleanup(self.prep.stop)
  self.think=patch('jarvis.household_thinking.HouseholdThinking.handle',new=prose);self.think.start();self.addCleanup(self.think.stop)
 async def test_approved_background_builds_both_days_without_writes(self):
  before=self.path.read_bytes();await self.agenda.refresh();view=self.agenda.project()
  self.assertEqual(len(view['days']),2);self.assertEqual(len(view['days'][1]['people']),4)
  self.assertTrue(self.model_calls);self.assertEqual(before,self.path.read_bytes());self.assertFalse(self.store.memories());self.assertEqual(self.store.job_counts(),{})
  mia=next(p for p in view['days'][1]['people'] if p['id']=='mia');self.assertEqual(mia['event_count'],2)
  self.assertIn('needs checking',' '.join(mia['attention']));self.assertEqual(mia['departures'][0]['leave_at'],'2026-10-29T16:41:00+01:00')
 async def test_unchanged_sources_do_not_repeat_model_work(self):
  await self.agenda.refresh();count=self.model_calls;await self.agenda.refresh();self.assertEqual(count,self.model_calls)
 async def test_calendar_change_and_cancellation_replace_old_plans(self):
  await self.agenda.refresh();self.c.events['calendar.familiekalender'][1]['start']='2026-10-29T18:00:00+01:00';self.c.events['calendar.familiekalender'][1]['end']='2026-10-29T19:00:00+01:00'
  await self.agenda.refresh();mia=next(p for p in self.agenda.project()['days'][1]['people'] if p['id']=='mia');self.assertEqual(mia['departures'][0]['leave_at'],'2026-10-29T17:41:00+01:00')
  self.c.events['calendar.familiekalender']=[];await self.agenda.refresh();mia=next(p for p in self.agenda.project()['days'][1]['people'] if p['id']=='mia');self.assertFalse(mia['departures']);self.assertEqual(mia['event_count'],0)
 async def test_no_approval_sharing_or_enablement_means_no_projection(self):
  await self.agenda.refresh()
  for field in ('enabled','approval_source'):
   original=self.agenda.approval[field];self.agenda.approval[field]=False if field=='enabled' else '';self.assertEqual(self.agenda.project()['days'],[]);self.agenda.approval[field]=original
  self.p._data['sharing_policy']['knowledge_access']['mode']='disabled';self.assertFalse(self.agenda.project()['days'])
 async def test_source_outage_does_not_retain_an_old_departure_as_current(self):
  await self.agenda.refresh();self.container.household_thinking.reader.handle=AsyncMock(return_value=None)
  await self.agenda.refresh();self.assertTrue(all(not d['people'] for d in self.agenda.project()['days']));self.assertEqual([d['label'] for d in self.agenda.project()['days']],['Today','Tomorrow']);self.assertTrue(all('needs checking' in d['coverage'] for d in self.agenda.project()['days']))
 async def test_profile_and_allowlist_change_withdraw_old_projection(self):
  await self.agenda.refresh();self.p._data['revision']+=1;self.assertFalse(self.agenda.project()['days']);self.p._data['revision']-=1
  self.container.proactive_allowed_entities=();self.assertFalse(self.agenda.project()['days']);await self.agenda.refresh();self.assertFalse(self.agenda.project()['days'])
 async def test_day_rollover_and_old_checks_are_not_shown_as_fresh(self):
  await self.agenda.refresh();self.time[0]+=timedelta(seconds=181);self.assertTrue(all(not d['people'] for d in self.agenda.project()['days']))
  self.time[0]+=timedelta(days=1);self.assertFalse(self.agenda.project()['days'])
 async def test_foreground_entry_cancels_background_work(self):
  blocked=asyncio.Event();self.agenda.work=asyncio.create_task(blocked.wait());await asyncio.sleep(0)
  self.a.enter();await asyncio.gather(self.agenda.work,return_exceptions=True);self.assertTrue(self.agenda.work.cancelled())
  with self.assertRaises(Superseded):await self.agenda.refresh()
  self.a.leave()
 async def test_profile_change_during_model_work_cannot_publish(self):
  async def change(*args,**kw):self.p._data['revision']+=1;return {'status':'success','message':'Old advice.'}
  with patch('jarvis.household_thinking.HouseholdThinking.handle',new=change),patch('jarvis.event_preparation.EventPreparation.handle',new=change):
   with self.assertRaises(Superseded):await self.agenda.refresh()
  self.assertFalse(self.agenda.project()['days'])
 async def test_source_recheck_prevents_publish_from_changed_snapshot(self):
  original=self.container.household_thinking.reader.handle;count=0
  async def read(*a,**kw):
   nonlocal count
   count+=1;result=await original(*a,**kw)
   if count==2:result['evidence']['source_failures'].append('Calendar changed during generation')
   return result
  self.container.household_thinking.reader.handle=read
  with self.assertRaises(Superseded):await self.agenda.refresh()
  self.assertTrue(all(not d['people'] for d in self.agenda.project()['days']))
 async def test_all_day_and_work_entries_do_not_assume_a_home_drive(self):
  self.c.events['calendar.familiekalender']=[{'summary':'All day activity','start':'2026-10-29','end':'2026-10-30','location':'Sports Hall'}]
  await self.agenda.refresh();self.assertTrue(all(not p['departures'] for d in self.agenda.project()['days'] for p in d['people']))
 async def test_cross_person_overlap_is_conditional_not_an_assigned_driver(self):
  base={'kind':'appointment','all_day':False,'start':'2026-10-29T17:00:00+01:00','end':'2026-10-29T18:00:00+01:00'}
  e={'facts':[{**base,'owners':['mia'],'location':'Hall A'},{**base,'owners':['linda'],'location':'Hall B'}]}
  text=self.agenda.coordination(e,{'mia':'Mia','linda':'Linda'})[0];self.assertIn('If shared transport is needed',text);self.assertNotIn('will drive',text)

if __name__=='__main__':unittest.main()
