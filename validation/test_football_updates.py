import asyncio,json,unittest
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from jarvis.football_updates import FootballUpdates,matches,table,headlines
from jarvis.companion_store import CompanionStore
import xml.etree.ElementTree as ET
NOW=datetime(2026,10,31,8,tzinfo=timezone.utc)
def event(id='1',status='STATUS_SCHEDULED',completed=False,when='2026-10-31T12:30Z',score=('0','0')):
 sides=[{'team':{'id':'360','displayName':'Manchester United'},'homeAway':'home','score':{'displayValue':score[0]}},{'team':{'id':'363','displayName':'Chelsea'},'homeAway':'away','score':{'displayValue':score[1]}}]
 return {'id':id,'date':when,'timeValid':True,'league':{'name':'Premier League'},'competitions':[{'timeValid':True,'competitors':sides,'status':{'type':{'name':status,'description':'Full Time' if completed else 'Scheduled','completed':completed,'state':'post' if completed else 'pre'}}}]}
def schedule(events=()):return {'status':'success','team':{'id':'360','displayName':'Manchester United'},'season':{'year':2026},'events':list(events)}
def league():
 return {'children':[{'standings':{'season':2026,'entries':[{'team':{'id':'360' if i==5 else str(1000+i),'displayName':'Manchester United' if i==5 else 'Club '+str(i)},'stats':[{'name':k,'displayValue':str(v)} for k,v in dict(rank=i+1,points=20-i,gamesPlayed=8,wins=4,ties=2,losses=2,pointDifferential=2).items()]} for i in range(20)]}}]}
class FootballTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.time=[NOW];self.clock=[0.];self.store=CompanionStore(now=lambda:self.time[0]);self.addCleanup(self.store.close)
  self.owner=SimpleNamespace(profile=SimpleNamespace(),policy=SimpleNamespace(data={'enabled':True}),store=self.store,now=lambda:self.time[0],clock=lambda:self.clock[0],foreground=0,container=SimpleNamespace(home_assistant=SimpleNamespace()))
  self.data={'fixtures':schedule([event()]),'results':schedule(),'standings':league(),'news':ET.fromstring('<rss><channel/></rss>')}
  self.f=FootballUpdates(self.owner,fetcher=lambda k:self.data[k]);self.f.config={'enabled':True,'final_scores':True,'activated_at':NOW.isoformat()};self.f.notify=AsyncMock()
 async def test_daily_silent_delivery_and_restart_dedupe(self):
  await self.f.tick();self.assertEqual(self.f.notify.await_count,1);self.assertIn('daily',self.f.notify.call_args.args[0]);self.assertEqual(self.f.project()['briefs'][0]['title'],'Manchester United · 31 October')
  other=FootballUpdates(self.owner,fetcher=lambda k:self.data[k]);other.config=self.f.config;other.notify=AsyncMock();await other.tick();other.notify.assert_not_awaited()
 async def test_final_only_once_and_corrected_result_updates_same_notification(self):
  await self.f.tick();self.f.notify.reset_mock();self.time[0]=NOW+timedelta(hours=7);self.clock[0]+=1000
  self.data['results']=schedule([event(status='STATUS_FULL_TIME',completed=True,score=('2','1'))]);await self.f.tick();self.f.notify.assert_awaited_once();key=self.f.notify.call_args.args[0]
  self.clock[0]+=1000;await self.f.tick();self.assertEqual(self.f.notify.await_count,1)
  self.data['results']=schedule([event(status='STATUS_FULL_TIME',completed=True,score=('3','1'))]);self.clock[0]+=1000;await self.f.tick();self.assertEqual(self.f.notify.await_count,2);self.assertEqual(self.f.notify.call_args.args[0],key)
 async def test_initial_old_scores_not_sent_and_outage_not_invented(self):
  self.data['results']=schedule([event(status='STATUS_FULL_TIME',completed=True,when='2026-10-30T12:30Z')]);await self.f.tick();self.assertEqual(self.f.notify.await_count,1)
  self.f.notify.reset_mock();self.time[0]+=timedelta(days=1);self.clock[0]+=90000
  self.data['results']=schedule([event(status='STATUS_FULL_TIME',completed=True,when='2026-10-30T12:30Z')]);await self.f.tick();self.assertEqual(self.f.notify.await_count,1);self.assertIn('daily',self.f.notify.call_args.args[0])
 async def test_failed_delivery_not_marked_and_retry_has_stable_id(self):
  self.f.notify.side_effect=TimeoutError()
  with self.assertRaises(TimeoutError):await self.f.tick()
  self.assertIsNone(self.f.state()['daily']);key=self.f.notify.call_args.args[0];self.f.notify.side_effect=None;self.clock[0]+=1000;await self.f.tick();self.assertEqual(self.f.notify.call_args.args[0],key)
 async def test_partial_failure_withholds_stale_values(self):
  await self.f.refresh();self.assertTrue(self.f.current('fixtures'))
  self.data['fixtures']={'status':'success','team':{'id':'382'}};self.clock[0]+=1000;await self.f.refresh();self.assertIsNone(self.f.current('fixtures'));self.assertIn('source unavailable',' '.join(self.f.brief()['lines']));self.assertFalse(any('host Chelsea' in x for x in self.f.brief()['lines']))
  self.time[0]+=timedelta(minutes=11);self.assertIsNone(self.f.current('standings'))
 def test_wrong_team_season_and_incomplete_table_rejected(self):
  for d in [dict(schedule(),team={'id':'382'}),dict(schedule(),season={'year':2025})]:
   with self.assertRaises(ValueError):matches(d,NOW)
  d=league();d['children'][0]['standings']['entries'][0]['stats'][-1]['displayValue']='+2';self.assertEqual(len(table(d,NOW)),20)
  d['children'][0]['standings']['entries'].pop()
  with self.assertRaises(ValueError):table(d,NOW)
 def test_pending_live_postponed_abandoned_and_future_not_final(self):
  for name,complete in [('STATUS_SCHEDULED',False),('STATUS_IN_PROGRESS',False),('STATUS_POSTPONED',True),('STATUS_ABANDONED',True),('STATUS_CANCELED',True)]:self.assertFalse(matches(schedule([event(status=name,completed=complete)]),NOW+timedelta(hours=7))[0]['final'])
  self.assertFalse(matches(schedule([event(status='STATUS_FULL_TIME',completed=True)]),NOW)[0]['final'])
 def test_news_team_filter_age_sources_and_womens_team(self):
  titles=['Man Utd manager latest','Manchester City latest','Man Utd women win','Leeds striker update']
  xml='<rss><channel>'+''.join('<item><title>'+t+'</title><link>https://www.bbc.co.uk/sport/1</link><pubDate>Fri, 30 Oct 2026 10:00:00 GMT</pubDate></item>' for t in titles)+'</channel></rss>'
  self.assertEqual([n['title'] for n in headlines(ET.fromstring(xml),NOW)],['Man Utd manager latest'])
 def test_norway_time_dst_and_unconfirmed_kickoff(self):
  self.f.cache['fixtures']={'checked_at':NOW.isoformat(),'data':matches(schedule([event()]),NOW)};self.assertIn('13:30 CET',' '.join(self.f.brief('fixtures')['lines']))
  self.f.cache['fixtures']['data'][0]['time_confirmed']=False;self.assertNotIn('13:30',' '.join(self.f.brief('fixtures')['lines']))
 async def test_daily_time_not_delayed_by_recent_poll(self):
  self.time[0]=NOW.replace(hour=6,minute=59);await self.f.tick();self.f.notify.assert_not_awaited()
  self.time[0]=NOW.replace(hour=7,minute=0);self.clock[0]+=60;await self.f.tick();self.f.notify.assert_awaited_once()
 async def test_no_delivery_when_disabled(self):
  self.f.config['enabled']=False;await self.f.tick();self.f.notify.assert_not_awaited()
