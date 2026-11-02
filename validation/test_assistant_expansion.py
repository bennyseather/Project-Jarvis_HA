"""Fictional multi-turn, validity, source-change and performance contracts."""
import asyncio,json,unittest
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from jarvis.companion_memory import date_scope,MemoryLearner
from jarvis.memory_validity import temporal_phrase
from jarvis.household_planning import resolve_dates,DATE_PATTERN
from jarvis.conversation_topics import RETURN,resumed_request
from jarvis.request_timing import RequestTiming,session_slot,RequestBusy,timing_question
from jarvis.planning_changes import PlanningChanges,lines
from jarvis.preparation_interpretation import at_venue_items
from jarvis.issue_triage import symptom,inspection_problem
from jarvis.companion_store import CompanionStore
import test_planning_followthrough as follow
from test_companion_memory import model_item,context

class ValidityTests(unittest.TestCase):
 def test_norwegian_days_and_ranges_are_code_resolved(self):
  for phrase,expected in [('i morgen',('2026-11-03','2026-11-04')),('neste torsdag',('2026-11-12','2026-11-13')),('denne helgen',('2026-11-07','2026-11-09')),('neste uke',('2026-11-09','2026-11-16'))]:
   self.assertEqual(resolve_dates(phrase,'2026-11-02'),expected);self.assertIsNotNone(DATE_PATTERN.search(phrase))
 def test_bounded_duration_keeps_current_validity(self):
  for phrase in ('for two weeks','for the next two weeks','i to uker'):
   a,b,bad=date_scope(phrase,'2026-11-02');self.assertFalse(bad);self.assertTrue(a.startswith('2026-11-02'));self.assertTrue(b.startswith('2026-11-16'))
 def test_through_day_covers_now_through_inclusive_day(self):
  for phrase in ('through Friday','until the end of Friday','til og med fredag'):
   a,b,bad=date_scope(phrase,'2026-11-02');self.assertFalse(bad);self.assertTrue(a.startswith('2026-11-02'));self.assertTrue(b.startswith('2026-11-07'))
 def test_bare_until_is_not_silently_moved_to_friday(self):
  self.assertEqual(date_scope('until Friday','2026-11-02'),(None,None,True))
 def test_explicit_interval_and_invalid_range(self):
  a,b,bad=date_scope('from Monday through Friday','2026-11-02');self.assertFalse(bad);self.assertTrue(b.startswith('2026-11-07'))
  self.assertEqual(date_scope('for 999 weeks','2026-11-02'),(None,None,True))
 def test_temporal_phrase_is_original_source_span(self):
  for value in ('Mia has her instrument at school until Friday.','Benny takes the bus for two weeks.','Mia har instrumentet på skolen til og med fredag.'):
   phrase=temporal_phrase(value);self.assertIsNotNone(phrase);self.assertIn(phrase,value)
 def test_norwegian_and_punctuated_topic_returns(self):
  for value in ('Tilbake til Mias øving, hva trenger hun?','La oss gå tilbake til Mia: hva skal hun ta med?','Back to Mia; what should she bring?'):
   self.assertTrue(RETURN.search(value));self.assertNotEqual(resumed_request(value),value)
  self.assertFalse(RETURN.search('What is a return flight?'))
 def test_report_symptoms_are_not_root_cause_claims(self):
  for value,expected in [('That answer used the wrong date.','reported_timing_problem'),('Make that shorter does not work.','reported_wording_problem'),('You used the wrong person.','reported_continuity_problem')]:
   self.assertEqual(symptom(value),expected);self.assertIn('not a proven root cause',inspection_problem(expected))

class TimingTests(unittest.IsolatedAsyncioTestCase):
 def test_status_query_does_not_steal_preference_or_external_question(self):
  self.assertTrue(timing_question('What are your response times?'));self.assertTrue(timing_question('How fast do you respond?'));self.assertFalse(timing_question('Benny prefers quick response times.'));self.assertFalse(timing_question('Remember that I prefer quick response times.'));self.assertFalse(timing_question('What are visa response times?'))
 async def test_lock_timeout_is_bounded_and_does_not_release_another_owner(self):
  lock=asyncio.Lock();await lock.acquire()
  with self.assertRaises(RequestBusy):
   async with session_slot(lock,timeout=.01):self.fail('Must not enter')
  self.assertTrue(lock.locked());lock.release()
 async def test_cancelled_body_releases_lock(self):
  lock=asyncio.Lock()
  async def wait():
   async with session_slot(lock):await asyncio.Event().wait()
  task=asyncio.create_task(wait());await asyncio.sleep(.01);task.cancel();await asyncio.gather(task,return_exceptions=True);self.assertFalse(lock.locked())
 def test_metrics_are_bounded_and_contain_no_prompts_or_identity(self):
  clock=[0.];m=RequestTiming(lambda:clock[0]);self.assertEqual(m.project()['sample_count'],0)
  for n in range(120):clock[0]=float(n);m.record(0.,'success')
  data=m.project();self.assertEqual(data['sample_count'],100);self.assertEqual(data['last_seconds'],119);self.assertGreaterEqual(data['p95_seconds'],data['median_seconds']);self.assertNotIn('question',repr(data));self.assertNotIn('actor',repr(data))

class ChangeTests(unittest.TestCase):
 def setUp(self):
  self.now=[datetime(2026,11,2,10,tzinfo=timezone.utc)];self.store=CompanionStore(now=lambda:self.now[0]);self.addCleanup(self.store.close)
  self.owner=SimpleNamespace(store=self.store,now=lambda:self.now[0],container=SimpleNamespace(proactive_allowed_entities=('calendar.fixture',)))
  self.j=PlanningChanges(self.owner);self.items={'p':{'id':'p','title':'Band rehearsal','activity':'band rehearsal','person':'mia','name':'Mia','start':'2026-11-03T17:00:00+01:00','end':'2026-11-03T18:00:00+01:00','venue':'Elm School','venue_basis':'calendar','gaps':[],'followthrough':{'remaining':['instrument','sheet music'],'reported_ready':[]}}}
 def test_first_check_is_baseline_and_reads_do_not_write(self):
  self.j.observe(self.items);before='\n'.join(self.store.db.iterdump());data=self.j.project(True,items=self.items);self.assertEqual(data['status'],'baseline');self.assertIn('first complete',lines(data)[0]);self.assertEqual(before,'\n'.join(self.store.db.iterdump()))
 def test_time_and_readiness_changes_are_current_and_deduplicated(self):
  self.j.observe(self.items);self.items['p']['start']='2026-11-03T18:00:00+01:00';self.items['p']['end']='2026-11-03T19:00:00+01:00';self.items['p']['followthrough']={'remaining':['sheet music'],'reported_ready':['instrument']};self.j.observe(self.items);self.j.observe(self.items)
  data=self.j.project(True,items=self.items);self.assertEqual(len(data['changes']),1);text=' '.join(lines(data));self.assertIn('18:00',text);self.assertIn('reported ready: instrument',text);self.assertIn('still to check: sheet music',text)
 def test_unrecorded_or_incomplete_new_view_cannot_show_old_changes(self):
  self.j.observe(self.items);self.items['p']['venue']='Other School';self.assertEqual(self.j.project(True,items=self.items)['status'],'unavailable');self.assertEqual(self.j.project(False)['changes'],[])
 def test_partial_failure_is_not_a_cancellation_and_completed_items_do_not_alert(self):
  self.j.observe(self.items);self.assertEqual(self.j.project(False)['changes'],[]);self.assertIn('another check',lines(self.j.project(False))[0]);self.now[0]+=timedelta(days=2);self.j.observe({});self.assertEqual(self.j.project(True)['changes'],[])
 def test_removed_upcoming_item_is_not_claimed_cancelled(self):
  self.j.observe(self.items);self.j.observe({});text=' '.join(lines(self.j.project(True)));self.assertIn('does not establish a cancellation',text)
 def test_scope_and_generation_change_discards_previous_comparison(self):
  self.j.observe(self.items);self.owner.container.proactive_allowed_entities=();self.assertEqual(self.j.project(True)['status'],'unavailable');self.j.observe(self.items);self.assertEqual(self.j.project(True)['status'],'baseline')
 def test_filters_and_restart_retention(self):
  self.j.observe(self.items);self.items['p']['venue']='Other Hall';self.j.observe(self.items);again=PlanningChanges(self.owner);self.assertEqual(len(again.project(True,['mia'])['changes']),1);self.assertFalse(again.project(True,['benny'])['changes'])
 def test_malformed_nested_journal_is_withheld_and_rebuilt(self):
  self.j.observe(self.items)
  for mutate in (lambda d:d['snapshot']['p'].update(end='invalid'),lambda d:d.update(changes=[{}]),lambda d:d.update(checks='two'),lambda d:d.update(checked_at='2026-11-02T10:00:00')):
   original=self.j.read();broken=deepcopy(original);mutate(broken)
   with self.store.db:self.store.db.execute('UPDATE assistant_state SET value=? WHERE key=?',(json.dumps(broken),'planning_change_journal'))
   self.assertEqual(self.j.project(True)['status'],'unavailable');self.j.observe(self.items);self.assertEqual(self.j.project(True,items=self.items)['status'],'baseline')
 def test_unassigned_appointment_is_a_valid_baseline(self):
  self.items['p'].update(person=None,name='Unassigned');self.j.observe(self.items);self.assertEqual(self.j.project(True,items=self.items)['status'],'baseline')

class ReportTests(unittest.IsolatedAsyncioTestCase):
 setUpBase=follow.FollowupTests.setUpBase
 setUp=follow.FollowupTests.setUp
 model=follow.FollowupTests.model
 opened=follow.FollowupTests.opened
 async def test_item_already_at_checked_venue_enters_review_without_saving(self):
  item,_=await self.opened();self.f.reports.save(item,{'venue':'Elm School','equipment':['instrument','sheet music']},[],'Use Elm School and instrument and sheet music','fixture');await self.f.refresh();item=self.f.items[item['id']];step=next(s['id'] for s in item['checklist'] if s['text']=='instrument')
  self.frame.update(intent='readiness',venue='',equipment=[],journey_quote='',ready=[step]);opened=await self.f.open(item['id'],item['version'],'owner');out=await self.f.answer(opened['session'],'owner','Her instrument is already at school.');self.assertEqual(out['state'],'review');self.assertIn('Reported ready: instrument',' '.join(out['lines']));self.assertFalse(self.f.reports.get(item)['checked'])
 async def test_generic_location_cannot_mark_wrong_item_or_usual_venue_ready(self):
  item,_=await self.opened();item.update(venue='Elm School',venue_basis='calendar');item['checklist']=[{'id':'i','text':'instrument','kind':'equipment'},{'id':'m','text':'sheet music','kind':'equipment'}]
  self.assertEqual(at_venue_items('Her instrument is already at school.',item),['i']);self.assertEqual(at_venue_items('Is her instrument already at school?',item),[]);self.assertEqual(at_venue_items('Her instrument is not already at school.',item),[]);self.assertEqual(at_venue_items('Her instrument is already at Other Hall.',item),[]);item['venue_basis']='usual venue';self.assertEqual(at_venue_items('Her instrument is already at school.',item),[])
 async def test_norwegian_report_is_checked_against_same_venue(self):
  item,_=await self.opened();item.update(venue='Elm School',venue_basis='calendar');item['checklist']=[{'id':'i','text':'instrument','kind':'equipment'}];self.assertEqual(at_venue_items('Instrumentet er allerede på skolen.',item),['i'])
 async def test_native_change_query_is_read_only(self):
  await self.f.refresh();self.f.changes.observe(self.f.items);before='\n'.join(self.store.db.iterdump());out=await self.f.native_read('What changed in our plans?',[]);self.assertTrue(out['planning_changes']);self.assertEqual(before,'\n'.join(self.store.db.iterdump()))
 async def test_temporal_memory_keeps_interval_not_a_single_end_day(self):
  text='Mia has her instrument at school through Friday.';self.store.enqueue(text,context());job=self.store.next_job()
  with patch('jarvis.companion_memory.local_json',new=AsyncMock(return_value={'items':[model_item(text,subjects=['mia'])]})):
   records=await MemoryLearner(self.p,self.store,self.provider).extract(job)
  self.assertEqual(records[0]['kind'],'plan');self.assertEqual(records[0]['when_quote'],'through Friday');self.assertFalse(records[0]['date_unresolved'])
 async def test_packing_question_cannot_be_saved_as_a_completion(self):
  item,_=await self.opened();self.f.reports.save(item,{'venue':'Elm School','equipment':['instrument']},[],'Use Elm School and instrument','fixture');await self.f.refresh();item=self.f.items[item['id']];step=item['checklist'][0]['id'];self.frame.update(intent='readiness',venue='',equipment=[],journey_quote='',ready=[step]);opened=await self.f.open(item['id'],item['version'],'owner');out=await self.f.answer(opened['session'],'owner','Is her instrument packed?');self.assertEqual(out['state'],'conversation');self.assertFalse(self.f.reports.get(item)['checked'])

class DepartureTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  from jarvis.event_preparation import EventPreparation
  from jarvis.departure_continuation import remember
  self.clock=[1];self.store=CompanionStore();self.addCleanup(self.store.close);self.event={'text':'Band rehearsal','source':'family','owners':['mia'],'start':'2026-11-03T18:00:00+01:00','end':'2026-11-03T19:00:00+01:00','location':'Elm School','description':''}
  self.event['kind']='appointment'
  self.state={'read_focus':{'event_focus':[EventPreparation.event_identity(self.event)]}}
  self.router=SimpleNamespace(dated_evidence=AsyncMock(return_value={'facts':[self.event]}));self.owner=SimpleNamespace(store=self.store,profile=SimpleNamespace(_data={'revision':1}),clock=lambda:self.clock[0],now=lambda:datetime(2026,11,2,10,tzinfo=timezone.utc),container=SimpleNamespace(companion_routing=self.router),agent=SimpleNamespace(reads=SimpleNamespace(prior=lambda state:state['read_focus'])))
  remember(self.owner,self.state,self.event,10,'Elm School')
 async def test_new_origin_recalculates_with_checked_leg_and_allowance(self):
  from jarvis.departure_continuation import note
  result=await note(self.owner,self.state,12,'Library','Elm School');self.assertIn('17:38',result);self.assertIn('Library',result);self.assertIn('12-minute',result);self.assertIn('10-minute',result)
 async def test_changed_appointment_withholds_old_departure(self):
  from jarvis.departure_continuation import note
  self.event['start']='2026-11-03T20:00:00+01:00';result=await note(self.owner,self.state,12,'Library','Elm School');self.assertIn('withheld',result);self.assertNotIn('17:38',result)
 async def test_other_destination_or_expiry_does_not_reuse_time(self):
  from jarvis.departure_continuation import note
  self.assertIsNone(await note(self.owner,self.state,12,'Library','Other Hall'));self.clock[0]=602;self.assertIsNone(await note(self.owner,self.state,12,'Library','Elm School'))
 def test_origin_quote_is_literal_and_does_not_invent_a_work_address(self):
  from jarvis.departure_continuation import origin_quote
  self.assertEqual(origin_quote("We're leaving from work instead."),'work');self.assertEqual(origin_quote('When should we leave from Elm Library?'),'Elm Library');self.assertIsNone(origin_quote('When should we leave?'))

class OriginRouteTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  from test_companion_routing import RoutingTests
  RoutingTests.setUp(self)
 async def test_work_requires_specific_place_without_geocoding_work(self):
  from jarvis.calendar_context import calendar_scope
  self.provider.result.update(origin_quote='work',destination_quote='Ulsteinvik')
  with calendar_scope({'actor':'u','read':True,'write':False}):result=await self.router.handle("We're leaving from work to Ulsteinvik instead.",'s',self.state)
  self.assertEqual(result['status'],'clarification_required');self.assertIn('work address',result['message']);self.assertEqual(self.transport.calls,[]);self.assertEqual(self.state['route_pending']['destination'],'Ulsteinvik')

if __name__=='__main__':unittest.main()
