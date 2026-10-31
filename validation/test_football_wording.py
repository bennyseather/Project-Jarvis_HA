import asyncio,json,unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from datetime import timedelta
import test_football_updates as fixtures
from jarvis.football_updates import matches,table,headlines
from jarvis.football_wording import board,validate,compose
class WordingTests(unittest.IsolatedAsyncioTestCase):
 setUp=fixtures.FootballTests.setUp
 async def prepared(self):
  self.time[0]=fixtures.NOW+timedelta(hours=8)
  self.data['results']=fixtures.schedule([fixtures.event(status='STATUS_FULL_TIME',completed=True,score=('0','2'))])
  self.data['fixtures']=fixtures.schedule([fixtures.event(id='2',when='2026-11-03T20:00Z'),fixtures.event(id='3',when='2026-11-08T16:30Z')])
  await self.f.refresh();return board(self.f)
 async def test_default_is_one_result_fixture_position_and_headline(self):
  facts=await self.prepared();kinds=[u['kind'] for u in facts['units']];self.assertEqual(kinds,['result','standing','fixture']);self.assertIn('2–0 defeat at home to Chelsea',facts['fallback']);self.assertIn('6th in the Premier League with 15 points from 8 matches',facts['fallback']);self.assertIn('21:00 CET',facts['fallback']);self.assertNotIn('Sunday 8',facts['fallback']);self.assertLessEqual(len(facts['fallback'].split()),100)
 async def test_result_orientation_home_away_win_and_draw(self):
  for score,expected in [(('3','1'),'3–1 win at home to Chelsea'),(('0','2'),'2–0 defeat at home to Chelsea'),(('1','1'),'1–1 draw at home to Chelsea')]:
   await self.prepared();self.f.cache['results']['data'][0]['score']=list(score);self.assertIn(expected,board(self.f,'results')['fallback'])
  self.f.cache['results']['data'][0].update(home='Chelsea',away='Manchester United',score=['2','0']);self.assertIn('2–0 defeat away to Chelsea',board(self.f,'results')['fallback'])
 async def test_draft_retains_roles_numbers_and_next_match(self):
  facts=await self.prepared();good=facts['fallback'];self.assertEqual(validate({'answer':good},facts),good)
  for changed in (good.replace('2–0 defeat','2–0 win'),good.replace('6th','5th'),good.replace('21:00','20:00'),good+' They signed a striker for 80 million.',good.replace('at home to Chelsea','away to Chelsea')):
   with self.assertRaises(ValueError):validate({'answer':changed},facts)
 async def test_contradiction_rejected_by_independent_review(self):
  facts=await self.prepared();draft=facts['fallback']+' United have not lost.'
  with patch('jarvis.football_wording.local_json',new=AsyncMock(side_effect=[{'answer':draft},{'grounded':False,'complete':True,'natural':True,'news_attributed':True}])):
   r=await compose(object(),facts,lambda:True)
  self.assertFalse(r['language_model_composition']);self.assertEqual(r['answer'],facts['fallback']);self.assertEqual(r['fallback_reason'],'review')
 async def test_model_timeout_or_changed_facts_uses_short_fallback(self):
  facts=await self.prepared()
  for side in [TimeoutError(),[{'answer':facts['fallback']},{'grounded':True,'complete':True,'natural':True,'news_attributed':True}]]:
   with patch('jarvis.football_wording.local_json',new=AsyncMock(side_effect=side)):
    r=await compose(object(),facts,lambda:False)
   self.assertFalse(r['language_model_composition']);self.assertEqual(r['answer'],facts['fallback'])
 async def test_partial_failed_sources_do_not_reuse_previous_facts(self):
  await self.prepared();self.f.errors=['standings source unavailable; previous data is withheld.'];facts=board(self.f);self.assertNotIn('6th',facts['fallback']);self.assertIn('league table',facts['coverage']);self.assertEqual(len([u for u in facts['units'] if u['kind']=='fixture']),1)
 async def test_full_table_and_fixtures_available_only_explicitly(self):
  await self.prepared();short=await self.f.present('standings');full=await self.f.present('standings',expanded=True);self.assertEqual(len(short['lines']),1);self.assertGreater(len(full['lines']),15);self.assertTrue(full['expanded'])
 async def test_sources_changed_during_wording_rebuilds_fallback(self):
  await self.prepared()
  async def changed(provider,facts,valid):
   self.f.errors=['results source unavailable; previous data is withheld.'];return {'answer':facts['fallback'],'language_model_composition':True}
  with patch('jarvis.football_wording.compose',side_effect=changed):b=await self.f.present()
  self.assertFalse(b['language_model_composition']);self.assertNotIn('2–0',b['lines'][0]);self.assertIn('latest result',b['lines'][0])
 async def test_style_migration_replaces_daily_without_replaying_scores(self):
  await self.f.tick();s=self.f.state();s.pop('style_revision');s['seen']['past']='2:0';self.f.save(s);self.f.notify.reset_mock();self.clock[0]+=30;await self.f.tick();self.f.notify.assert_awaited_once();self.assertEqual(self.f.notify.call_args.args[0],'jarvis_mu_daily');self.assertEqual(self.f.state()['seen']['past'],'2:0');self.assertEqual(len(self.f.state()['briefs']),1);self.assertEqual(self.f.state()['style_revision'],2)
 async def test_unconfirmed_kickoff_stays_unconfirmed(self):
  await self.prepared();self.f.cache['fixtures']['data'][0]['time_confirmed']=False;facts=board(self.f,'fixtures');self.assertIn('kick-off time unconfirmed',facts['fallback']);self.assertNotIn('21:00',facts['fallback'])
 async def test_news_cannot_invent_article_details_or_drop_uncertainty(self):
  facts=await self.prepared();facts['units'].append({'kind':'news','headline':'What Howe could bring to Man Utd','basis':'BBC headline only'});facts['required_phrases'].append('BBC')
  for text in [facts['fallback']+' BBC reports Howe could improve his management style and integration.',facts['fallback']+' BBC says Howe will bring Man Utd.']:
   with self.assertRaises(ValueError):validate({'answer':text},facts)
 async def test_no_unsupplied_club_or_bbc_story_even_if_model_review_approves(self):
  facts=await self.prepared()
  for text in [facts['fallback']+' Their next match is against Brighton & Hove Albion.',facts['fallback']+' BBC reports they could climb the table.']:
   with self.assertRaises(ValueError):validate({'answer':text},facts)
 async def test_valid_model_body_survives_rejected_news_detail(self):
  facts=await self.prepared();facts['units'].append({'kind':'news','headline':'What Howe could bring to Man Utd','basis':'BBC headline only'});facts['required_phrases'].append('BBC')
  draft=facts['fallback']+' BBC says Howe could bring new ideas and management style.'
  with patch('jarvis.football_wording.local_json',new=AsyncMock(side_effect=[{'answer':draft},{'grounded':True,'complete':True,'natural':True,'news_attributed':True}])):
   r=await compose(object(),facts,lambda:True)
  self.assertTrue(r['language_model_composition']);self.assertTrue(r['news_fallback']);self.assertNotIn('management style',r['answer']);self.assertIn('BBC’s latest headline',r['answer'])
 async def test_accept_reviewed_natural_output(self):
  facts=await self.prepared();draft=facts['fallback'].replace('United’s latest result was','United are coming off').replace('United are currently','They’re currently')
  with patch('jarvis.football_wording.local_json',new=AsyncMock(side_effect=[{'answer':draft},{'grounded':True,'complete':True,'natural':True,'news_attributed':True}])):
   r=await compose(object(),facts,lambda:True)
  self.assertTrue(r['language_model_composition']);self.assertEqual(r['answer'],draft)
