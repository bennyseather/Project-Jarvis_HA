"""Synthetic household/calendar/voice relevance. No real profiles or services."""
import asyncio
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from jarvis.household_profile import HouseholdProfile
from jarvis.household_speaker import speaker_scope
from jarvis.household_memory import memory_question
from jarvis.household_briefing import HouseholdBriefing, SOURCES, interval

ZONE=ZoneInfo('Europe/Oslo')


def document():
    return {'schema_version':1,'revision':1,'roster_complete':True,'assistant':{'name':'Jarvis'},
        'members':[{'id':'benny','preferred_name':'Benny','birth_date':{'status':'confirmed','value':'2000-02-03'},
            'employment':{'status':'confirmed','role':'Synthetic tester','employer':'Fixture company'}},
            {'id':'mia','preferred_name':'Mia'}, {'id':'linda','preferred_name':'Linda'}],
        'sharing_policy':{'directory_enabled':True,'source':'Synthetic approval','recorded_on':'2026-10-21',
            'relationships':[],'knowledge_access':{'mode':'shared_household','source':'Synthetic approval','recorded_on':'2026-10-21'}},
        'conversational_updates':{'mode':'shared_confirmation','source':'Synthetic approval'}}


def scope(profile,person,key='session'):
    return speaker_scope({'member_id':person,'basis':'voice_match' if person else 'unknown','conversation_id':key},profile,key)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'profile.json';self.path.write_text(json.dumps(document()))
        self.profile=HouseholdProfile.load(self.path)
    def ask(self,text,key='session'):return self.profile.edit_request(text,key)
    def test_first_person_confirmation_persist_review(self):
        before=self.path.read_bytes()
        with scope(self.profile,'benny'):
            p=self.ask('Please remember that I prefer quiet mornings')
            self.assertIn('Benny prefers quiet mornings',p['message']);self.assertEqual(before,self.path.read_bytes())
            self.assertIn('Saved household',self.ask('yes')['message'])
            review=memory_question('What do you remember about me?',self.profile)
            self.assertIn('You work as Synthetic tester',review['message'])
            self.assertIn('quiet mornings',review['message'])
        self.assertEqual(len(HouseholdProfile.load(self.path)._data['conversation_notes']),1)
    def test_unknown_cannot_bind_my_but_named_shared_save_works(self):
        with scope(self.profile,None):
            self.assertIn('Whose',self.ask('Remember I like painting')['message'])
            self.assertIn('Whose',memory_question('What do you know about me?',self.profile)['message'])
            self.ask('Remember Mia likes painting');self.assertIn('Saved household',self.ask('yes')['message'])
            self.assertIn('Mia likes painting',memory_question('What do you remember about Mia?',self.profile)['message'])
    def test_natural_replace_forget_and_undo(self):
        self.ask('Remember Mia likes red');self.ask('confirm household change')
        self.ask('Change "Mia likes red" to "Mia likes blue"');self.ask('confirm household change')
        self.assertEqual(self.profile._data['conversation_notes'][0]['text'],'Mia likes blue')
        result=self.ask('Forget "Mia likes blue"');self.assertIn('Proposed',result['message'])
        self.assertIn('secure erasure',result['message']);self.ask('confirm household change')
        self.assertEqual(self.profile._data['conversation_notes'],[])
        self.ask('undo last household change');self.ask('confirm household change')
        self.assertEqual(self.profile._data['conversation_notes'][0]['text'],'Mia likes blue')
    def test_duplicate_note_does_not_increment_revision(self):
        self.ask('Remember Mia likes painting');self.ask('confirm household change')
        before=self.path.read_bytes();r=self.ask('Remember mia likes painting')
        self.assertIn('already',r['message']);self.assertEqual(before,self.path.read_bytes())
    def test_unrelated_turn_and_voice_switch_cannot_confirm_bare_yes(self):
        with scope(self.profile,'benny'):self.ask('Remember I like coffee')
        with scope(self.profile,'linda'):
            self.assertIn('review',self.ask('yes')['message'])
            self.assertIn('Saved household',self.ask('confirm household change')['message'])
        self.ask('Remember the fixture is blue');self.profile._edits.observe_turn('What is the weather?','session')
        self.assertIsNone(self.ask('yes'))
    def test_unknown_note_cancel_secrets_and_stale_conflict(self):
        self.assertIn('Nothing was removed',self.ask('Forget "not saved"')['message'])
        self.ask('Remember Mia likes painting');self.ask('no')
        self.assertIn('no pending',self.ask('confirm household change')['message'])
        self.assertIn('passwords',self.ask('Remember the API key is synthetic')['message'])
        self.ask('Remember the rug is red','a');self.ask('Remember the rug is blue','b');self.ask('confirm household change','b')
        self.assertIn('changed since',self.ask('confirm household change','a')['message'])
    def test_invalid_new_proposal_clears_old_yes_and_raw_key_rejected(self):
        self.ask('Remember Mia likes painting')
        self.ask('Remember the API key is synthetic')
        self.assertIsNone(self.ask('yes'))
        before=self.path.read_bytes()
        self.assertIn('passwords',self.ask('Remember sk-fixture_synthetic_only_abcdef')['message'])
        self.assertEqual(before,self.path.read_bytes())
    def test_reasoning_notes_are_bounded_attributed_and_not_saved_again(self):
        for i in range(12):
            self.ask('Remember Mia likes fixture colour '+str(i));self.ask('confirm household change')
        self.ask('Remember Linda prefers fixture tea');self.ask('confirm household change')
        before=self.path.read_bytes()
        selected=self.profile.reasoning_context('What does Mia prefer?')
        self.assertEqual(len(selected['shared_household_notes']),8)
        self.assertNotIn('Linda prefers',str(selected['shared_household_notes']))
        self.assertEqual(len(self.profile.context()['shared_household_notes']),13)
        self.assertEqual(before,self.path.read_bytes())
    def test_confirmed_style_update_and_forget_without_extra_store(self):
        with scope(self.profile,'benny'):
            self.ask('Remember I prefer short answers');self.ask('yes')
            self.assertEqual(self.profile.reasoning_context('What do I prefer?')['speaker_presentation_preference'],'concise')
            r=self.ask('Remember I prefer detailed answers');self.assertIn('Update confirmed answer-length',r['message'])
            self.ask('yes');self.assertEqual(len(self.profile._data['conversation_notes']),1)
            self.assertEqual(self.profile.reasoning_context('What do I prefer?')['speaker_presentation_preference'],'detailed')
            self.ask('Forget "Benny prefers detailed answers"');self.ask('yes')
            self.assertEqual(self.profile.reasoning_context('What do I prefer?')['speaker_presentation_preference'],'balanced')
    def test_extended_family_memory_uses_approved_relationships(self):
        self.profile._data['extended_family']=[{'id':'fixture_guest','preferred_name':'Casey','source':'Synthetic report','recorded_on':'2026-10-21'}]
        self.profile._data['sharing_policy']['relationships'].append('Casey is a relative of Benny')
        r=memory_question('What do you remember about Casey?',self.profile)
        self.assertIn('Casey is a relative of Benny',r['message'])
        self.assertNotIn('Which household member',r['message'])


def event(title,start,end):return {'summary':title,'start':start,'end':end}


class Client:
    def __init__(self):self.calls=[];self.fail=set();self.bad_summary=False;self.events={name:[] for name in SOURCES}
    async def call_service_response(self,domain,service,data):
        assert (domain,service)==('calendar','get_events')
        name=next(n for n,e in SOURCES.items() if e==data['entity_id']);self.calls.append(name)
        if name in self.fail:raise RuntimeError('fixture outage')
        return {data['entity_id']:{'events':self.events[name]}}
    async def get_household_today(self,period,*,start_date,end_date):
        start=datetime.fromisoformat(start_date);end=datetime.fromisoformat(end_date)
        days=[]
        while start<end:
            days.append({'date':start.date().isoformat(),'timezone':'Europe/Oslo','cards':[
                {'title':'Mia · usual school','lines':['08:15–13:30','Term dates/holidays and attendance are not confirmed.']},
                {'title':'Linda · usual work','lines':['Leave for work around 08:00; finish around 16:00.']}],
                'calendar':{'status':'available','events':[]}});start+=timedelta(days=1)
        return {'read_only':not self.bad_summary,'planning':{'generated_on':'2026-10-21','timezone':'Europe/Oslo','days':days}}


class BriefingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.profile=HouseholdProfile(document());self.client=Client()
        self.clock=[datetime(2026,10,21,12,tzinfo=ZONE)]
        self.brief=HouseholdBriefing(self.profile,self.client,SOURCES.values(),now=lambda:self.clock[0])
    async def ask(self,text,person='benny',key='session'):
        with scope(self.profile,person,key):return await self.brief.handle(text,key)
    async def test_personal_day_work_travel_cities_and_no_family_misattribution(self):
        self.client.events['work']=[event('Fixture meeting','2026-10-21T09:00:00+02:00','2026-10-21T10:00:00+02:00')]
        self.client.events['travel']=[event('LH9796 · SIN → PER','2026-10-21T18:00:00+08:00','2026-10-21T23:00:00+08:00')]
        r=await self.ask('What does my day look like?')
        self.assertIn('your briefing',r['message']);self.assertIn('Fixture meeting',r['message'])
        self.assertIn('Singapore to Perth',r['message']);self.assertNotIn('Mia’s family calendar',r['message'])
        self.assertEqual(self.client.calls,['work','travel']);self.assertFalse(r['cacheable'])
        self.assertNotIn('any shared plans recorded',r['message'])
    async def test_named_child_and_unknown_my_briefing(self):
        r=await self.ask('What does my day look like?',None)
        self.assertIn('Whose',r['message']);self.assertEqual(self.client.calls,[])
        r=await self.ask("What does Mia's day look like tomorrow?",None)
        self.assertIn("Mia's briefing",r['message']);self.assertIn('usual school',r['message'])
        self.assertEqual(self.client.calls,['family'])
    async def test_next_filters_past_and_distinguishes_ongoing(self):
        self.client.events['work']=[event('Past','2026-10-21T09:00:00+02:00','2026-10-21T10:00:00+02:00'),
            event('Current','2026-10-21T11:00:00+02:00','2026-10-21T13:00:00+02:00'),
            event('Next','2026-10-21T14:00:00+02:00','2026-10-21T15:00:00+02:00')]
        r=await self.ask("What's next for me?")
        self.assertNotIn('“Past”',r['message']);self.assertIn('currently scheduled',r['message']);self.assertIn('“Next”',r['message'])
    async def test_followups_same_speaker_only_and_unrelated_clears(self):
        await self.ask('Give me my briefing for next week')
        r=await self.ask('And the following week?');self.assertEqual(r['period']['start'],'2026-11-02')
        self.assertIsNone(await self.ask('And tomorrow?','linda'))
        await self.ask('Give us a household briefing');self.assertIsNone(await self.ask('Turn off the lights'))
        self.assertIsNone(await self.ask('And tomorrow?'))
    async def test_failure_not_empty_and_personal_calendar_ownership(self):
        self.client.fail={'travel'}
        r=await self.ask('Give me my briefing')
        self.assertIn('travel calendar temporarily unavailable',r['message']);self.assertIn('unknown, not empty',r['message'])
        self.client.calls=[];r=await self.ask("What does Linda's day look like?")
        self.assertEqual(self.client.calls,[]);self.assertIn('do not have a connected personal calendar for Linda',r['message'])
    async def test_cancelled_duplicate_and_all_day_overlap(self):
        fixture=event('All day','2026-10-20','2026-10-22')
        self.client.events['family']=[fixture,dict(fixture),{**fixture,'status':'cancelled'}]
        r=await self.ask('Give us a household briefing')
        self.assertEqual(r['message'].count('“All day”'),1);self.assertIn('all day',r['message'])
    async def test_unconnected_or_stale_sources_are_honest(self):
        self.brief.allowed=frozenset();self.client.bad_summary=True
        r=await self.ask('Give me my briefing')
        self.assertIn('not connected or not shared',r['message']);self.assertIn('could not be read',r['message'])
        self.assertEqual(self.client.calls,[])
    async def test_domain_actions_bad_date_and_rollover(self):
        for q in ('When is my next travel to Perth?','What is next for the lights?',
                  'What should I know about the weather?',"What should I know about Linda's job?",
                  'What do we have planned after school tomorrow?',
                  'Remember my breakfast preference','What is Mia doing today?'):
            self.assertIsNone(await self.ask(q),q)
        r=await self.ask('Give me my briefing yesterday');self.assertEqual(r['status'],'clarification_required')
        await self.ask('Give me my briefing');self.clock[0]+=timedelta(days=1)
        self.assertIsNone(await self.ask('And tomorrow?'))
    async def test_all_day_and_dst_bounds(self):
        self.assertEqual((interval(event('DST','2026-10-25','2026-10-26'))['end'].timestamp()-interval(event('DST','2026-10-25','2026-10-26'))['start'].timestamp())/3600,25)
        with self.assertRaises(ValueError):interval(event('No timezone','2026-10-21T12:00:00','2026-10-21T13:00:00'))
    async def test_natural_personal_plan_variants(self):
        for question in ('What do I have on today?', 'What have I got on tomorrow?',
                         'What is on my calendar today?', 'What should I prepare for tomorrow?',
                         'What does my week look like?'):
            r=await self.ask(question);self.assertEqual(r['provider'],'household_briefing',question)
            self.assertRegex(r['message'],r'your (?:next-up )?briefing')
    async def test_full_day_more_and_no_silent_calendar_truncation(self):
        self.client.events['work']=[event('Fixture '+str(i),f'2026-10-21T{i:02}:00:00+02:00',f'2026-10-21T{i:02}:30:00+02:00') for i in range(22)]
        r=await self.ask('Give me my briefing');self.assertEqual(r['message'].count('“Fixture'),6)
        self.assertIn('more appointments',r['message'])
        r=await self.ask('Tell me more');self.assertEqual(r['message'].count('“Fixture'),20)
        self.assertIn('shorter date range',r['message'])
    async def test_cancel_stale_inflight_result_on_unrelated_turn(self):
        started=asyncio.Event();finish=asyncio.Event();original=self.client.get_household_today
        async def slow(*a,**k):started.set();await finish.wait();return await original(*a,**k)
        self.client.get_household_today=slow
        first=asyncio.create_task(self.ask('Give me my briefing'));await started.wait()
        self.assertIsNone(await self.ask('What is the weather?'));finish.set()
        self.assertIn('superseded',(await first)['message'])
    async def test_profile_change_during_request_requires_fresh_read(self):
        original=self.client.get_household_today
        async def changed(*a,**k):
            d=await original(*a,**k);self.profile._data['revision']+=1;return d
        self.client.get_household_today=changed
        self.assertEqual((await self.ask('Give me my briefing'))['status'],'unavailable')
    async def test_invalid_event_fails_whole_source_not_empty(self):
        self.client.events['work']=[event('Missing timezone','2026-10-21T12:00:00','2026-10-21T13:00:00')]
        r=await self.ask('Give me my briefing')
        self.assertIn('work calendar temporarily unavailable',r['message'])
    async def test_overlap_same_owner_but_never_assign_child_activity(self):
        self.client.events['work']=[event('Meeting','2026-10-21T14:00:00+02:00','2026-10-21T15:00:00+02:00')]
        self.client.events['family']=[event('Child activity','2026-10-21T14:00:00+02:00','2026-10-21T15:00:00+02:00')]
        r=await self.ask('Give us a household briefing');self.assertNotIn('entries overlap',r['message'])
        self.client.events['travel']=[event('Airport transfer','2026-10-21T14:30:00+02:00','2026-10-21T15:30:00+02:00')]
        r=await self.ask('Give us a household briefing');self.assertIn('entries overlap',r['message'])
        self.assertNotIn('Child activity” and',r['message'])
    async def test_duplicate_between_work_and_travel_and_concise_preference(self):
        fixture=event('Copied entry','2026-10-21T14:00:00+02:00','2026-10-21T15:00:00+02:00')
        self.client.events['work']=[fixture]+[event('More '+str(i),f'2026-10-21T{i+16}:00:00+02:00',f'2026-10-21T{i+16}:30:00+02:00') for i in range(4)]
        self.client.events['travel']=[dict(fixture)]
        self.profile._data['conversation_notes']=[{'id':'abcdef12','text':'Benny prefers concise answers'}]
        r=await self.ask('Give me my briefing')
        self.assertEqual(r['message'].count('“Copied entry”'),1)
        self.assertEqual(r['message'].count('“More '),2)
        self.assertIn('more appointments',r['message'])
    async def test_weekly_birthday_not_lost_among_empty_routine_days(self):
        original=self.client.get_household_today
        async def birthday(*a,**k):
            d=await original(*a,**k)
            d['planning']['days'][1]['cards'].append({'title':'Birthday','lines':['Benny has a birthday on this date.']})
            return d
        self.client.get_household_today=birthday
        r=await self.ask('What does my week look like?')
        self.assertIn('Benny has a birthday',r['message']);self.assertNotIn('No approved shared',r['message'])
    async def test_multiday_timed_event_uses_end_date_not_start_date(self):
        self.client.events['travel']=[event('Fixture stay','2026-10-19T15:00:00+02:00','2026-10-22T12:00:00+02:00')]
        r=await self.ask("What's next for me?")
        self.assertIn('until Thu 22 Oct at 12:00',r['message'])
    async def test_malformed_routine_cards_do_not_crash_other_live_sources(self):
        original=self.client.get_household_today
        async def malformed(*a,**k):
            d=await original(*a,**k);d['planning']['days'][0]['cards']=None;return d
        self.client.get_household_today=malformed
        r=await self.ask('Give me my briefing');self.assertIn('routine summary could not be read',r['message'])


class ApplicationBundleTests(unittest.IsolatedAsyncioTestCase):
    async def test_household_proposal_cancels_older_generic_memory_confirmation(self):
        from jarvis.homeassistant.conversation_bridge import JarvisConversationBridge
        cancelled=[]
        async def handle(*a,**k):
            return {'status':'clarification_required','provider':'household_edits','message':'Proposed fixture note'}
        app=SimpleNamespace(container=SimpleNamespace(household_profile=HouseholdProfile(document()),
            conversation_store=SimpleNamespace(normalize_conversation_id=lambda x:x),
            natural_memory_controller=SimpleNamespace(cancel_confirmation=cancelled.append)),
            handle_request=handle,_user_message=lambda r:r['message'])
        bridge=JarvisConversationBridge(app);bridge._pending_by_conversation['session']=('memory','old-fixture-token')
        r=await bridge.process('Remember a new shared household fact',conversation_id='session')
        self.assertIn('Proposed',r['message']);self.assertEqual(cancelled,['old-fixture-token'])
        self.assertNotIn('session',bridge._pending_by_conversation)

    async def test_other_speaker_does_not_inherit_planning_topic(self):
        from jarvis.household_planning import HouseholdConversation,Plan
        async def unexpected(*a,**k):raise AssertionError('Unrelated speaker must not inherit planning')
        profile=HouseholdProfile(document());conversation=HouseholdConversation(unexpected,None)
        conversation.planning.seed('session::household-speaker:benny',Plan(('mia',),'school_end','2026-10-29','2026-10-30'))
        with scope(profile,'linda'):
            self.assertIsNone(await conversation.handle('And Friday?','session'))

    async def test_real_request_gate_preserves_voice_binding_and_fresh_data(self):
        import ast
        path=Path('src/jarvis/core/application.py')
        if not path.exists():path=Path('jarvis/app/src/jarvis/core/application.py')
        source=path.read_text()
        method=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.AsyncFunctionDef) and n.name=='handle_request')
        env={'asyncio':asyncio};exec(compile(ast.Module(body=[method],type_ignores=[]),'<real request gate>','exec'),env)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'profile.json';p.write_text(json.dumps(document()));profile=HouseholdProfile.load(p)
            client=Client()
            client.get_household_today=unittest.mock.AsyncMock(return_value={'read_only':True,'planning':{
                'generated_on':datetime.now(ZONE).date().isoformat(),'timezone':'Europe/Oslo','days':[{
                'date':datetime.now(ZONE).date().isoformat(),'timezone':'Europe/Oslo','cards':[]}]}})
            app=SimpleNamespace(container=SimpleNamespace(household_profile=profile,home_assistant=client,
                proactive_allowed_entities=SOURCES.values()))
            with scope(profile,'benny'):
                for q in ('Remember I prefer concise answers','yes'):
                    r=await env['handle_request'](app,q,'session');self.assertIn('household',r['provider'])
                r=await env['handle_request'](app,'What do you remember about me?','session')
                self.assertIn('Benny prefers concise answers',r['message'])
                r=await env['handle_request'](app,'What does my day look like?','session')
                self.assertEqual(r['provider'],'household_briefing')
                self.assertIn('your briefing',r['message'])
            with scope(profile,None):
                r=await env['handle_request'](app,'What does my day look like?','session')
                self.assertEqual(r['status'],'clarification_required')


if __name__=='__main__':unittest.main()
