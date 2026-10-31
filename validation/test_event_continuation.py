"""No-report selected-event continuation; fictional data only."""
import unittest
from datetime import datetime
from copy import deepcopy
import test_event_preparation as prep
from jarvis.event_preparation import EventPreparation
from jarvis.event_activity import requirement
class ContinuationTests(unittest.IsolatedAsyncioTestCase):
 setUp=prep.PreparationTests.setUp
 ask=prep.PreparationTests.ask
 def monday(self):
  self.now[0]=datetime(2026,10,31,12,tzinfo=prep.ZONE)
  self.event.update(summary='Fellesøving Korps',start='2026-11-02T17:30:00+01:00',end='2026-11-02T18:30:00+01:00',location='',description='')
  self.client.events['calendar.familiekalender']=[deepcopy(self.event)]
 async def initial(self):
  self.monday();result=await self.ask('What should Mia prepare on monday?')
  self.assertEqual(result['status'],'success');self.assertIn('17:30',result['message']);return deepcopy(self.h.sessions['s'])
 async def test_no_report_remaining_keeps_monday_and_admits_unknown_readiness(self):
  plan=await self.initial()
  resolved={**plan,'question':'whats left before we leave?','previous_question':plan['question'],'shared_read_context':True,'event_continuation':True}
  with prep.scope(self.p,'benny','s'):result=await self.h.handle('whats left before we leave?','s',resolved=resolved)
  self.assertEqual(result['status'],'success',result);self.assertEqual(result['report_goal'],'remaining');self.assertIn('17:30',result['message']);self.assertIn('no packing or readiness report',result['message']);self.assertNotIn('which appointment',result['message'].casefold());self.assertNotIn('not packed',result['message']);self.assertEqual(self.h.sessions['s']['source_focus'],plan['source_focus'])
 async def test_removed_focus_does_not_select_another_same_day_event(self):
  plan=await self.initial();self.client.events['calendar.familiekalender']=[{**self.event,'summary':'Swimming lesson','start':'2026-11-02T19:00:00+01:00','end':'2026-11-02T20:00:00+01:00'}]
  resolved={**plan,'question':'whats left before we leave?','previous_question':plan['question'],'shared_read_context':True,'event_continuation':True}
  with prep.scope(self.p,'benny','s'):result=await self.h.handle('whats left before we leave?','s',resolved=resolved)
  self.assertEqual(result['status'],'clarification_required');self.assertIn('selected appointment changed',result['message']);self.assertNotIn('Swimming',result['message'])
 async def test_explicit_new_kind_does_not_bypass_source_evidence(self):
  plan=await self.initial();resolved={**plan,'source_focus':[],'question':'What about swimming?','previous_question':plan['question'],'shared_read_context':True,'event_continuation':False}
  with prep.scope(self.p,'benny','s'):result=await self.h.handle('What about swimming?','s',resolved=resolved)
  self.assertEqual(result['status'],'clarification_required');self.assertIn('cannot confirm that activity',result['message'])
if __name__=='__main__':unittest.main()
