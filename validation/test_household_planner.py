"""Fictional shared-calendar ownership, review and write-receipt contracts."""
import asyncio
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from jarvis.calendar_membership import assignment,description,identity,PREFIX
from jarvis.household_planner import HouseholdPlanner,local_time,CALENDAR,ZONE
from test_planning_preparation_bundle import profile

class Client:
    def __init__(self):self.events=[];self.writes=[];self.fail=False;self.after_write_error=False
    async def get_calendar_events(self,entity,start,end):
        if self.fail:raise RuntimeError('fictional offline')
        return deepcopy(self.events) if entity==CALENDAR else []
    async def create_household_appointment(self,data):
        self.writes.append(deepcopy(data))
        self.events.append({'summary':data['summary'],'start':data.get('start_date_time',data.get('start_date')),
            'end':data.get('end_date_time',data.get('end_date')),'description':data['description'],'location':data.get('location','')})
        if self.after_write_error:raise RuntimeError('unknown delivery')

class Membership(unittest.TestCase):
    def test_explicit_multi_member_metadata_is_not_a_voice_identity(self):
        event={'description':description(['linda','mia'],'sport','fictional-id','Bring water.')}
        out=assignment(event,{'linda','mia'},active=True)
        self.assertEqual(out['members'],['linda','mia']);self.assertEqual(out['notes'],'Bring water.')
    def test_malformed_unknown_or_duplicate_metadata_is_unassigned(self):
        for data in ({'members':['stranger'],'category':'sport','id':'fictional-id'},
                     {'members':['mia','mia'],'category':'sport','id':'fictional-id'}):
            self.assertFalse(assignment({'description':PREFIX+json.dumps(data)},{'mia'},active=True)['members'])
        self.assertFalse(assignment({'description':PREFIX+'{"members":[],"members":["mia"],"category":"sport","id":"fictional-id"}'},{'mia'},active=True)['members'])
    def test_identity_matches_ha_service_and_native_calendar_formats(self):
        a={'summary':'Club','start':'2026-11-05T17:00:00+01:00','end':'2026-11-05T18:00:00+01:00'}
        b={**a,'start':{'dateTime':'2026-11-05T16:00:00Z'},'end':{'dateTime':'2026-11-05T17:00:00Z'}}
        self.assertEqual(identity(a),identity(b))
    def test_clock_change_missing_and_ambiguous_times_rejected(self):
        for value in ('2027-03-28T02:30','2027-10-31T02:30'):
            with self.assertRaises(ValueError):local_time(value)
        self.assertEqual(local_time('2027-03-28T03:30').utcoffset().total_seconds(),7200)

class PlannerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.p=profile();self.c=Client();self.clock=[1]
        self.planner=HouseholdPlanner(self.p,self.c,[CALENDAR],path=Path(self.temp.name)/'planner.sqlite3',
            now=lambda:datetime(2026,10,27,12,tzinfo=ZONE),clock=lambda:self.clock[0])
        self.addCleanup(self.planner.db.close)
        self.planner.bootstrap([])
        self.draft={'title':'Fictional club','members':['linda'],'category':'sport','start':'2026-11-05T17:00',
            'end':'2026-11-05T18:00','all_day':False,'location':'Fictional Hall','notes':'Bring water.'}
    async def review(self,owner='tablet-a',draft=None):return await self.planner.review(draft or self.draft,owner)
    async def confirm(self,review,owner='tablet-a'):return await self.planner.confirm({'token':review['token']},owner)
    async def test_review_does_not_write_or_change_profile(self):
        before=deepcopy(self.p._data);out=await self.review()
        self.assertEqual(out['state'],'review');self.assertEqual(self.c.writes,[]);self.assertEqual(before,self.p._data)
    async def test_confirm_writes_once_with_explicit_members_and_phone_calendar(self):
        out=await self.confirm(await self.review());self.assertEqual(out['state'],'confirmed')
        self.assertEqual(self.c.writes[0]['entity_id'],CALENDAR);self.assertEqual(self.planner.assign(self.c.events[0])['members'],['linda'])
    async def test_simultaneous_confirmations_and_replay_create_one_event(self):
        review=await self.review();out=await asyncio.gather(self.confirm(review),self.confirm(review))
        self.assertTrue(all(r['state']=='confirmed' for r in out));self.assertEqual(len(self.c.writes),1)
    async def test_two_review_tokens_cannot_create_the_same_appointment_twice(self):
        one,two=await self.review(),await self.review(owner='tablet-b')
        await self.confirm(one);out=await self.confirm(two,'tablet-b')
        self.assertEqual(out['state'],'duplicate');self.assertEqual(len(self.c.writes),1)
    async def test_wrong_session_expiry_and_changed_profile_stop_write(self):
        review=await self.review()
        with self.assertRaises(ValueError):await self.confirm(review,'tablet-b')
        self.clock[0]=302
        with self.assertRaises(ValueError):await self.confirm(review)
        self.clock[0]=1;self.p._data['revision']+=1
        with self.assertRaises(ValueError):await self.confirm(review)
        self.assertFalse(self.c.writes)
    async def test_duplicate_in_calendar_blocks_a_review(self):
        await self.confirm(await self.review());out=await self.review()
        self.assertEqual(out['state'],'duplicate');self.assertEqual(len(self.c.writes),1)
    async def test_uncertain_write_never_retries_blindly(self):
        review=await self.review();self.c.after_write_error=True
        self.assertEqual((await self.confirm(review))['state'],'uncertain')
        self.assertEqual((await self.confirm(review))['state'],'uncertain');self.assertEqual(len(self.c.writes),1)
        self.assertEqual((await self.review())['state'],'duplicate')
    async def test_failed_read_cannot_create_an_appointment(self):
        review=await self.review();self.c.fail=True
        with self.assertRaises(RuntimeError):await self.confirm(review)
        self.assertFalse(self.c.writes)
    async def test_all_day_form_end_is_inclusive_but_calendar_end_is_exclusive(self):
        draft={**self.draft,'all_day':True,'start':'2026-11-05','end':'2026-11-05'}
        await self.confirm(await self.review(draft=draft))
        self.assertEqual(self.c.writes[0]['start_date'],'2026-11-05');self.assertEqual(self.c.writes[0]['end_date'],'2026-11-06')
    async def test_unknown_members_missing_title_wrong_dates_and_unknown_fields_rejected(self):
        for changes in ({'members':[]},{'members':['stranger']},{'title':''},{'end':'2026-11-05T16:00'},
            {'start':'2027-03-28T02:30'},{'category':'invented'},{'calendar':'calendar.other'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):await self.review(draft={**self.draft,**changes})
        self.assertFalse(self.c.writes)
    async def test_existing_mia_assignment_is_kept_new_phone_entry_is_unassigned(self):
        p=profile();c=Client();route=HouseholdPlanner(p,c,[CALENDAR]);self.addCleanup(route.db.close)
        old={'summary':'Old club','start':'2026-11-05T17:00:00+01:00','end':'2026-11-05T18:00:00+01:00'}
        route.bootstrap([old]);self.assertEqual(route.assign(old)['members'],['mia'])
        self.assertEqual(route.assign({**old,'summary':'New phone appointment'})['members'],[])
        with self.assertRaises(ValueError):route.bootstrap([old])
    async def test_bad_existing_metadata_blocks_bootstrap_atomically(self):
        p=profile();route=HouseholdPlanner(p,Client(),[CALENDAR]);self.addCleanup(route.db.close)
        old={'summary':'Old club','start':'2026-11-05T17:00:00+01:00','end':'2026-11-05T18:00:00+01:00'}
        with self.assertRaises(ValueError):route.bootstrap([old,{**old,'description':'JARVIS-PLAN/1 invalid'}])
        self.assertFalse(route.ready);self.assertEqual(route.annotations(),{})
    async def test_personal_view_does_not_label_linda_appointment_as_mia(self):
        await self.confirm(await self.review())
        query={'start':'2026-11-05','end':'2026-11-06'}
        linda=await self.planner.agenda({**query,'members':['linda']});mia=await self.planner.agenda({**query,'members':['mia']})
        self.assertEqual(len(linda['events']),1);self.assertFalse(mia['events'])
    async def test_restart_keeps_write_receipt_and_does_not_send_again(self):
        review=await self.review();await self.confirm(review)
        other=HouseholdPlanner(self.p,self.c,[CALENDAR],path=self.planner.path,now=self.planner.now,clock=lambda:1)
        self.addCleanup(other.db.close)
        self.assertEqual((await other.confirm({'token':review['token']},'tablet-a'))['state'],'confirmed')
        self.assertEqual(len(self.c.writes),1)
    async def test_disabled_shared_policy_stops_writes(self):
        review=await self.review();self.p._data['sharing_policy']['directory_enabled']=False
        with self.assertRaises(ValueError):await self.confirm(review)
        self.assertFalse(self.c.writes)
    async def test_overlaps_are_attributed_to_the_same_member_only(self):
        await self.confirm(await self.review());draft={**self.draft,'title':'Another club','start':'2026-11-05T17:30','end':'2026-11-05T18:30'}
        self.assertTrue((await self.review(draft=draft))['overlaps'])
        self.assertFalse((await self.review(draft={**draft,'members':['mia']}))['overlaps'])
    async def test_reviewed_assignment_changes_catalogue_not_google_event(self):
        event={'summary':'Phone entry','start':'2026-11-05T17:00:00+01:00','end':'2026-11-05T18:00:00+01:00'}
        self.c.events=[event];before=deepcopy(self.c.events)
        draft={'key':identity(event),'start':'2026-11-05','end':'2026-11-06','members':['emrik'],'category':'school'}
        review=await self.planner.review_assignment(draft,'tablet-a')
        self.assertFalse(self.planner.assign(event)['members'])
        await self.confirm(review);self.assertEqual(self.planner.assign(event)['members'],['emrik'])
        self.assertEqual(before,self.c.events);self.assertFalse(self.c.writes)
    async def test_assignment_source_change_stops_commit(self):
        event={'summary':'Phone entry','start':'2026-11-05T17:00:00+01:00','end':'2026-11-05T18:00:00+01:00'}
        self.c.events=[event]
        draft={'key':identity(event),'start':'2026-11-05','end':'2026-11-06','members':['emrik'],'category':'school'}
        review=await self.planner.review_assignment(draft,'tablet-a');event['description']='Changed in Google while reviewing'
        with self.assertRaises(ValueError):await self.confirm(review)
        self.assertFalse(self.planner.assign(event)['members'])
    async def test_confirmed_equivalent_titles_are_duplicate_not_two_activities(self):
        from jarvis import household_activities as a
        for title in ('Club A','Club B'):
            a.install(self.p._data,a.proposal('Remember Mia\'s activity "'+title+'" in the family calendar means "gymnastics"',self.p._data))
        a.install(self.p._data,a.proposal('Remember Mia\'s activity "Club B" in the family calendar is the same activity as "Club A"',self.p._data))
        await self.confirm(await self.review(draft={**self.draft,'members':['mia'],'title':'Club A'}))
        self.assertEqual((await self.review(draft={**self.draft,'members':['mia'],'title':'Club B'}))['state'],'duplicate')
