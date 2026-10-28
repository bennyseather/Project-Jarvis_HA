"""Fictional provider edits, concurrency, source preservation and chat reviews."""
import asyncio
from copy import deepcopy
from datetime import datetime
import json,tempfile,unittest
from pathlib import Path
from jarvis.calendar_mutations import MutationStore,VersionConflict,snapshot
from jarvis.calendar_membership import identity,description
from jarvis.calendar_conversation import CalendarConversation
from jarvis.calendar_context import calendar_scope
from jarvis.calendar_changes import review
from jarvis.calendar_editing import change_day
from jarvis.calendar_editing import EditingInterpreter,SCHEMA as EDIT_SCHEMA
from jarvis.household_planner import HouseholdPlanner,CALENDAR,ZONE
from test_planning_preparation_bundle import profile

def event():
    return {'id':'fictional-google-id','iCalUID':'fictional-ical-id','etag':'version-1','summary':'Dentist',
        'start':{'dateTime':'2026-11-05T16:00:00+01:00','timeZone':'Europe/Oslo'},
        'end':{'dateTime':'2026-11-05T17:00:00+01:00','timeZone':'Europe/Oslo'},
        'description':description(['mia'],'health','fictional-plan-id','Keep these organiser notes.'),
        'location':'Fictional Clinic','colorId':'3','reminders':{'useDefault':False},'extendedProperties':{'private':{'unrelated':'preserve'}}}

class Source:
    def __init__(self):self.raw=event();self.writes=[];self.conflict=False;self.after_error=False;self.refresh_error=False
    async def resolve(self,selection):
        if selection['key']!=identity(snapshot(self.raw)):raise ValueError('The appointment changed')
        return {'id':self.raw['id'],'calendar':'fictional-calendar'},deepcopy(self.raw)
    async def get(self,ref):return deepcopy(self.raw)
    async def write(self,ref,operation,patch,version):
        if self.conflict or version!=self.raw['etag']:raise VersionConflict('Changed on phone')
        self.writes.append((ref,operation,deepcopy(patch),version))
        self.raw.update({'status':'cancelled'} if operation=='cancel' else deepcopy(patch));self.raw['etag']='version-2'
        if self.after_error:raise RuntimeError('Response lost')
    async def refresh(self):
        if self.refresh_error:raise RuntimeError('HA cache delayed')

class Client:
    def __init__(self,source,store):self.source=source;self.store=store
    async def get_calendar_events(self,entity,start,end):
        return [snapshot(self.source.raw)] if entity==CALENDAR and self.source.raw.get('status')!='cancelled' else []
    async def manage_household_appointment(self,action,payload):
        if action=='inspect':return await self.store.inspect(payload['selection'])
        if action=='prepare':return await self.store.prepare('ha-user',**payload)
        return await self.store.commit('ha-user',payload['token'])

class MutationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.s=Source();self.clock=[1];self.now=lambda:datetime(2026,10,28,12,tzinfo=ZONE)
        self.store=MutationStore(self.s,clock=lambda:self.clock[0],now=self.now);self.addCleanup(self.store.db.close)
        self.selection={'key':identity(snapshot(self.s.raw)),'start':'2026-11-05','end':'2026-11-06'}
    async def prepare(self,patch=None,operation='update'):
        return await self.store.prepare('ha-user',self.selection,operation,patch if patch is not None else {'location':'New Fictional Clinic'},self.s.raw['etag'])
    async def test_review_writes_nothing_commit_patches_one_stable_id_preserving_other_fields(self):
        before=deepcopy(self.s.raw);r=await self.prepare();self.assertFalse(self.s.writes)
        out=await self.store.commit('ha-user',r['token']);self.assertEqual(out['state'],'confirmed')
        self.assertEqual(self.s.raw['id'],before['id']);self.assertEqual(self.s.raw['iCalUID'],before['iCalUID'])
        for key in ('description','colorId','reminders','extendedProperties'):self.assertEqual(self.s.raw[key],before[key])
        self.assertEqual(self.s.writes[0][3],'version-1')
    async def test_replay_and_concurrent_confirmation_write_once(self):
        r=await self.prepare();out=await asyncio.gather(*(self.store.commit('ha-user',r['token']) for _ in range(2)))
        self.assertTrue(all(v['state']=='confirmed' for v in out));self.assertEqual(len(self.s.writes),1)
    async def test_changed_source_before_confirmation_and_conditional_race_block_overwrite(self):
        r=await self.prepare();self.s.raw['etag']='phone-version'
        with self.assertRaises(ValueError):await self.store.commit('ha-user',r['token'])
        self.assertFalse(self.s.writes)
        self.s.raw['etag']='version-1';self.s.conflict=True
        out=await self.store.commit('ha-user',r['token']);self.assertEqual(out['state'],'review_required');self.assertFalse(self.s.writes)
    async def test_wrong_owner_expired_and_invalid_patch_do_not_write(self):
        r=await self.prepare()
        with self.assertRaises(ValueError):await self.store.commit('other',r['token'])
        self.clock[0]=302
        with self.assertRaises(ValueError):await self.store.commit('ha-user',r['token'])
        for patch in ({'attendees':[]},{'recurrence':[]},{'start':{'date':'2026-11-05'}}):
            with self.assertRaises(ValueError):await self.prepare(patch)
        self.assertFalse(self.s.writes)
    async def test_attendee_and_series_master_edits_are_not_sent(self):
        self.s.raw['attendees']=[{'email':'nobody@example.invalid'}]
        with self.assertRaises(ValueError):await self.prepare()
        self.s.raw.pop('attendees');self.s.raw['recurrence']=['RRULE:FREQ=WEEKLY']
        with self.assertRaises(ValueError):await self.prepare()
        self.assertFalse(self.s.writes)
    async def test_cancel_one_recurring_instance_preserves_parent_and_rules(self):
        self.s.raw.update(recurringEventId='fictional-parent',originalStartTime={'dateTime':'2026-11-05T16:00:00+01:00'})
        parent=deepcopy(self.s.raw['recurringEventId']);r=await self.prepare({},'cancel')
        self.assertTrue(r['recurring']);out=await self.store.commit('ha-user',r['token'])
        self.assertEqual(out['state'],'confirmed');self.assertEqual(self.s.raw['recurringEventId'],parent)
        self.assertEqual(self.s.writes[0][1],'cancel');self.assertEqual(self.s.writes[0][2],{})
    async def test_lost_response_and_process_restart_never_retry_write(self):
        self.s.after_error=True;r=await self.prepare();out=await self.store.commit('ha-user',r['token'])
        self.assertEqual(out['state'],'uncertain');await self.store.commit('ha-user',r['token']);self.assertEqual(len(self.s.writes),1)
    async def test_persisted_dispatch_is_uncertain_after_reopening_and_is_not_sent_again(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'receipts.sqlite3';first=MutationStore(self.s,path,now=self.now)
            r=await first.prepare('ha-user',self.selection,'update',{'location':'New Clinic'},self.s.raw['etag'])
            with first.db:first.db.execute("UPDATE receipts SET state='sending' WHERE token=?",(r['token'],))
            first.db.close();second=MutationStore(self.s,path,now=self.now)
            try:self.assertEqual((await second.commit('ha-user',r['token']))['state'],'uncertain');self.assertFalse(self.s.writes)
            finally:second.db.close()
    async def test_confirmed_provider_update_is_not_failed_when_ha_refresh_is_delayed(self):
        self.s.refresh_error=True;r=await self.prepare();out=await self.store.commit('ha-user',r['token'])
        self.assertEqual(out['state'],'confirmed');self.assertFalse(out['ha_refreshed'])
    async def test_noop_and_past_start_are_rejected_without_a_write(self):
        self.assertEqual((await self.prepare({'location':'Fictional Clinic'}))['state'],'unchanged')
        with self.assertRaises(ValueError):await self.prepare({'start':{'dateTime':'2026-10-01T16:00:00+02:00'},'end':{'dateTime':'2026-10-01T17:00:00+02:00'}})
        self.assertFalse(self.s.writes)
    async def test_relative_new_weekday_uses_selected_appointment_week(self):
        self.assertEqual(change_day('Friday','2026-11-05','2026-10-28'),'2026-11-06')
        self.assertEqual(change_day('tomorrow','2026-11-05','2026-10-28'),'2026-10-29')
        with self.assertRaises(ValueError):change_day('Monday','2026-10-30','2026-10-28')

class Extractor:
    def __init__(self,responses):self.responses=responses
    async def extract(self,text,*args):return deepcopy(self.responses[text])

class DialogueTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.s=Source();self.store=MutationStore(self.s,now=lambda:datetime(2026,10,28,12,tzinfo=ZONE));self.addCleanup(self.store.db.close)
        self.p=profile();self.client=Client(self.s,self.store)
        self.planner=HouseholdPlanner(self.p,self.client,[CALENDAR],now=lambda:datetime(2026,10,28,12,tzinfo=ZONE));self.planner.bootstrap([]);self.addCleanup(self.planner.db.close)
        self.chat=CalendarConversation(self.planner);self.e=self.chat.editing
        self.responses={
            'Find Mia dentist appointment next Thursday':('find',{'title':'dentist','person':'mia','range':('2026-11-05','2026-11-06')},{}),
            'Move the appointment to Friday at 1600':('update',{}, {'date':'2026-11-06','time':'16:00'}),
            'Change the venue to New Fictional Clinic':('update',{}, {'location':'New Fictional Clinic'}),
            'Cancel that appointment':('cancel',{},{}),
            'That appointment is for Linda':('update',{}, {'members':['linda']}),
            'What is the weather?':('unrelated',{}, {})}
        self.e.extractor=Extractor(self.responses)
    async def say(self,text,source='phone',write=True):
        with calendar_scope({'actor':'ha-user','read':True,'write':write}):return await self.chat.handle(text,'chat',source)
    async def test_find_move_venue_review_confirm_and_followup_cancel(self):
        self.assertIn('I found', (await self.say('Find Mia dentist appointment next Thursday'))['message'])
        out=await self.say('Move the appointment to Friday at 1600');self.assertIn('Friday 6 November',out['message']);self.assertFalse(self.s.writes)
        out=await self.say('Change the venue to New Fictional Clinic');self.assertIn('New Fictional Clinic',out['message'])
        self.assertEqual((await self.say('Yes'))['status'],'success');self.assertEqual(len(self.s.writes),1)
        self.assertIn('2026-11-06',self.s.raw['start']['dateTime']);self.assertEqual(self.s.raw['location'],'New Fictional Clinic')
        out=await self.say('Cancel that appointment');self.assertIn('does not cancel a booking',out['message']);self.assertEqual(len(self.s.writes),1)
        await self.say('Yes');self.assertEqual(self.s.raw['status'],'cancelled');self.assertEqual(len(self.s.writes),2)
    async def test_discard_and_unrelated_question_invalidate_previous_review(self):
        await self.say('Find Mia dentist appointment next Thursday');await self.say('Cancel that appointment');await self.say('Cancel')
        await self.say('Yes');self.assertFalse(self.s.writes)
    async def test_actor_source_permissions_and_profile_revision_are_checked(self):
        await self.say('Find Mia dentist appointment next Thursday');await self.say('Cancel that appointment')
        await self.say('Yes',source='other');self.assertFalse(self.s.writes)
        self.assertEqual((await self.say('Find Mia dentist appointment next Thursday',write=False))['status'],'forbidden')
    async def test_person_correction_updates_metadata_and_preserves_organiser_notes(self):
        await self.say('Find Mia dentist appointment next Thursday');await self.say('That appointment is for Linda');await self.say('Yes')
        self.assertEqual(self.planner.assign(snapshot(self.s.raw))['members'],['linda'])
        self.assertIn('Keep these organiser notes.',self.s.raw['description'])
    async def test_unchanged_requested_venue_does_not_create_metadata_or_write(self):
        self.responses['Change the venue to Fictional Clinic']=('update',{}, {'location':'Fictional Clinic'})
        await self.say('Find Mia dentist appointment next Thursday');out=await self.say('Change the venue to Fictional Clinic')
        self.assertIn('already has',out['message']);self.assertFalse(self.s.writes)
    async def test_find_without_a_known_date_searches_a_bounded_upcoming_window(self):
        self.responses['Find Mia next dentist appointment']=('find',{'title':'dentist','person':'mia'}, {})
        out=await self.say('Find Mia next dentist appointment');self.assertIn('I found',out['message'])
        self.assertEqual(self.e.sessions['chat']['selection']['start'],'2026-11-05');self.assertFalse(self.s.writes)
    async def test_new_phone_entry_is_interpreted_when_found_without_a_dashboard_refresh(self):
        self.s.raw.update(summary='Mia dentist',description='Bring the letter.')
        class Interpreter:
            async def interpret(self,event):return {'members':['mia'],'category':'health','venue':'Fictional Clinic','activity':'dental appointment','unclear':[],'basis':'fictional supported extraction'}
        self.planner.interpreter=Interpreter()
        self.responses['Find Mia dentist appointment next Thursday']=('find',{'title':'dentist','person':'mia','range':('2026-11-05','2026-11-06')},{})
        out=await self.say('Find Mia dentist appointment next Thursday');self.assertIn('for Mia',out['message']);self.assertFalse(self.s.writes)
    async def test_negated_and_whole_series_requests_are_not_prepared(self):
        out=await self.say("Don't delete that appointment");self.assertIn('unchanged',out['message'])
        await self.say('Find Mia dentist appointment next Thursday')
        out=await self.say('Move every occurrence of that appointment');self.assertIn('phone calendar',out['message']);self.assertFalse(self.s.writes)
    async def test_all_day_move_preserves_calendar_days_across_clock_change(self):
        self.s.raw.update(start={'date':'2027-03-27'},end={'date':'2027-03-30'})
        selection={'key':identity(snapshot(self.s.raw)),'start':'2027-03-27','end':'2027-03-28'}
        r=await review(self.planner,selection,'update',{'date':'2027-04-03'},'owner')
        self.assertEqual((r['after']['start'],r['after']['end']),('2027-04-03','2027-04-06'))
        self.assertFalse(self.s.writes)
    async def test_long_organiser_notes_are_not_truncated(self):
        self.s.raw['description']='x'*3100
        selection={'key':identity(snapshot(self.s.raw)),'start':'2026-11-05','end':'2026-11-06'}
        r=await review(self.planner,selection,'update',{'location':'New Clinic','members':['mia']},'owner')
        await self.planner.confirm({'token':r['token']},'owner')
        self.assertEqual(self.s.raw['description'],'x'*3100);self.assertEqual(self.s.raw['location'],'New Clinic')
    async def test_clean_phone_notes_stay_clean_and_attribution_survives_later_phone_reschedule(self):
        self.s.raw['description']='Unmodified phone notes.'
        selection={'key':identity(snapshot(self.s.raw)),'start':'2026-11-05','end':'2026-11-06'}
        r=await review(self.planner,selection,'update',{'date':'2026-11-06','members':['mia']},'owner')
        await self.planner.confirm({'token':r['token']},'owner')
        self.assertEqual(self.s.raw['description'],'Unmodified phone notes.')
        self.s.raw['start']['dateTime']='2026-11-07T16:00:00+01:00';self.s.raw['end']['dateTime']='2026-11-07T17:00:00+01:00'
        self.assertEqual(self.planner.assign(snapshot(self.s.raw))['members'],['mia'])
        self.s.raw['summary']='Linda new appointment';self.assertFalse(self.planner.assign(snapshot(self.s.raw))['members'])

class GroundingTests(unittest.IsolatedAsyncioTestCase):
    def provider(self,operation,target_title='',target_date='',target_person='',**changes):
        from types import SimpleNamespace
        from jarvis.calendar_drafting import FIELDS
        data={'operation':operation,'target_title':target_title,'target_date':target_date,'target_person':target_person,
            'changes':{'members':[],'category':'',**dict.fromkeys(FIELDS,''),**changes}}
        return SimpleNamespace(reason_local=lambda **kwargs:{'status':'success','message':json.dumps(data)})
    async def test_unsupported_model_fields_are_dropped_without_losing_stated_venue(self):
        interpreter=EditingInterpreter(self.provider('update','Old invented appointment','Thursday','mia',venue='Fictional Clinic',date='Thursday',time='1600',member_evidence='not stated'))
        operation,target,patch=await interpreter.extract('Change the venue to Fictional Clinic',{'mia':'Mia'},'2026-10-28',True,None)
        self.assertEqual(target,{});self.assertEqual(patch,{'location':'Fictional Clinic','venue_known':True})
    async def test_model_cannot_turn_a_find_into_removal_without_a_stated_cancel_verb(self):
        interpreter=EditingInterpreter(self.provider('cancel',target_title='dentist'))
        with self.assertRaises(ValueError):await interpreter.extract('Find dentist appointment',{'mia':'Mia'},'2026-10-28',False,None)
    async def test_relative_shift_is_not_misinterpreted_as_a_new_duration(self):
        interpreter=EditingInterpreter(self.provider('update',duration='30 minutes'))
        with self.assertRaisesRegex(ValueError,'exact new time'):await interpreter.extract('Move it 30 minutes later',{'mia':'Mia'},'2026-10-28',True,None)
