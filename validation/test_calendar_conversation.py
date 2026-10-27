"""Calendar chat contracts. Fictional events only; no cloud or appliance calls."""
import ast
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from jarvis.calendar_context import calendar_scope,current_calendar_access
from jarvis.calendar_drafting import FIELDS,parse_patch,clock_value,duration_value,CalendarDrafting,literal_clock_patch
from jarvis.calendar_conversation import CalendarConversation
from jarvis.household_planner import HouseholdPlanner,CALENDAR,ZONE
from jarvis.calendar_membership import assignment,description,identity
from jarvis.household_speaker import speaker_scope
from test_household_planner import Client
from test_planning_preparation_bundle import profile

def raw(intent='continue',**values):
    return json.dumps({'intent':intent,'members':[],'category':'',**dict.fromkeys(FIELDS,''),**values})

PEOPLE={'mia':'Mia','linda':'Linda','benny':'Benny','emrik':'Emrik'}
START='Add a dentist appointment for Mia next Thursday at 14:00'
DATA={'title':'dentist appointment','members':['mia'],'member_evidence':'for Mia','date':'next Thursday',
      'time':'14:00','category':'health','category_evidence':'dentist'}

class Extraction(unittest.TestCase):
    def test_dates_are_calculated_by_code_and_norway_times(self):
        intent,d=parse_patch(raw('create',**DATA),START,PEOPLE,'2026-10-27')
        self.assertEqual(intent,'create');self.assertEqual(d['date'],'2026-11-05');self.assertEqual(d['time'],'14:00')
        self.assertNotIn('duration',d);self.assertNotIn('location',d)
    def test_invented_quotes_or_people_cannot_enter_draft(self):
        for kwargs in ({**DATA,'venue':'Invented Hall'}, {**DATA,'members':['linda']}, {**DATA,'date':'2026-11-05'},
                       {**DATA,'category_evidence':''}):
            with self.assertRaises(ValueError):parse_patch(raw('create',**kwargs),START,PEOPLE,'2026-10-27')
    def test_pronoun_needs_matched_speaker_and_alternatives_clarify(self):
        value=raw('create',members=['benny'],member_evidence='for me')
        with self.assertRaises(ValueError):parse_patch(value,'Add an appointment for me',PEOPLE,'2026-10-27')
        self.assertEqual(parse_patch(value,'Add an appointment for me',PEOPLE,'2026-10-27','benny')[1]['members'],['benny'])
        with self.assertRaises(ValueError):parse_patch(raw(members=['mia'],member_evidence='Mia or Linda'),'Mia or Linda',PEOPLE,'2026-10-27')
    def test_strict_json_duplicate_keys_and_invalid_types_rejected(self):
        for data in (raw().replace('"members": []','"members": [], "members": ["mia"]'),raw(members='mia'),raw(time=14)):
            with self.assertRaises((ValueError,TypeError)):parse_patch(data,'14 Mia',PEOPLE,'2026-10-27')
    def test_clock_duration_and_dst_bounds(self):
        self.assertEqual(clock_value('2:15 pm'),'14:15');self.assertEqual(clock_value('12 am'),'00:00')
        for text,n in [('an hour',60),('half an hour',30),('45 minutes',45),('two hours',120)]:self.assertEqual(duration_value(text),n)
        for t in ('25:00','14:80','2pm tomorrow'):
            with self.assertRaises(ValueError):clock_value(t)
        for t in ('0 minutes','2000 hours'):
            with self.assertRaises(ValueError):duration_value(t)
    def test_compact_and_twelve_hour_clocks_have_the_same_reviewed_time(self):
        for raw_time,expected in (('1600','16:00'),('0930','09:30'),('930','09:30'),('0000','00:00'),
                ('2359','23:59'),('at 1600','16:00'),('4 pm','16:00'),('4pm','16:00'),
                ('4:30 p.m.','16:30'),('4.30 PM','16:30'),('12 am','00:00'),('12 pm','12:00'),
                ('noon','12:00'),('midnight','00:00'),('four pm','16:00')):
            with self.subTest(raw_time=raw_time):
                self.assertEqual(clock_value(raw_time),expected)
                _,patch=parse_patch(raw(time=raw_time),'Start '+raw_time,PEOPLE,'2026-10-27')
                self.assertEqual(patch['time'],expected)
    def test_invalid_compact_and_contradictory_clocks_cannot_be_saved(self):
        for value in ('2400','1260','0060','1600 pm','0 am','13 pm','12345','1600:30','4.5 pm','4pm tomorrow'):
            with self.subTest(value=value),self.assertRaises(ValueError):clock_value(value)
    def test_end_clock_is_normalized_without_weakening_source_evidence(self):
        _,patch=parse_patch(raw(time='4 pm',end_time='1730'),'Start 4 pm until 1730',PEOPLE,'2026-10-27')
        self.assertEqual((patch['time'],patch['end_time']),('16:00','17:30'))
        with self.assertRaises(ValueError):parse_patch(raw(time='16:00'),'Start 4 pm',PEOPLE,'2026-10-27')
    def test_literal_clock_requires_dated_draft_and_whole_clock_reply(self):
        self.assertIsNone(literal_clock_patch('1600',{}))
        self.assertIsNone(literal_clock_patch('Remind me at 1600',{'date':'2026-11-05'}))
        self.assertIsNone(literal_clock_patch('One hour',{'date':'2026-11-05'}))

class ClockRouting(unittest.IsolatedAsyncioTestCase):
    async def test_short_clock_replies_work_without_calling_the_model(self):
        def fail(**kwargs):raise AssertionError('A literal clock should not call a model')
        extractor=CalendarDrafting(SimpleNamespace(reason_local=fail))
        for text,key,value in (('1600','time','16:00'),('4 pm','time','16:00'),('12 am','time','00:00'),('Until 1730','end_time','17:30')):
            intent,patch=await extractor.extract(text,PEOPLE,'2026-10-28',{'date':'2026-11-05'})
            self.assertEqual(intent,'continue');self.assertEqual(patch[key],value)
        with self.assertRaises(ValueError):await extractor.extract('2500',PEOPLE,'2026-10-28',{'date':'2026-11-05'})

class Extractor:
    def __init__(self):self.calls=[];self.responses={}
    async def extract(self,text,people,today,partial,speaker):
        self.calls.append((text,deepcopy(partial),speaker))
        if text not in self.responses:raise ValueError('Fictional extractor unavailable')
        return parse_patch(self.responses[text],text,people,today,speaker)

class CalendarChat(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.p=profile();self.c=Client();self.now=[datetime(2026,10,27,12,tzinfo=ZONE)];self.clock=[1]
        self.planner=HouseholdPlanner(self.p,self.c,[CALENDAR],now=lambda:self.now[0],clock=lambda:self.clock[0])
        self.planner.bootstrap([]);self.addCleanup(self.planner.db.close)
        self.e=Extractor();self.chat=CalendarConversation(self.planner,extractor=self.e,clock=lambda:self.clock[0])
        self.e.responses={START:raw('create',**DATA),'One hour':raw(duration='One hour'),
            'The venue is Fictional Hall':raw(venue='Fictional Hall'),'Venue unknown':raw(omit_venue='Venue unknown'),
            'That appointment is for Linda':raw('correct',members=['linda'],member_evidence='for Linda'),
            'What is the weather?':raw('unrelated')}
    async def say(self,text,key='chat-a',source='phone-a',actor='ha-user',write=True,prior=None):
        with calendar_scope({'actor':actor,'read':True,'write':write}):return await self.chat.handle(text,key,source,prior)
    async def review(self):
        a=await self.say(START);self.assertIn('How long',a['message'])
        b=await self.say('One hour');self.assertIn('Where',b['message'])
        out=await self.say('The venue is Fictional Hall');self.assertIn('Shall I save',out['message']);return out
    async def test_collect_review_correct_and_confirm_one_phone_event(self):
        out=await self.review();self.assertIn('Thursday 5 November 2026',out['message']);self.assertFalse(self.c.writes)
        out=await self.say('That appointment is for Linda');self.assertIn('for Linda',out['message']);self.assertFalse(self.c.writes)
        self.assertEqual((await self.say('Yes'))['status'],'success');self.assertEqual(len(self.c.writes),1)
        self.assertEqual(self.planner.assign(self.c.events[0])['members'],['linda'])
        self.assertIn('14:00:00+01:00',self.c.writes[0]['start_date_time'])
        self.assertEqual(self.c.writes[0]['location'],'Fictional Hall')
        await self.say('Yes');self.assertEqual(len(self.c.writes),1)
    async def test_venue_unknown_is_explicit_not_a_default(self):
        await self.say(START);await self.say('One hour');out=await self.say('Venue unknown')
        self.assertIn('no venue recorded',out['message']);await self.say('Confirm');self.assertNotIn('location',self.c.writes[0])
    async def test_compact_start_and_am_pm_end_are_reviewed_and_saved_as_norway_times(self):
        question='Add a dentist appointment for Mia next Thursday at 1600'
        self.e.responses[question]=raw('create',**{**DATA,'time':'1600'})
        self.e.responses['Until 5 pm']=raw(end_time='5 pm')
        await self.say(question);await self.say('Until 5 pm');out=await self.say('Venue unknown')
        self.assertIn('16:00–17:00',out['message']);self.assertFalse(self.c.writes)
        await self.say('yes')
        self.assertIn('T16:00:00+01:00',self.c.writes[0]['start_date_time'])
        self.assertIn('T17:00:00+01:00',self.c.writes[0]['end_date_time'])
    async def test_cancel_and_unrelated_turn_revoke_old_review(self):
        for last in ('Cancel','What is the weather?'):
            await self.review();await self.say(last);out=await self.say('yes');self.assertIsNone(out);self.assertFalse(self.c.writes)
        self.assertEqual(self.planner.db.execute("SELECT count(*) FROM intents WHERE state='prepared'").fetchone()[0],0)
    async def test_source_actor_profile_date_and_expiry_invalidate_confirmation(self):
        for mutation in ('source','actor','revision','date','expiry'):
            self.now[0]=datetime(2026,10,27,12,tzinfo=ZONE);self.clock[0]=1
            await self.review()
            if mutation=='revision':self.p._data['revision']+=1
            if mutation=='date':self.now[0]+=timedelta(days=1)
            if mutation=='expiry':self.clock[0]=302
            out=await self.say('yes',source='other' if mutation=='source' else 'phone-a',actor='other' if mutation=='actor' else 'ha-user')
            self.assertIn('expired or its context changed',out['message']);self.assertFalse(self.c.writes)
    async def test_permissions_default_deny_and_voice_never_grants_writes(self):
        with speaker_scope({'member_id':'benny','basis':'voice_match','conversation_id':'chat-a'},self.p,'chat-a'):
            out=await self.chat.handle(START,'chat-a','phone-a')
        self.assertEqual(out['status'],'forbidden');self.assertFalse(self.e.calls)
        await self.review();self.assertEqual((await self.say('yes',write=False))['status'],'forbidden');self.assertFalse(self.c.writes)
    async def test_distinct_conversation_cannot_confirm(self):
        await self.review();self.assertIsNone(await self.say('yes',key='chat-b'));self.assertFalse(self.c.writes)
        await self.say('yes');self.assertEqual(len(self.c.writes),1)
    async def test_simultaneous_confirm_and_replay_write_once(self):
        await self.review();await asyncio.gather(self.say('yes'),self.say('yes'));self.assertEqual(len(self.c.writes),1)
    async def test_duplicate_overlaps_and_changed_live_evidence(self):
        await self.review();await self.say('yes');out=await self.say(START);await self.say('One hour');out=await self.say('Venue unknown')
        self.assertIn('already in Familiekalender',out['message']);self.assertEqual(len(self.c.writes),1)
    async def test_failed_or_uncertain_save_does_not_retry(self):
        await self.review();self.c.after_write_error=True
        out=await self.say('yes');self.assertEqual(out['status'],'unavailable');await self.say('yes');self.assertEqual(len(self.c.writes),1)
    async def test_overlap_is_shown_and_a_new_overlap_requires_a_new_review(self):
        self.c.events=[{'summary':'Fictional overlap','start':'2026-11-05T14:30:00+01:00','end':'2026-11-05T15:30:00+01:00','description':description(['mia'],'sport','fictional-conflict','')}]
        out=await self.review();self.assertIn('Fictional overlap',out['message'])
        self.c.events.append({**self.c.events[0],'summary':'New conflict'})
        self.assertEqual((await self.say('yes'))['status'],'unavailable');self.assertFalse(self.c.writes)
    async def test_live_read_failure_and_past_start_do_not_write(self):
        await self.say(START);await self.say('One hour');self.c.fail=True
        self.assertEqual((await self.say('Venue unknown'))['status'],'unavailable');self.assertFalse(self.c.writes)
        self.c.fail=False
        self.e.responses['Add a dentist appointment for Mia today at 10:00 for one hour at Fictional Hall']=raw('create',**{**DATA,'date':'today','time':'10:00','duration':'one hour','venue':'Fictional Hall'})
        out=await self.say('Add a dentist appointment for Mia today at 10:00 for one hour at Fictional Hall')
        self.assertIn('already passed',out['message']);self.assertFalse(self.c.writes)
    async def test_speaker_relevance_change_invalidates_first_person_draft(self):
        with speaker_scope({'member_id':'benny','basis':'voice_match','conversation_id':'chat-a'},self.p,'chat-a'):await self.review()
        with speaker_scope({'member_id':'linda','basis':'voice_match','conversation_id':'chat-a'},self.p,'chat-a'):
            out=await self.say('yes');self.assertIn('context changed',out['message'])
        self.assertFalse(self.c.writes)
    async def test_model_failure_or_injected_extra_quote_cannot_write(self):
        self.e.responses[START]=raw('create',**{**DATA,'venue':'invented'})
        self.assertEqual((await self.say(START))['status'],'unavailable');await self.say('yes');self.assertFalse(self.c.writes)
    async def test_recurrence_and_reminder_never_silently_create_one_event(self):
        out=await self.say('Add a dentist appointment for Mia every Thursday');self.assertIn('phone calendar',out['message'])
        self.assertIsNone(await self.say('Add a reminder for Mia tomorrow'));self.assertFalse(self.c.writes)
    async def test_existing_assignment_uses_fresh_unique_source_and_no_google_write(self):
        self.c.events=[{'summary':'Fictional Club','start':'2026-11-05T14:00:00+01:00','end':'2026-11-05T15:00:00+01:00','description':description(['mia'],'sport','fictional-test-id','') }]
        self.e.responses['Correct the appointment for Linda next Thursday']=raw('correct',members=['linda'],member_evidence='for Linda',date='next Thursday')
        out=await self.say('Correct the appointment for Linda next Thursday')
        self.assertIn('phone calendar entry stays as it is',out['message']);await self.say('yes')
        self.assertEqual(self.planner.assign(self.c.events[0])['members'],['linda']);self.assertFalse(self.c.writes)
        # A phone edit to the authoritative header invalidates the old override.
        self.c.events[0]['description']=description(['emrik'],'sport','fictional-test-id','')
        self.assertEqual(self.planner.assign(self.c.events[0])['members'],['emrik'])
    async def test_changed_existing_event_invalidates_review(self):
        self.c.events=[{'summary':'Fictional Club','start':'2026-11-05T14:00:00+01:00','end':'2026-11-05T15:00:00+01:00'}]
        self.e.responses['Correct the appointment for Linda next Thursday']=raw('correct',members=['linda'],member_evidence='for Linda',date='next Thursday')
        await self.say('Correct the appointment for Linda next Thursday');self.c.events[0]['location']='Changed'
        out=await self.say('yes');self.assertEqual(out['status'],'unavailable');self.assertFalse(self.planner.manual_annotations())
    async def test_ambiguous_existing_event_is_numbered_and_reread(self):
        self.c.events=[{'summary':t,'start':'2026-11-05T14:00:00+01:00','end':'2026-11-05T15:00:00+01:00'} for t in ('Club A','Club B')]
        self.e.responses['Correct the appointment for Linda next Thursday']=raw('correct',members=['linda'],member_evidence='for Linda',date='next Thursday')
        out=await self.say('Correct the appointment for Linda next Thursday');self.assertIn('Which one?',out['message'])
        out=await self.say('2');self.assertIn('Club B',out['message']);await self.say('yes')
        self.assertFalse(self.planner.assign(self.c.events[0])['members']);self.assertEqual(self.planner.assign(self.c.events[1])['members'],['linda'])
    async def test_prior_selected_event_context_resolves_that_appointment(self):
        e={'summary':'Club A','start':'2026-11-05T14:00:00+01:00','end':'2026-11-05T15:00:00+01:00'};self.c.events=[e]
        prior={'start':'2026-11-05','end':'2026-11-06','source_focus':[(e['summary'],'family',e['start'],e['end'],('mia',))]}
        out=await self.say('That appointment is for Linda',prior=prior);self.assertIn('Club A',out['message']);await self.say('yes');self.assertFalse(self.c.writes)
    async def test_readonly_classification_uses_fresh_selected_event(self):
        e={'summary':'Club A','start':'2026-11-05T14:00:00+01:00','end':'2026-11-05T15:00:00+01:00','description':description(['mia'],'sport','fictional-read-id','')};self.c.events=[e]
        prior={'start':'2026-11-05','end':'2026-11-06','source_focus':[(e['summary'],'family',e['start'],e['end'],('mia',))]}
        out=await self.say('Who is that appointment for?',prior=prior,write=False)
        self.assertEqual(out['status'],'success');self.assertIn('Mia',out['message']);self.assertIn('sport',out['message']);self.assertFalse(self.c.writes);self.assertFalse(self.e.calls)
    async def test_application_and_authenticated_bridge_use_the_same_review(self):
        from jarvis.homeassistant.conversation_bridge import JarvisConversationBridge
        from types import MethodType
        root=Path(__file__).resolve().parents[1]
        source=root/'src/jarvis/core/application.py'
        if not source.exists():source=root/'jarvis/app/src/jarvis/core/application.py'
        method=next(n for n in ast.walk(ast.parse(source.read_text(encoding='utf-8'))) if isinstance(n,ast.AsyncFunctionDef) and n.name=='handle_request')
        namespace={'asyncio':asyncio};exec(compile(ast.Module(body=[method],type_ignores=[]),'<calendar application>','exec'),namespace)
        self.p._source_path=Path('/fictional/no-file-is-created.json')
        cancelled=[]
        app=SimpleNamespace()
        app.handle_request=MethodType(namespace['handle_request'],app)
        app._user_message=lambda result:result['message']
        app.container=SimpleNamespace(household_profile=self.p,home_assistant=self.c,household_planner=self.planner,
            calendar_conversation=self.chat,natural_memory_controller=SimpleNamespace(cancel_confirmation=cancelled.append),
            conversation_store=SimpleNamespace(normalize_conversation_id=lambda value:value))
        app._pending_action_payloads={}
        bridge=JarvisConversationBridge(app);bridge._pending_by_conversation['chat-a']=('memory','old-unrelated-review')
        access={'actor':'ha-user','read':True,'write':True}
        for q in (START,'One hour','Venue unknown'):
            out=await bridge.process(q,conversation_id='chat-a',source_id='phone-a',calendar_context=access)
            self.assertEqual(out['status'],'clarification_required')
        self.assertEqual(cancelled,['old-unrelated-review']);self.assertFalse(self.c.writes)
        out=await bridge.process('yes',conversation_id='chat-a',source_id='phone-a',calendar_context=access)
        self.assertEqual(out['status'],'success');self.assertEqual(len(self.c.writes),1)

class HAAccess(unittest.IsolatedAsyncioTestCase):
    async def test_actual_adapter_method_uses_authenticated_entity_permissions(self):
        root=Path(__file__).resolve().parents[1]
        source=root/'home_assistant/custom_components/jarvis_conversation/conversation.py'
        if not source.exists():source=root/'custom_components/jarvis_conversation/conversation.py'
        tree=ast.parse(source.read_text(encoding='utf-8'))
        fn=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name=='_calendar_access')
        fn=deepcopy(fn);fn.body=[n for n in fn.body if not isinstance(n,ast.ImportFrom)]
        namespace={'POLICY_READ':'read','POLICY_CONTROL':'control'};exec(compile(ast.Module(body=[fn],type_ignores=[]),'adapter','exec'),namespace)
        grants={('calendar.familiekalender','read'),('calendar.familiekalender','control'),('calendar.work_reach','read')}
        user=SimpleNamespace(id='shared-ha-user',permissions=SimpleNamespace(check_entity=lambda e,p:(e,p) in grants))
        async def get_user(identifier):return user if identifier=='shared-ha-user' else None
        obj=SimpleNamespace(hass=SimpleNamespace(auth=SimpleNamespace(async_get_user=get_user),states=SimpleNamespace(get=lambda e:e=='calendar.work_reach')))
        inp=SimpleNamespace(context=SimpleNamespace(user_id='shared-ha-user'))
        self.assertTrue((await namespace['_calendar_access'](obj,inp))['write'])
        grants.remove(('calendar.work_reach','read'));self.assertFalse((await namespace['_calendar_access'](obj,inp))['write'])
        inp.context.user_id=None;self.assertFalse((await namespace['_calendar_access'](obj,inp))['read'])

class AccessScope(unittest.TestCase):
    def test_strict_request_context_and_reset(self):
        self.assertFalse(current_calendar_access.get().write)
        with calendar_scope({'actor':'ha-user','read':True,'write':True}):self.assertTrue(current_calendar_access.get().write)
        self.assertFalse(current_calendar_access.get().write)
        for value in ({'actor':'u','read':False,'write':True},{'actor':'u','read':True,'write':'yes'},{'actor':'u','read':True,'write':True,'speaker':'benny'}):
            with self.assertRaises(ValueError):
                with calendar_scope(value):pass
