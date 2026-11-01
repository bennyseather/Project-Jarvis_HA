"""Conversational case reads, permissions, history and truthful evidence."""
import json,unittest
from unittest.mock import patch
from jarvis.development_dialogue import followup,resumed,phase_line,result_lines,proposal_lines,release_note
from jarvis.calendar_context import calendar_scope
from jarvis.development_workspace import DevelopmentWorkspace,canonical,sha
import test_development_workspace as base

class PresentationTests(unittest.TestCase):
 def test_only_complete_independent_release_receipt_changes_the_label(self):
  row={'state':'released','release':{'version':'0.45.140','commit':'a'*40,'reviewed_by':'Codex'},'result':{'phases':{'candidate_suite':{'passed':True,'tests_reported':3}}}}
  self.assertIn('released as Jarvis 0.45.140',release_note(row));self.assertNotIn('not passed',' '.join(result_lines(row)))
  row['diff']='checked patch';self.assertNotIn('before release',proposal_lines(row,'risks'));self.assertIn('review has been recorded',proposal_lines(row,'risks'))
  for malformed in ({'state':'review_required'}, {'release':{'version':'0.45.140','commit':'a'*40,'reviewed_by':'Qwen'}},{'release':{'version':'latest','commit':'a'*40,'reviewed_by':'Codex'}}):self.assertEqual(release_note({**row,**malformed}),'')
 def test_proposal_discussion_is_closed_to_unrelated_topics(self):
  for text,kind in [('Why this change?','why'),('What could it affect?','risks'),('What would you improve next?','next')]:self.assertEqual(followup(text),kind)
  for text in ("What could Mia's appointment affect?",'Why this change and deploy it','What should Mia improve next?'):self.assertIsNone(followup(text))
 def test_inspection_discussion_does_not_invent_a_defect_or_candidate(self):
  row={'scope':'memory','summary':'It reads attributed memories.','state':'inspection_complete','mode':'inspect','citations':[{'symbol':'answer_memory'}]}
  self.assertIn('not evidence of a defect',proposal_lines(row,'why'))
  self.assertIn('no candidate change',proposal_lines(row,'risks').lower())
  self.assertIn('concrete failing example',proposal_lines(row,'next'))
 def test_candidate_risks_and_next_step_do_not_treat_tests_as_approval(self):
  row={'scope':'memory','problem':'IDs appeared in an answer.','summary':'Request one clean rewrite.','state':'review_required','diff':'a real diff','citations':[{'symbol':'answer_memory'}],'result':{'phases':{'candidate_suite':{'passed':True,'tests_reported':3}}}}
  self.assertIn(row['problem'],proposal_lines(row,'why'));self.assertIn(row['summary'],proposal_lines(row,'why'))
  self.assertIn('do not prove every behaviour',proposal_lines(row,'risks'));self.assertIn('independently review',proposal_lines(row,'next'))
  row['state']='needs_revision';row['result']['phases']['candidate_suite']['passed']=False
  self.assertIn('no passing full candidate',proposal_lines(row,'risks'));self.assertIn('failed checks',proposal_lines(row,'next'))
 def test_expected_failure_requires_the_correct_phase_and_both_flags(self):
  for name,passed,failed,expected in [('original_regression',False,True,True),('original_regression',False,False,False),('original_regression',True,True,False),('candidate_suite',False,True,False),('original_suite',False,True,False)]:
   with self.subTest(name=name,passed=passed,failed=failed):
    text=phase_line(name,{'tests_reported':1,'passed':passed,'assertion_failure':failed})
    self.assertEqual('failed as expected' in text,expected)
    if not passed and not expected:self.assertIn('did not pass',text)
 def test_singular_and_plural_keep_reported_counts(self):
  for count,noun in ((0,'tests'),(1,'test'),(2,'tests')):self.assertIn(str(count)+' '+noun+' reported',phase_line('candidate_suite',{'tests_reported':count,'passed':True}))
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
 async def test_proposal_discussion_is_read_only_and_case_bound(self):
  row=self.row();row.update(mode='inspect',state='inspection_complete',summary='It reads evidence.');self.w.save(row)
  with calendar_scope({'actor':'owner','read':True,'write':False}):
   await self.w.handle('show '+row['id'],'chat','phone')
   for text in ('Why this change?','What could it affect?','What would you improve next?'):
    out=await self.w.handle(text,'chat','phone');self.assertEqual(out['development_case'],row['id'])
    self.assertIn('Which development case',(await self.w.handle(text,'other','phone'))['message'])
  self.assertEqual(len(self.w.jobs()),1);self.assertFalse(any(path=='/v1/jobs' for path,_ in self.calls))
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

class QwenRegressionTests(unittest.TestCase):
 # Qwen supplied this valid positive regression in W687e4d2d6634. Its proposed
 # implementation failed independent semantic review and was not applied.
 def test_original_regression_failure(self):
  phase={'tests_reported':1,'passed':False,'assertion_failure':True}
  result=phase_line('original_regression',phase)
  self.assertIn('failed as expected',result)
  self.assertNotIn('did not pass',result)
