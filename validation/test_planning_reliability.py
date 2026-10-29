"""Overlaps, after-hours plans, sync receipts and sparse-calendar conclusions."""
import asyncio,json,unittest
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
import test_household_agenda as agenda_fixture
from jarvis.calendar_evidence import calendar_evidence
from jarvis.calendar_freshness import receipt,collect,current_health,SOURCES
from jarvis.household_briefing import Brief
from jarvis.household_thinking import HouseholdThinking

NOW=datetime(2026,10,29,12,tzinfo=timezone.utc)
def raw(status='ok',**kwargs):
 value={'v':1,'attempt':int(NOW.timestamp()),'success':int(NOW.timestamp()),'failure':None,'status':status};value.update(kwargs);return json.dumps(value)

class ReceiptTests(unittest.IsolatedAsyncioTestCase):
 async def test_success_failure_stale_and_incomplete_have_distinct_meaning(self):
  good=receipt(raw(),NOW);self.assertEqual(good['status'],'fresh');self.assertIsNone(good['last_failure'])
  self.assertEqual(receipt(raw('failed',success=int(NOW.timestamp())-300,failure=int(NOW.timestamp())),NOW)['status'],'failed')
  self.assertEqual(receipt(raw(),NOW+timedelta(seconds=2101))['status'],'stale')
  self.assertEqual(receipt(raw('refreshing',success=None),NOW+timedelta(seconds=91))['status'],'incomplete')
  self.assertEqual(current_health({'work':good},NOW+timedelta(hours=1))['work']['status'],'stale')
 async def test_missing_malformed_future_and_false_success_are_never_fresh(self):
  for value in (None,'unavailable','{}',raw(success=None),raw(attempt=True),raw(attempt=int(NOW.timestamp())+61,success=int(NOW.timestamp())+61),raw('failed',failure=None)):
   self.assertEqual(receipt(value,NOW)['status'],'unknown',value)
 async def test_old_client_has_no_fabricated_health_and_failures_are_unknown(self):
  self.assertEqual(await collect(object(),['work'],NOW),{})
  client=SimpleNamespace(get_calendar_health=AsyncMock(side_effect=TimeoutError()))
  result=await collect(client,['work'],NOW);self.assertEqual(result['work']['status'],'unknown');self.assertIsNone(result['work']['last_success'])
 async def test_optional_missing_helpers_do_not_disable_existing_working_calendar_clients(self):
  helper=SOURCES['work'][1];client=SimpleNamespace(get_calendar_health=AsyncMock(return_value={helper:{'receipt':None,'source_state':'off','monitoring_enabled':False}}))
  row=(await collect(client,['work'],NOW))['work'];self.assertEqual(row['status'],'not_configured');self.assertIsNone(row['last_success'])

 async def test_native_source_unavailable_overrides_a_previous_success_without_fake_failure_time(self):
  helper=SOURCES['work'][1];client=SimpleNamespace(get_calendar_health=AsyncMock(return_value={helper:{'receipt':raw(),'source_state':'unavailable'}}))
  row=(await collect(client,['work'],NOW))['work'];self.assertEqual(row['status'],'unavailable');self.assertIsNotNone(row['last_success']);self.assertIsNone(row['last_failure'])


class EvidenceTests(unittest.TestCase):
 def test_routine_owner_loop_does_not_break_same_person_or_cross_person_overlap(self):
  p=SimpleNamespace(_data={'members':[{'id':'mia','preferred_name':'Mia'},{'id':'benny','preferred_name':'Benny'}]})
  base={'start':NOW,'end':NOW+timedelta(hours=1),'all_day':False,'title':'Practice','source':'family','owners':['mia']}
  events=[base,{**base,'title':'Dentist','start':NOW+timedelta(minutes=20)},{**base,'title':'Work meeting','source':'work','owners':['benny'],'start':NOW+timedelta(minutes=30)}]
  snapshot={'planning':{'days':[{'date':'2026-10-29','cards':[{'title':'Mia · usual school','lines':['08:15–12:50']}]}]}}
  evidence=calendar_evidence(p,Brief('all','2026-10-29','2026-10-30'),events,snapshot,['family','work'],[],NOW)
  overlaps=[f for f in evidence['facts'] if f['kind']=='overlap'];self.assertEqual(len(overlaps),1);self.assertEqual(overlaps[0]['owners'],['mia'])
 def test_recorded_calendar_load_does_not_allow_a_whole_day_judgement(self):
  p=SimpleNamespace(_data={'members':[{'id':'benny','preferred_name':'Benny'}]})
  event={'start':NOW,'end':NOW+timedelta(minutes=30),'all_day':False,'title':'Meeting','source':'work','owners':['benny']}
  e=calendar_evidence(p,Brief('benny','2026-10-29','2026-10-30'),[event],{'planning':{'days':[]}},['work'],[],NOW)
  e['facts'].append({'id':'L1','kind':'calendar_load','owners':['benny'],'text':'Relatively light recorded appointment load.'})
  for text in ('Benny has a scheduled meeting at12:00. His day is relatively light.','His day looks quiet.','His afternoon looks relatively free.','Based on the recorded appointments, his day seems easy.'):
   with self.assertRaises(ValueError):HouseholdThinking.validate_compact(json.dumps({'answer':text}),e,None)
  self.assertIn('recorded appointment load',HouseholdThinking.validate_compact(json.dumps({'answer':'The recorded appointment load looks relatively light.'}),e,None))

class ReliabilityAgendaTests(unittest.IsolatedAsyncioTestCase):
 setUpBase=agenda_fixture.AgendaTests.setUpBase
 def setUp(self):
  agenda_fixture.AgendaTests.setUp(self)
  self.container.household_thinking.reader.now=lambda:self.time[0]
  original=self.c.get_household_today
  async def routines(*a,**kw):
   data=await original(*a,**kw);data['planning']['generated_on']=self.time[0].date().isoformat();return data
  self.c.get_household_today=routines
 async def test_all_events_ended_today_yields_a_valid_remaining_day_instead_of_a_failure(self):
  self.time[0]=self.time[0].replace(day=29,hour=22)
  await self.agenda.refresh();today=self.agenda.project()['days'][0]
  self.assertEqual(today['state'],'ready');self.assertEqual(len(today['people']),4)
  for p in today['people']:self.assertEqual(p['event_count'],0);self.assertFalse(p['departures']);self.assertIn('No further appointments',p['summary'])
 async def test_failed_refresh_withholds_cached_source_events(self):
  self.c.get_calendar_health=AsyncMock(return_value={row[1]:raw('failed',success=int(NOW.timestamp())-100,failure=int(NOW.timestamp())) for row in SOURCES.values()})
  # Anchor the helper receipt to this fixture's actual current time.
  stamp=int(self.time[0].timestamp());self.c.get_calendar_health.return_value={row[1]:json.dumps({'v':1,'attempt':stamp,'success':stamp-100,'failure':stamp,'status':'failed'}) for row in SOURCES.values()}
  await self.agenda.refresh();view=self.agenda.project();self.assertEqual(view['status'],'partial')
  self.assertTrue(all(p['event_count']==0 for d in view['days'] for p in d['people']));self.assertEqual(view['source_health']['family']['status'],'failed')
 async def test_excluded_calendar_has_no_receipt_read_or_exposed_health(self):
  reader=self.container.household_thinking.reader;reader.allowed=frozenset({'calendar.familiekalender'})
  stamp=int(self.time[0].timestamp());helper=SOURCES['family'][1]
  self.c.get_calendar_health=AsyncMock(return_value={helper:json.dumps({'v':1,'attempt':stamp,'success':stamp,'failure':None,'status':'ok'})})
  result=await reader.handle('household',None,resolved=Brief('all','2026-10-29','2026-10-30'),structured_only=True)
  self.c.get_calendar_health.assert_awaited_once_with([helper]);self.assertEqual(set(result['evidence']['source_health']),{'family'})

 async def test_success_timestamp_refresh_does_not_repeat_unchanged_model_work(self):
  stamp=int(self.time[0].timestamp())
  self.c.get_calendar_health=AsyncMock(return_value={row[1]:json.dumps({'v':1,'attempt':stamp,'success':stamp,'failure':None,'status':'ok'}) for row in SOURCES.values()})
  await self.agenda.refresh();count=self.model_calls;self.time[0]+=timedelta(minutes=15);stamp=int(self.time[0].timestamp())
  self.c.get_calendar_health.return_value={row[1]:json.dumps({'v':1,'attempt':stamp,'success':stamp,'failure':None,'status':'ok'}) for row in SOURCES.values()}
  await self.agenda.refresh();self.assertEqual(self.model_calls,count);self.assertEqual(self.agenda.project()['source_health']['work']['last_success'],self.time[0].astimezone(timezone.utc).isoformat())

if __name__=='__main__':unittest.main()
