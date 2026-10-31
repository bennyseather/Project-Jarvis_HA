import unittest
from unittest.mock import AsyncMock,patch
import test_planning_followthrough as fixture
from jarvis.planning_followup import SOURCE_NAMES
from jarvis.calendar_context import calendar_scope
class NativePlanningTests(unittest.IsolatedAsyncioTestCase):
 setUpBase=fixture.FollowupTests.setUpBase
 setUp=fixture.FollowupTests.setUp
 async def focused(self,key='native',source='fixture'):
  await self.f.refresh();item=next(i for i in self.f.items.values() if i['person']=='mia' and i['title']=='Band rehearsal');e=item['_event'];state=self.a.agent.state(key,source)
  state['read_focus']={'purpose':'preparation','question':'What should Mia prepare tomorrow?','task':'What should Mia prepare tomorrow?','window':'all_day','between':False,'subjects':['mia'],'start':'2026-10-29','end':'2026-10-30','expires':self.a.clock()+600,'event_focus':[(e['title'],SOURCE_NAMES[e['source']],e['start'],e['end'],tuple(e['members']))]}
  return state,item
 async def test_details_review_confirm_and_new_conversation_reads_same_store(self):
  state,item=await self.focused();r=await self.a.planning_conversation.handle(self.text,'native','fixture',state);self.assertTrue(r['planning_report_review']);self.assertIsNone(self.f.reports.get(item));self.assertIn('Shall I save',r['message'])
  done=await self.a.planning_conversation.confirm('yes','native','fixture',state);self.assertTrue(done['planning_report_saved']);self.assertEqual(self.f.reports.get(item)['details']['journey_minutes'],2);self.assertIsNone(await self.a.planning_conversation.confirm('yes','native','fixture',state));self.assertEqual(self.store.memories(),[])
 async def test_ready_item_only_needs_review_and_remaining_updates(self):
  state,item=await self.focused();r=await self.a.planning_conversation.handle(self.text,'native','fixture',state);await self.a.planning_conversation.confirm('yes','native','fixture',state)
  state,item=await self.focused();step=item['checklist'][0]['id'];self.frame.update(intent='readiness',ready=[step],venue='',equipment=[],journey_quote='')
  r=await self.a.planning_conversation.handle('Her instrument is already packed.','native','fixture',state);self.assertFalse(self.f.items[item['id']]['checklist'][0]['ready']);done=await self.a.planning_conversation.confirm('yes','native','fixture',state);self.assertIn('Still to check',done['message']);self.assertTrue(self.f.items[item['id']]['checklist'][0]['ready'])
 async def test_cancel_or_changed_source_does_not_save(self):
  state,item=await self.focused();await self.a.planning_conversation.handle(self.text,'native','fixture',state);await self.a.planning_conversation.confirm('cancel','native','fixture',state);self.assertIsNone(self.f.reports.get(item))
  await self.a.planning_conversation.handle(self.text,'native','fixture',state);self.c.events['calendar.familiekalender']=[];done=await self.a.planning_conversation.confirm('yes','native','fixture',state);self.assertNotEqual(done['status'],'success');self.assertIsNone(self.f.reports.get(item))
 async def test_missing_ambiguous_expired_and_different_person_no_save(self):
  state,item=await self.focused();state['read_focus']['event_focus']*=2;r=await self.a.planning_conversation.handle(self.text,'native','fixture',state);self.assertIn('Which appointment',r['message'])
  state,item=await self.focused();state['read_focus']['expires']=0;r=await self.a.planning_conversation.handle(self.text,'native','fixture',state);self.assertIn('Which appointment',r['message'])
  state,item=await self.focused();state['read_focus']['subjects']=['emrik'];r=await self.a.planning_conversation.handle(self.text,'native','fixture',state);self.assertNotIn('planning_report_review',r)
 async def test_usual_profile_uses_same_review(self):
  state,item=await self.focused();self.frame['scope']='usual';r=await self.a.planning_conversation.handle('Usually at Elm School, instrument and sheet music, two minutes from home.','native','fixture',state);self.assertIn('usual activity knowledge',r['message']);self.assertFalse(self.p._data.get('activity_profiles'));done=await self.a.planning_conversation.confirm('yes','native','fixture',state);self.assertTrue(done['planning_report_saved']);self.assertEqual(self.p._data['activity_profiles'][0]['usual_venue'],'Elm School')
 async def test_read_only_cannot_report_or_confirm(self):
  state,item=await self.focused()
  with calendar_scope({'actor':'test-owner','read':True,'write':False}):
   with self.assertRaises(ValueError):await self.a.planning_conversation.handle(self.text,'native','fixture',state)
 async def test_pending_home_journey_accepts_bare_duration(self):
  state,item=await self.focused();state['read_focus']['awaiting_detail']='journey';self.frame.update(venue='',equipment=[],journey_quote='two minutes')
  r=await self.a.planning_conversation.handle('two minutes','native','fixture',state);self.assertTrue(r['planning_report_review']);done=await self.a.planning_conversation.confirm('yes','native','fixture',state);self.assertEqual(self.f.reports.get(item)['details']['journey_minutes'],2)
 async def model(self,*a,**kw):return await fixture.FollowupTests.model(self,*a,**kw)
