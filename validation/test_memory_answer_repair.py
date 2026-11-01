"""Reproduce leaked metadata without weakening factual grounding or retries."""
import unittest
from unittest.mock import AsyncMock,patch
from jarvis.companion_memory import answer_memory,MemoryNoMatch

class MemoryAnswerRepairTests(unittest.IsolatedAsyncioTestCase):
 def row(self,**kw):
  return {'id':'Mabcdef12','kind':'preference','subjects':['benny'],'quote':'Benny prefers the train to the airport.','interpretation':'','confidence':'user_reported','anchor':'2026-11-01','currently_applicable':True,**kw}
 def answer(self,text,ids=None):return {'answer':text,'memory_ids':['Mabcdef12'] if ids is None else ids}
 async def run_answer(self,responses,**kw):
  with patch('jarvis.companion_memory.local_json',new=AsyncMock(side_effect=responses)) as model:
   result=await answer_memory(None,'What does Benny prefer for airport transport?',[self.row(**kw)],{'benny':'Benny'})
   return result,model
 async def test_reproduced_id_leak_gets_one_clean_rewrite_and_grounding_review(self):
  result,model=await self.run_answer([self.answer('Benny prefers the train, per memory Mabcdef12.'),self.answer('Benny prefers taking the train to the airport.'),{'supported':True}])
  self.assertEqual(result,('Benny prefers taking the train to the airport.',['Mabcdef12']))
  self.assertEqual(model.await_count,3)
  rewrite=model.await_args_list[1]
  self.assertIn('memory_ids',rewrite.args[1]);self.assertIn('memories',rewrite.args[2])
 async def test_all_letter_uppercase_and_unknown_internal_tokens_are_also_rewritten(self):
  for token in ('Mabcdefab','MABCDEFAB','M12345678'):
   with self.subTest(token=token):
    result,model=await self.run_answer([self.answer('Benny prefers the train ('+token+').'),self.answer('Benny prefers the train.'),{'supported':True}])
    self.assertNotIn(token,result[0]);self.assertEqual(model.await_count,3)
 async def test_repeated_leak_is_rejected_after_two_generations(self):
  fake=AsyncMock(return_value=self.answer('Benny prefers the train: Mabcdef12.'))
  with patch('jarvis.companion_memory.local_json',new=fake):
   with self.assertRaises(ValueError):await answer_memory(None,'Transport?',[self.row()],{'benny':'Benny'})
  self.assertEqual(fake.await_count,2)
 async def test_clean_first_answer_keeps_normal_call_count(self):
  result,model=await self.run_answer([self.answer('Benny prefers the train.'),{'supported':True}])
  self.assertEqual(result[0],'Benny prefers the train.');self.assertEqual(model.await_count,2)
 async def test_rewrite_cannot_add_an_unsubstantiated_number(self):
  with self.assertRaises(ValueError):await self.run_answer([self.answer('Benny prefers the train Mabcdef12.'),self.answer('The journey takes 999 minutes.')])
 async def test_rewrite_cannot_upgrade_history_or_inference(self):
  for kw in ({'currently_applicable':False},{'kind':'hint','interpretation':'Benny might prefer the train.'}):
   with self.subTest(kw=kw):
    with self.assertRaises(ValueError):await self.run_answer([self.answer('Benny prefers the train Mabcdef12.'),self.answer('Benny prefers the train.')],**kw)
 async def test_rewrite_still_needs_semantic_support(self):
  with self.assertRaises(MemoryNoMatch):await self.run_answer([self.answer('Benny prefers the train Mabcdef12.'),self.answer('Benny prefers flying.'),{'supported':False}])
 async def test_rewrite_cannot_cite_an_unknown_record(self):
  with self.assertRaises(ValueError):await self.run_answer([self.answer('Benny prefers the train Mabcdef12.'),self.answer('Benny prefers the train.',['Munknown1'])])
 async def test_empty_support_and_malformed_output_fail_closed(self):
  for bad in (self.answer('Nothing to recall.',[]),{'answer':'No citation'},self.answer('Benny prefers the train.','Mabcdef12')):
   with self.subTest(bad=bad):
    with self.assertRaises(ValueError):await self.run_answer([bad])
 async def test_legitimate_numbers_are_preserved(self):
  result,model=await self.run_answer([self.answer('Benny prefers a 2-day trip.'),{'supported':True}],quote='Benny prefers a 2-day trip.')
  self.assertIn('2-day',result[0]);self.assertEqual(model.await_count,2)
