"""Fictional own-code cases: no production API, shell or credentials."""
import asyncio,json,tempfile,unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from jarvis.development_contract import *
from jarvis.development_workspace import DevelopmentWorkspace,Client,load_config,URL,workspace_command
from jarvis.companion_store import CompanionStore
from jarvis.calendar_context import calendar_scope
from test_companion_memory import NOW

SOURCE='def join_items(items):\n    return "".join(items)\n\ndef untouched():\n    return 4\n'
TEST='import unittest\nfrom jarvis.workshop_fixture import join_items\nclass Regression(unittest.TestCase):\n def test_separator(self):\n  self.assertEqual(join_items(["one","two"]), "one, two")\n'
def snapshot():return make_snapshot({'src/jarvis/workshop_fixture.py':SOURCE,'validation/test_workshop_fixture.py':'import unittest\nclass Base(unittest.TestCase):\n def test_base(self):\n  self.assertTrue(True)\n'},'0.45.138','a'*40,fixture=True)
def candidate():return {'path':'src/jarvis/workshop_fixture.py','symbol':'join_items','module_sha256':sha(SOURCE),'old':'return "".join(items)','new':'return ", ".join(items)','test_source':TEST}
def config(**kw):return {'enabled':True,'url':URL,'token':'F'*48,'snapshot':snapshot()['digest'],'approval_source':'Fictional approval','recorded_on':'2026-11-01',**kw}

class ContractTests(unittest.TestCase):
 def test_workspace_command_scope_does_not_capture_family_memory_questions(self):
  for text in ('show development workspace','inspect your weekly preparation code','show patch W123456789abc','cancel W123456789abc'):self.assertTrue(workspace_command(text))
  for text in ('what does Benny remember?','show me Mia plans','inspect my music preferences','show ../../config','cancel my appointment'):self.assertFalse(workspace_command(text))
 def test_exact_source_citation_and_deterministic_patch(self):
  snap=snapshot();inspected=inspect_source(snap,'fixture','src/jarvis/workshop_fixture.py','join_items')
  self.assertEqual(inspected['source'],'def join_items(items):\n    return "".join(items)\n');self.assertEqual(inspected['start'],1)
  result=apply_candidate(snap,'fixture',candidate());self.assertIn('+    return ", ".join(items)',result['diff']);self.assertEqual(snap['files']['src/jarvis/workshop_fixture.py'],SOURCE)
 def test_snapshot_digest_size_paths_and_reserved_test(self):
  for name in ('../secret.py','src/jarvis/../../x.py','src\\jarvis\\x.py','/config/private.py','validation/a.txt','src/jarvis/x.py/evil.py'):
   if name=='src/jarvis/x.py/evil.py':continue
   with self.assertRaises(ValueError):make_snapshot({name:'pass'},'0.45.138','a'*40)
  snap=snapshot();snap['files']['src/jarvis/workshop_fixture.py']='pass'
  with self.assertRaises(ValueError):validate_snapshot(snap)
  with self.assertRaises(ValueError):make_snapshot({'validation/test_workshop_candidate.py':'pass'},'0.45.138','a'*40)
 def test_scope_cannot_expand_to_config_shell_or_other_function(self):
  for change in ({'path':'/config/private.py'},{'symbol':'untouched'},{'module_sha256':'0'*64},{'execute':'sh'},{'new':'return 1\n\ndef injected():\n    return 2'},{'old':'def join_items(items):','new':'def renamed(items):'},{'old':'not in source'},{'new':candidate()['old']}):
   with self.subTest(change=change),self.assertRaises((ValueError,SyntaxError)):apply_candidate(snapshot(),'fixture',{**candidate(),**change})
 def test_generated_test_must_be_bounded_real_test_module(self):
  for test in ('pass','def test_bad(: pass','x'*2500):
   with self.assertRaises((ValueError,SyntaxError)):apply_candidate(snapshot(),'fixture',{**candidate(),'test_source':test})
 def test_full_job_identity_and_immutable_snapshot(self):
  body={'id':'W'+'1'*12,'snapshot':snapshot()['digest'],'scope':'fixture','patch':candidate()}
  self.assertTrue(validate_job(snapshot(),body)['diff'])
  for field in ({'id':'../../evil'},{'snapshot':'0'*64},{'scope':'preparation'},{'command':'sh'}):
   with self.assertRaises(ValueError):validate_job(snapshot(),{**body,**field})
 def test_signature_and_decorators_cannot_change(self):
  for old,new in [('def join_items(items):','def join_items(items, extra=None):'),('def join_items(items):','@staticmethod\ndef join_items(items):')]:
   with self.assertRaises(ValueError):apply_candidate(snapshot(),'fixture',{**candidate(),'old':old,'new':new})
 def test_config_requires_explicit_approval_and_fixed_broker(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'private.json'
   for change in ({'url':'http://example.com'},{'token':''},{'enabled':'true'},{'shell':True},{'approval_source':''}):
    path.write_text(json.dumps(config(**change)))
    with self.assertRaises(ValueError):load_config(path)
   path.write_text(json.dumps(config()));self.assertTrue(load_config(path)['enabled'])
 def test_client_has_no_unrestricted_path(self):
  client=Client(config())
  for path in ('/v1/deploy','http://example.com','/v1/jobs/../../config','/v1/shell','/v1/inspect?token=x'):
   with self.assertRaises(ValueError):client.request(path)

class WorkspaceTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.store=CompanionStore(now=lambda:NOW);self.addCleanup(self.store.close);self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  root=Path(self.temp.name);(root/'jarvis').mkdir();(root/'jarvis/workshop_fixture.py').write_text(SOURCE)
  self.owner=SimpleNamespace(profile=SimpleNamespace(_source_path=None),policy=SimpleNamespace(data={'enabled':True,'improvement_proposals':True}),store=self.store,now=lambda:NOW,clock=lambda:100,foreground=0,last_activity=0,provider=None,background=None)
  self.w=DevelopmentWorkspace(self.owner,config=config(),client=SimpleNamespace(request=self.request),source_root=root);self.addAsyncCleanup(self.w.close)
  self.answers=[];self.calls=[]
 def request(self,path,body=None):
  self.calls.append((path,body))
  if '/catalog/' in path:return {'functions':scope_catalog(snapshot(),'fixture')}
  if path=='/v1/inspect':return inspect_source(snapshot(),'fixture',body['path'],body['symbol'])
  return {'id':body['id'] if body else 'W'+'1'*12,'state':'queued'}
 async def model(self,*a,**kw):return self.answers.pop(0)
 def row(self,mode='inspect'):
  row={'id':'W'+'1'*12,'owner':sha('owner'),'scope':'fixture','problem':'Fix missing separators','mode':mode,'state':'selecting','created_at':NOW.isoformat(),'snapshot':snapshot()['digest'],'attempts':0};self.w.save(row);return row
 async def test_inspection_cites_exact_source_without_testing_or_mutation(self):
  self.answers=[{'index':0,'reason':'It joins the supplied list.'},{'summary':'It joins items without a separator.','line':2}];row=self.row()
  with patch.object(self.w,'model',side_effect=self.model):
   for _ in range(3):await self.w.step(row)
  self.assertEqual(row['state'],'inspection_complete');self.assertEqual(row['citations'][0]['module_sha256'],sha(SOURCE));self.assertFalse(any(p=='/v1/jobs' for p,_ in self.calls));self.assertEqual(self.store.revision,0)
 async def test_candidate_goes_through_structural_check_then_typed_job(self):
  self.answers=[{'index':0,'reason':'Join formatting.'},{'summary':'Add commas.','old':candidate()['old'],'new':candidate()['new']},{'test_source':TEST}];row=self.row('investigate')
  with patch.object(self.w,'model',side_effect=self.model):
   for _ in range(5):await self.w.step(row)
  self.assertEqual(row['state'],'testing');payload=next(body for path,body in self.calls if path=='/v1/jobs');validate_job(snapshot(),payload)
  self.assertNotIn('owner',self.w.public(row));self.assertNotIn('token',canonical(self.w.public(row)))
 async def test_changed_installed_source_stops_before_model_draft(self):
  row=self.row();row.update(state='inspecting',selected=scope_catalog(snapshot(),'fixture')[0]);(self.w.source_root/'jarvis/workshop_fixture.py').write_text('pass')
  await self.w.step(row);self.assertEqual(row['state'],'source_changed')
 async def test_malformed_model_or_off_function_patch_never_runs(self):
  row=self.row();self.answers=[{'index':999,'reason':'bad'},{'index':999,'reason':'bad'}]
  with patch.object(self.w,'model',side_effect=self.model):await self.w.step(row);await self.w.step(row)
  self.assertEqual(row['state'],'needs_review');self.assertFalse(any(p=='/v1/jobs' for p,_ in self.calls))
 async def test_identity_and_ha_permissions_are_separate(self):
  with calendar_scope({'actor':'read-only-owner','read':True,'write':False}),patch('jarvis.development_workspace.local_json',return_value={'action':'inspect','scope':'memory','case':'','problem_quote':'inspect your memory code'}):
   self.assertEqual((await self.w.handle('inspect your memory code'))['status'],'forbidden')
  self.assertFalse(self.w.jobs())
  with calendar_scope({'actor':'unauthorised','read':False,'write':False}):self.assertEqual((await self.w.handle('show development workspace'))['status'],'forbidden')
 async def test_cancel_only_creator_and_cannot_enable_deployment(self):
  row=self.row();row['state']='drafting';self.w.save(row)
  with calendar_scope({'actor':'other','read':True,'write':True}):self.assertEqual((await self.w.handle('cancel '+row['id']))['status'],'forbidden')
  with calendar_scope({'actor':'owner','read':True,'write':True}):
   await self.w.handle('cancel '+row['id']);self.assertEqual(self.w.jobs()[0]['state'],'cancelled')
   out=await self.w.handle('deploy '+row['id']);self.assertIn('independently reviewed',out['message'])
 async def test_conversation_cancels_background_work_without_erasing_stage(self):
  row=self.row()
  async def wait():await asyncio.sleep(20)
  self.w.work=asyncio.create_task(wait());await asyncio.sleep(0);self.w.interrupt();await asyncio.gather(self.w.work,return_exceptions=True)
  self.assertTrue(self.w.work.cancelled());self.assertEqual(self.w.jobs()[0]['state'],'selecting')
 async def test_cases_survive_reopen_and_summary_omits_raw_runner_output(self):
  row=self.row();row.update(result={'review_required':True,'phases':{'candidate_suite':{'passed':True,'output':'UNTRUSTED LOG','tests_reported':1}}});self.w.save(row)
  other=DevelopmentWorkspace(self.owner,config=config(),client=self.w.client);self.assertEqual(other.jobs()[0]['id'],row['id']);self.assertNotIn('UNTRUSTED LOG',canonical(other.project()));self.assertFalse(self.store.memories())
