"""Fictional flight changes, planning margins, source failures and no side effects."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
import unittest
from jarvis.companion_store import CompanionStore
from jarvis.companion_transport import EnturTransport,coordinates
from jarvis.companion_travel import TravelPreparer,journeys
NOW=datetime(2026,10,28,12,tzinfo=timezone.utc)
def flight(uid='first',origin='HOV',destination='OSL',start='2026-11-05T10:00:00+00:00',end='2026-11-05T11:00:00+00:00',ref='REALABC'):
 return {'uid':uid,'summary':'SK123 · '+origin+' → '+destination,'description':'Booking reference: '+ref,'start':{'dateTime':start},'end':{'dateTime':end},'location':''}
class Client:
 def __init__(self,rows):self.rows=rows;self.fail=False;self.service_calls=[]
 async def get_calendar_events(self,*args):
  if self.fail:raise ConnectionError('fictional unavailable')
  return deepcopy(self.rows)
 async def get_home_location(self):return {'latitude':62.2,'longitude':6.0}
class Transport:
 def __init__(self):self.calls=[];self.fail=False
 def airport(self,code):return {'coordinates':{'latitude':62.18,'longitude':6.08},'label':'Fictional airport'} if code=='HOV' else None
 def route(self,a,b,target,mode):
  self.calls.append(mode)
  if self.fail:return {'state':'source_error','options':[],'mode':mode}
  return {'state':'available','mode':mode,'options':[{'departure':(target-timedelta(minutes=30)).isoformat(),'arrival':target.isoformat(),'duration_minutes':30,'legs':[{'mode':'car' if mode=='driving' else 'bus','line':'340'}]}]}
class TravelTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.store=CompanionStore(now=lambda:NOW);self.addCleanup(self.store.close);self.client=Client([flight()]);self.transport=Transport()
  self.reader=SimpleNamespace(_resolve_entity=lambda:'calendar.jarvis_travels')
  self.p=TravelPreparer(self.client,self.reader,self.store,None,transport=self.transport,now=lambda:NOW)
 async def test_automatic_scan_prepares_driving_and_public_options_without_a_request(self):
  result=await self.p.scan();self.assertEqual(result['prepared'],1)
  report=self.store.briefs()[0];self.assertEqual(report['owner'],'benny');self.assertTrue(report['automatic']);self.assertTrue(report['read_only'])
  self.assertEqual(set(self.transport.calls),{'driving','public_transport'});self.assertEqual(self.client.service_calls,[])
  self.assertIn('08:15',report['summary']);self.assertEqual(report['details']['airport_planning_allowance_minutes'],120)
 async def test_connected_journey_uses_first_leg_and_later_change_refreshes(self):
  self.client.rows.append(flight(uid='second',origin='OSL',destination='PER',start='2026-11-05T14:00:00+00:00',end='2026-11-06T06:00:00+00:00'))
  await self.p.scan();row=self.store.briefs()[0];self.assertEqual(row['details']['origin'],'HOV');self.assertEqual(row['details']['destination'],'PER')
  self.client.rows[1]['end']['dateTime']='2026-11-06T07:00:00+00:00';result=await self.p.scan()
  self.assertEqual(result['prepared'],1);self.assertNotEqual(row['input_hash'],self.store.briefs()[0]['input_hash'])
 async def test_unchanged_flight_is_not_researched_repeatedly(self):
  await self.p.scan();self.transport.calls=[];result=await self.p.scan();self.assertEqual(result['prepared'],0);self.assertEqual(self.transport.calls,[])
 async def test_cancelled_or_removed_booking_withdraws_old_advice(self):
  await self.p.scan();self.client.rows[0]['status']='cancelled';result=await self.p.scan()
  self.assertEqual(result['prepared'],0);self.assertEqual(self.store.briefs(),[]);self.assertEqual(self.store.briefs(True)[0]['status'],'withdrawn')
 async def test_source_outage_does_not_misreport_booking_cancellation(self):
  await self.p.scan();self.client.fail=True;await self.p.scan()
  self.assertEqual(len(self.store.briefs()),1);self.assertEqual(self.p.status,'travel_calendar_unavailable')
 async def test_unknown_foreign_origin_is_not_replaced_by_the_home_location(self):
  self.client.rows=[flight(origin='PER',destination='SIN')];await self.p.scan();report=self.store.briefs()[0]
  self.assertEqual(report['status'],'needs_input');self.assertIsNone(report['details']['driving']);self.assertEqual(self.transport.calls,[])
  self.assertIn('Where will you be setting out',report['summary']);self.assertIn('Where do you need to go after arriving',report['questions'][-1])
 async def test_missing_routes_do_not_invent_a_departure_or_claim_no_services_exist(self):
  self.transport.fail=True;await self.p.scan();report=self.store.briefs()[0]
  self.assertNotIn('suggested_leave_time',report['details']);self.assertIn('could not verify',report['summary'])
  self.assertNotIn('no buses exist',report['summary'].lower())
 def test_non_flight_all_day_and_unknown_zone_entries_are_not_prepared(self):
  rows=[flight()];rows[0]['start']={'date':'2026-11-05'};self.assertEqual(journeys(rows,NOW,NOW+timedelta(days=30)),[])
  rows[0]=flight(start='2026-11-05T10:00:00');self.assertEqual(journeys(rows,NOW,NOW+timedelta(days=30)),[])
 def test_missing_uid_and_booking_reference_do_not_merge_same_day_flights(self):
  a=flight(uid=None,ref='');b=flight(uid=None,origin='HOV',destination='BGO',start='2026-11-05T16:00:00+00:00',end='2026-11-05T17:00:00+00:00',ref='')
  rows=journeys([a,b],NOW,NOW+timedelta(days=30));self.assertEqual(len(rows),2);self.assertNotEqual(rows[0]['id'],rows[1]['id'])
 async def test_in_progress_journey_keeps_arrival_preparation_but_no_outbound_route(self):
  self.client.rows=[flight(start='2026-10-28T11:00:00+00:00',end='2026-10-28T13:00:00+00:00')]
  await self.p.scan();row=self.store.briefs()[0];self.assertEqual(row['details']['journey_phase'],'in_progress');self.assertEqual(self.transport.calls,[])

 async def test_new_trip_details_withdraw_old_route_until_refresh(self):
  import json
  await self.p.scan();old=self.store.briefs()[0]
  provider=SimpleNamespace(reason_local=lambda **kw:{'status':'success','message':json.dumps({'origin_quote':'home','onward_quote':'Fictional Hotel'})})
  await self.p.update_input(old['id'],"I am leaving from home, onward to Fictional Hotel",provider)
  row=self.store.briefs()[0];self.assertEqual(row['status'],'needs_input');self.assertTrue(row['refresh_requested']);self.assertNotIn('08:15',row['summary'])
  out=await self.p.scan();self.assertEqual(out['prepared'],1);row=self.store.briefs()[0]
  self.assertEqual(row['details']['arrival_onward_destination'],'Fictional Hotel');self.assertFalse(any('Where do you need to go' in q for q in row['questions']))
 async def test_changed_flight_does_not_inherit_old_origin_or_hotel(self):
  import json
  await self.p.scan();old=self.store.briefs()[0]
  provider=SimpleNamespace(reason_local=lambda **kw:{'status':'success','message':json.dumps({'origin_quote':'home','onward_quote':'Fictional Hotel'})})
  await self.p.update_input(old['id'],'home, onward to Fictional Hotel',provider)
  self.client.rows[0]['end']['dateTime']='2026-11-05T12:00:00+00:00'
  await self.p.scan();self.assertEqual(self.store.briefs()[0]['details']['arrival_onward_destination'],'not confirmed')
 async def test_model_cannot_invent_a_place_from_trip_reply(self):
  import json
  await self.p.scan();old=self.store.briefs()[0]
  provider=SimpleNamespace(reason_local=lambda **kw:{'status':'success','message':json.dumps({'origin_quote':'Fictional Palace','onward_quote':''})})
  with self.assertRaises(ValueError):await self.p.update_input(old['id'],'leaving from home',provider)
  self.assertEqual(self.store.travel_input(old['id'],old['input_hash']),{})

class TransportTests(unittest.TestCase):
 def test_nynorsk_airport_name_is_accepted_and_cached(self):
  calls=[]
  def http(url,payload=None):calls.append(url);return {'features':[{'properties':{'label':'Ørsta-Volda lufthamn, Ørsta'},'geometry':{'coordinates':[6.08,62.18]}}]}
  client=EnturTransport(http=http);self.assertEqual(client.airport('HOV')['code'],'HOV');client.airport('HOV');self.assertEqual(len(calls),1)
 def test_route_request_has_access_and_egress_and_minutes_search_window(self):
  calls=[]
  def http(url,payload):calls.append(payload);return {'data':{'trip':{'tripPatterns':[],'routingErrors':[]}}}
  client=EnturTransport(http=http);row=client.route({'latitude':62.2,'longitude':6.0},{'latitude':62.18,'longitude':6.08},NOW+timedelta(days=1),'public_transport')
  self.assertEqual(row['state'],'no_options_in_search_window');self.assertEqual(row['search_window_minutes'],360)
  self.assertEqual(calls[0]['variables']['modes']['accessMode'],'foot');self.assertEqual(calls[0]['variables']['modes']['egressMode'],'foot')
 def test_graphql_errors_are_not_reported_as_no_public_transport(self):
  client=EnturTransport(http=lambda *a:{'errors':[{'message':'data unavailable'}]})
  row=client.route({'latitude':62.2,'longitude':6.0},{'latitude':62.18,'longitude':6.08},NOW+timedelta(days=1),'public_transport');self.assertEqual(row['state'],'source_error')
 def test_foreign_region_and_invalid_coordinates_do_not_call_route_provider(self):
  client=EnturTransport(http=lambda *a:(_ for _ in ()).throw(AssertionError('Must not call')))
  row=client.route({'latitude':-31.9,'longitude':115.9},{'latitude':-31.9,'longitude':116.0},NOW,'driving');self.assertEqual(row['state'],'unsupported_region')
  with self.assertRaises(ValueError):coordinates({'latitude':float('nan'),'longitude':6})

if __name__=='__main__':unittest.main()
