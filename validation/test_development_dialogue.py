"""Conversational case reads, permissions, history and truthful evidence."""
import json,unittest
from unittest.mock import patch
from jarvis.development_dialogue import followup,resumed,phase_line,result_lines
from jarvis.calendar_context import calendar_scope
from jarvis.development_workspace import DevelopmentWorkspace,canonical,sha
import test_development_workspace as base

class PresentationTests(unittest.TestCase):
 def test_closed_followups_do_not_steal_household_topics(self):
  for text,kind in [('What did you find?','findings'),('How is it going?','status'),('Show the patch','patch'),('Did the tests pass?','tests')]:self.assertEqual(followup(text),kind)
  for text in ('What should Mia bring?','And her birthday?','Did Mia pass her tests?','Show the patch and deploy it','How is Mia going tomorrow?'):self.assertIsNone(followup(text))
 def test_resumption_prefix_is_specific_to_development(self):
  self.assertEqual(resumed('Back to development, what did you find?'),'what did you find?')
  self.assertIsNone(resumed("Back to Mia's rehearsal, what should she bring?"))
 def test_existing_suite_success_and_candidate_failure_are_distinct(self):
  self.assertIn('passed',phase_line('original_suite',{'tests_reported':2,'passed':True}))
  self.assertIn('did not pass',phase_line('candidate_suite',{'tests_reported':2,'passed':False}))
 def test_inspection_never_claims_tests_or_a_patch(self):
  self.assertIn('no tests were run',' '.join(result_lines({'mode':'inspect','state':'inspection_complete'})))
  self.assertIn('No completed test results',' '.join(result_lines({'mode':'investigate','state':'drafting'})))
 def test_interrupted_and_failed_candidate_keep_review_qualification(self):
  text=' '.join(result_lines({'state':'interrupted','result':{'phases':{'candidate_suite':{'passed':False,'tests_reported':2}}}}))
  self.assertIn('not passed',text);self.assertIn('independent review',text)

class ConversationTests(unittest.IsolatedAsyncioTestCase):
 setUp=base.WorkspaceTests.setUp
 request=base.WorkspaceTests.request
 model=base.WorkspaceTests.model
 row=base.WorkspaceTests.row
 async def test_natural_reads_use_current_case_in_same_conversation(self):
  row=self.row();row.update(state='inspection_complete',summary='It joins items.',mode='inspect');self.w.save(row)
  with calendar_scope({'actor':'owner','read':True,'write':True}):
   await self.w.handle('show '+row['id'],'chat','phone')
   self.assertIn('It joins items.',(await self.w.handle('What did you find?','chat','phone'))['message'])
   self.assertIn('no tests were run',(await self.w.handle('Did the tests pass?','chat','phone'))['message'])
   self.assertIn('No candidate patch',(await self.w.handle('Show the patch','chat','phone'))['message'])
   self.assertIn('Which development case',(await self.w.handle('What did you find?','other','phone'))['message'])
 async def test_focus_cannot_cross_ha_account_or_source_and_expires(self):
  row=self.row()
  with calendar_scope({'actor':'owner','read':True,'write':True}):await self.w.handle('show '+row['id'],'chat','phone')
  with calendar_scope({'actor':'other','read':True,'write':True}):self.assertIn('Which development case',(await self.w.handle('What did you find?','chat','phone'))['message'])
  with calendar_scope({'actor':'owner','read':True,'write':True}):
   self.assertIsNone(self.w.selected('chat','tablet'))
   self.owner.clock=lambda:2001;self.assertIsNone(self.w.selected('chat','phone'))
 async def test_unrelated_topic_leaves_followup_unrouted_until_explicit_return(self):
  with calendar_scope({'actor':'owner','read':True,'write':True}):
   self.assertTrue(self.w.routes('What did you find?','chat','phone','development'))
   self.assertFalse(self.w.routes('What did you find?','chat','phone','football'))
   self.assertTrue(self.w.routes('Back to development, what did you find?','chat','phone','football'))
   self.assertFalse(self.w.routes('And her birthday?','chat','phone','development'))
 async def test_inactive_case_cannot_be_used_by_a_misrouted_bare_followup(self):
  row=self.row();row.update(state='inspection_complete',summary='Code finding.');self.w.save(row)
  with calendar_scope({'actor':'owner','read':True,'write':True}):
   await self.w.handle('show '+row['id'],'chat','phone');self.w.deactivate('chat','phone')
   self.assertIn('Which development case',(await self.w.handle('What did you find?','chat','phone'))['message'])
   self.assertIn('Code finding.',(await self.w.handle('Back to development, what did you find?','chat','phone'))['message'])
 async def test_diagnostics_retained_and_default_status_focuses_on_real_work(self):
  diagnostic=self.row();diagnostic.update(diagnostic=True,state='inspection_complete',problem='Diagnostic');self.w.save(diagnostic)
  real={**diagnostic,'id':'W'+'2'*12,'diagnostic':False,'problem':'Real case','state':'inspecting'};self.w.save(real)
  with calendar_scope({'actor':'owner','read':True,'write':True}):
   out=await self.w.handle('show development workspace','chat','phone');self.assertNotIn('Diagnostic',out['message']);self.assertIn('in progress',out['message'])
   self.assertEqual(self.w.selected('chat','phone')['id'],real['id'])
   self.assertIn('(diagnostic)',(await self.w.handle('show development history','chat','phone'))['message'])
  self.assertEqual(len(self.w.jobs()),2);self.assertEqual(self.w.project()['diagnostic_count'],1)
 async def test_results_stay_before_source_so_mobile_formatter_keeps_them(self):
  row=self.row();row.update(state='review_required',summary='A candidate.',result={'phases':{'candidate_suite':{'passed':True,'tests_reported':2}}},citations=[{'path':'src/jarvis/workshop_fixture.py','start':1,'symbol':'join_items'}]);self.w.save(row)
  message=self.w.explain(row)['message'];self.assertLess(message.index('tests reported'),message.index('Source:'));self.assertIn('independent review',message.split('Source:')[0])
 async def test_followup_cannot_grant_write_authority_or_run_new_work(self):
  row=self.row();before=len(self.w.jobs())
  with calendar_scope({'actor':'owner','read':True,'write':False}):
   await self.w.handle('show '+row['id'],'chat','phone')
   await self.w.handle('Did the tests pass?','chat','phone')
   self.assertEqual((await self.w.handle('cancel '+row['id'],'chat','phone'))['status'],'forbidden')
  self.assertEqual(len(self.w.jobs()),before);self.assertFalse(any(path=='/v1/jobs' for path,_ in self.calls))
