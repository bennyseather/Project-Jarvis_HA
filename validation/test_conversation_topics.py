"""Topic returns are fresh read references, scoped to the current conversation."""
import unittest
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from jarvis.calendar_context import calendar_scope
from jarvis.household_speaker import speaker_scope
from jarvis.companion_agent import PROMPT
from jarvis.conversation_topics import resumed_request
import test_companion_agent as agent_fixture
from test_companion_agent import plan
from test_companion_read_context import frame

class TopicTests(unittest.IsolatedAsyncioTestCase):
    setUp = agent_fixture.AgentTests.setUp
    def scope(self, **kw):
        return calendar_scope({'actor':kw.get('actor','user'),'read':kw.get('read',True),'write':kw.get('write',True)})
    def selected(self, key='chat', **kw):
        state=self.a.agent.state(key,'phone')
        state['read_focus']={**dict(subjects=['mia'],start='2026-10-29',end='2026-10-30',question='What should Mia bring to band rehearsal tomorrow?',task='What should Mia bring to band rehearsal tomorrow?',purpose='preparation',window='all_day',between=False,duration_minutes=None,event_focus=[['Band rehearsal','family','2026-10-29T15:40:00+01:00','2026-10-29T16:00:00+01:00',['mia']]],expires=601),**kw}
        self.a.agent.topics.observe(state['read_focus']['question'],'appointments',{'status':'success'},['mia'],state)
        return state
    async def resume(self,text,state,id='1',quote=''):
        with patch('jarvis.conversation_topics.local_json',new=AsyncMock(return_value={'reference':id})):
            return await self.a.agent.topics.resume(text,state)
    async def test_return_restores_selected_task_only_after_three_other_topics(self):
        with self.scope():
            state=self.selected();expected=deepcopy(state['read_focus'])
            for text in ('What is stereo?','What is high fidelity?','How do speakers work?'):
                self.a.agent.reads.observe(text,'general',{'status':'success'},[],state)
                self.a.agent.topics.observe(text,'general',{'status':'success'},[],state)
            self.assertNotIn('read_focus',state)
            self.assertIs(await self.resume("Back to Mia's rehearsal, what should she bring?",state),False)
            self.assertEqual(state['read_focus']['event_focus'],expected['event_focus'])
            self.assertEqual(state['read_focus']['start'],'2026-10-29');self.assertEqual(state['history'],[])
            self.assertEqual(state['returned_topic']['subjects'],['mia'])
    async def test_explicit_return_is_required(self):
        with self.scope():
            state=self.selected();state.pop('read_focus')
            with patch('jarvis.conversation_topics.local_json',new=AsyncMock()) as model:
                self.assertIsNone(await self.a.agent.topics.resume('What is high fidelity audio?',state));model.assert_not_awaited()
            self.assertNotIn('read_focus',state)
    async def test_ambiguous_or_unknown_reference_does_not_change_active_task(self):
        with self.scope():
            state=self.selected();before=deepcopy(state['read_focus'])
            for id in ('ambiguous','','unknown'):
                self.assertIn('Which earlier topic',await self.resume('Back to that',state,id=id))
                self.assertEqual(state['read_focus'],before)
    async def test_expired_reference_is_not_renewed_by_return(self):
        with self.scope():
            state=self.selected();self.clock[0]=1802
            self.assertIn('Which earlier topic',await self.a.agent.topics.resume('Back to Mia',state))
            self.assertEqual(state['topic_references'],[])
    async def test_does_not_copy_facts_answers_or_review_tokens(self):
        with self.scope():
            state=self.selected();state['read_focus']['secret_answer']='cached organiser instruction';state['read_focus']['review_token']='old token'
            self.a.agent.topics.observe('What should Mia bring?','appointments',{'status':'success','message':'cached answer','token':'token'},['mia'],state)
            refs=repr(state['topic_references']);self.assertNotIn('cached',refs);self.assertNotIn('token',refs)
    async def test_topic_return_does_not_restore_slots_identity_or_write_review(self):
        with self.scope():
            state=self.selected();state['introduced']='benny';state['pending_identity']=False
            state.update(route_pending={'awaiting':'mode'},meal_route_pending={'missing':['venue']},activity_focus={'title':'other'})
            await self.resume('Back to rehearsal',state)
            self.assertEqual(state['introduced'],'benny');self.assertNotIn('route_pending',state);self.assertNotIn('meal_route_pending',state);self.assertNotIn('activity_focus',state);self.assertNotIn('planning_review',state['topic_references'][0])
    async def test_journal_is_bounded_and_same_task_deduplicated(self):
        with self.scope():
            state=self.selected();self.selected();self.assertEqual(len(state['topic_references']),1)
            for n in range(15):self.selected(start='2026-11-'+str(n+1).zfill(2))
            self.assertEqual(len(state['topic_references']),8);self.assertEqual(len(set(r['id'] for r in state['topic_references'])),8)
    async def test_failed_or_mutating_operations_are_not_returnable_reads(self):
        with self.scope():
            state=self.a.agent.state('chat','phone')
            for tool,result in [('calendar',{'status':'success'}),('appointments',{'status':'unavailable'}),('planning_report',{'status':'success'}),('identity',{'status':'success'}),('memory',{'status':'success'})]:
                state['_topic_operation']='write';self.a.agent.topics.observe('Save this',tool,result,['mia'],state)
            self.assertFalse(state.get('topic_references'))
    async def test_invalid_selection_shape_and_nonquoted_request_are_rejected(self):
        with self.scope():
            state=self.selected()
            with patch('jarvis.conversation_topics.local_json',new=AsyncMock(return_value={'reference':'1','request_quote':'','token':'invented'})):
                with self.assertRaises(ValueError):await self.a.agent.topics.resume('Back to rehearsal',state)
    async def test_actor_source_voice_revision_day_and_permission_changes_drop_references(self):
        with self.scope():
            old=self.selected()
            self.assertFalse(self.a.agent.state('new-chat','phone').get('topic_references'))
            self.assertFalse(self.a.agent.state('chat','tablet').get('topic_references'))
            self.selected()
        with self.scope(actor='other'):self.assertFalse(self.a.agent.state('chat','phone').get('topic_references'))
        with self.scope():self.selected();self.profile._data['revision']+=1;self.assertFalse(self.a.agent.state('chat','phone').get('topic_references'));self.selected()
        with self.scope(write=False):self.assertFalse(self.a.agent.state('chat','phone').get('topic_references'))
        with self.scope():
            self.selected();self.container.proactive_allowed_entities=('calendar.new',);self.assertFalse(self.a.agent.state('chat','phone').get('topic_references'))
            self.selected();self.a.now=lambda:__import__('test_companion_coordinator').NOW+timedelta(days=1);self.assertFalse(self.a.agent.state('chat','phone').get('topic_references'))
            self.selected()
            with speaker_scope({'member_id':'benny','basis':'voice_match','conversation_id':'chat'},self.profile,'chat'):self.assertFalse(self.a.agent.state('chat','phone').get('topic_references'))
    async def test_scope_change_clears_travel_and_pending_reviews(self):
        travel=SimpleNamespace(clear_context=__import__('unittest.mock',fromlist=['Mock']).Mock())
        self.container.travel_calendar_intelligence=travel
        with self.scope():self.selected();self.a.intake_pending['chat']={'old':'subject'}
        with self.scope(write=False):self.a.agent.state('chat','phone')
        travel.clear_context.assert_called_once_with('chat');self.assertNotIn('chat',self.a.intake_pending)
    async def test_permission_change_while_model_runs_prevents_dispatch(self):
        async def changed(*args):self.container.proactive_allowed_entities=('calendar.changed',);return plan('home')
        with self.scope(),patch.object(self.a.agent,'plan',new=changed):
            r=await self.a.process(AsyncMock()(),'What is the weather?','chat','phone')
        self.assertEqual(r['status'],'unavailable')
    async def test_read_question_cannot_select_report_or_memory_write(self):
        with self.scope():
            state=self.selected()
            for text in ('Is her instrument packed?','What did Mia prepare?','Tell me what is ready'):
                with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'tool':'planning_report','members':['mia']})) as model:
                    with self.assertRaises(ValueError):await self.a.agent.plan(text,'chat','phone',state)
                available=model.call_args.args[3]['properties']['tool']['enum'];self.assertNotIn('planning_report',available);self.assertNotIn('remember_detail',available)
    async def test_broader_activity_label_preserves_same_selected_rehearsal(self):
        with self.scope():
            state=self.selected();self.container.household_thinking=None
            f=frame(purpose='preparation',event_relation='continue')
            with patch('jarvis.companion_read_context.local_json',new=AsyncMock(return_value=f)):
                resolved=await self.a.agent.reads.resolve("Back to Mia's rehearsal, what should she bring?",'appointments',['mia'],state)
            self.assertEqual(resolved['source_focus'],state['read_focus']['event_focus'])
    async def test_prompt_fits_provider_budget(self):
        self.assertLessEqual(len(PROMPT),6000)

    async def test_return_prefix_does_not_hide_table_request_from_executor(self):
        with self.scope():
            state=self.a.agent.state('chat','phone');state['returned_topic']={'tool':'football','subjects':[],'question':'United news'}
            self.a.football.read=AsyncMock(return_value={'status':'success','message':'fresh table'})
            result=await self.a.agent.execute(plan('football'),'Back to United, show me the table','chat','phone',state,AsyncMock())
            self.a.football.read.assert_awaited_once_with('show me the table',state=state)
    async def test_return_prefix_never_strips_a_normal_request(self):
        self.assertEqual(resumed_request('Tell me about Mia, and Friday'),'Tell me about Mia, and Friday')
        self.assertEqual(resumed_request('Back to Mia'),'Back to Mia')
        self.assertEqual(resumed_request("Back to Mia's rehearsal, where is it?"),'where is it?')
    async def test_booked_personal_trip_is_a_sourced_capability(self):
        with self.scope():
            state=self.a.agent.state('chat','phone')
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'tool':'booked_travel','members':['benny']})) as model:
                await self.a.agent.plan('When is my next trip to Perth?','chat','phone',state)
            self.assertEqual(model.call_args.args[3]['properties']['tool']['enum'],['booked_travel'])
    async def test_general_cannot_fabricate_personal_birthday(self):
        with self.scope():
            state=self.selected()
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'tool':'general_chat','members':['mia']})) as model:
                with self.assertRaises(ValueError):await self.a.agent.plan('And her birthday?','chat','phone',state)
            self.assertEqual(model.call_args.args[3]['properties']['tool']['enum'],['household_facts']);self.assertEqual(model.await_count,1)

    async def test_general_topics_remain_distinct_and_public_topics_have_no_person(self):
        with self.scope():
            state=self.a.agent.state('chat','phone')
            for text in ('What is high fidelity?','How does a loudspeaker work?'):
                self.a.agent.topics.observe(text,'general',{'status':'success'},['benny'],state)
            self.assertEqual(len(state['topic_references']),2)
            state['football_topic']='standings';self.a.agent.topics.observe('Show the league table','football',{'status':'success'},['benny','mia'],state)
            self.assertEqual(state['topic_references'][-1]['subjects'],[])

    async def test_unsuccessful_return_also_discards_pending_changes(self):
        with self.scope():
            state=self.selected();state['planning_review']={'session':'expired-session','token':'old'}
            self.a.pending['chat']={'old':'confirmation'}
            await self.resume('Back to that',state,id='ambiguous')
            self.assertNotIn('planning_review',state);self.assertNotIn('chat',self.a.pending)
    async def test_existing_canonical_controls_keep_their_executor(self):
        cases=[('Forget who I am','identity'),('Pause automatic learning','assistant_settings'),('Show travel briefs','airport_brief'),("Find today's news about Norway",'internet_research')]
        with self.scope():
            state=self.a.agent.state('chat','phone')
            for text,tool in cases:
                with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'tool':'general_chat','members':[]})) as model:
                    with self.assertRaises(ValueError):await self.a.agent.plan(text,'chat','phone',state)
                self.assertEqual(model.call_args.args[3]['properties']['tool']['enum'],[tool])
    async def test_general_chat_cannot_claim_it_paused_a_setting(self):
        with self.scope():
            state=self.a.agent.state('chat','phone')
            with self.assertRaises(ValueError):await self.a.agent.execute(plan('general',answer='I have paused automatic learning.'),'Hello','chat','phone',state,AsyncMock())

    async def test_contextual_journey_question_keeps_route_capability(self):
        with self.scope():
            state=self.selected()
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'tool':'local_route','members':['mia']})) as model:
                result=await self.a.agent.plan("whats the travel time?",'chat','phone',state)
            self.assertEqual(result['tool'],'route');self.assertEqual(model.call_args.args[3]['properties']['tool']['enum'],['local_route'])

    async def test_explicit_united_update_switches_from_household_to_football(self):
        with self.scope():
            state=self.selected();state['last_tool']='profile'
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'tool':'football_updates','members':[]})) as model:
                result=await self.a.agent.plan('give me a united update','chat','phone',state)
            self.assertEqual(result['tool'],'football');self.assertEqual(model.call_args.args[3]['properties']['tool']['enum'],['football_updates'])

    async def test_validated_read_context_survives_a_legacy_pronoun_clarification(self):
        from jarvis.event_preparation import EventPreparation
        from test_planning_preparation_bundle import Client
        from test_companion_coordinator import NOW
        prep=EventPreparation(self.profile,Client(),('calendar.familiekalender',),self.provider,now=lambda:NOW)
        resolved={'subjects':('mia',),'start':'2026-10-29','end':'2026-10-30','speaker':None,'date':'2026-10-28','revision':self.profile._data['revision'],'expires':999,'question':'Is her instrument packed?','window':'all_day','shared_read_context':True}
        prep.sessions['chat']=dict(resolved)
        with self.scope(),patch.object(prep,'scope_valid',return_value=True),patch.object(prep,'request',side_effect=ValueError('Whose event should I check? Please name a household member.')),patch.object(prep.reader,'handle',new=AsyncMock(return_value={'status':'unavailable'})) as read:
            result=await prep.handle('Is her instrument packed?','chat',resolved=resolved)
        read.assert_awaited_once();self.assertEqual(result['status'],'unavailable');self.assertNotIn('Whose',result['message'])

    async def test_personal_preference_query_uses_memory_after_a_profile_topic(self):
        with self.scope():
            state=self.a.agent.state('chat','phone');state['last_tool']='profile';state['introduced']='benny'
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'tool':'recall_detail','members':['benny']})) as model:
                result=await self.a.agent.plan('What do I prefer when listening to music?','chat','phone',state)
            self.assertEqual((result['tool'],result['operation']),('memory','query'));self.assertEqual(model.call_args.args[3]['properties']['tool']['enum'],['recall_detail'])

    async def test_generic_preparation_return_uses_single_selected_source_title(self):
        with self.scope():
            state=self.selected();state['read_focus'].update(task='What should Mia prepare for Monday?',event_focus=[['Fellesøving Korps','family','2026-10-29T15:40:00+01:00','2026-10-29T16:00:00+01:00',['mia']]])
            state['returned_topic']={'tool':'appointments','subjects':['mia'],'question':state['read_focus']['task']}
            with patch('jarvis.companion_read_context.local_json',new=AsyncMock(return_value=frame(purpose='preparation',event_relation='continue'))):
                resolved=await self.a.agent.reads.resolve("back to mia's rehearsal, what should she bring?",'appointments',['mia'],state)
            self.assertEqual(resolved['source_focus'],state['read_focus']['event_focus']);self.assertTrue(resolved['event_continuation'])
            self.assertEqual(resolved['activity_question'],"mia's rehearsal, what should she bring?")
    async def test_return_does_not_relabel_a_rehearsal_as_swimming_or_robotics(self):
        with self.scope():
            for label in ('swimming','robotics'):
                state=self.selected();state['read_focus']['task']='What should Mia prepare for Monday?'
                state['returned_topic']={'tool':'appointments','subjects':['mia'],'question':state['read_focus']['task']}
                with patch('jarvis.companion_read_context.local_json',new=AsyncMock(return_value=frame(purpose='preparation',event_relation='continue'))):
                    resolved=await self.a.agent.reads.resolve("Back to Mia's "+label+", what should she bring?",'appointments',['mia'],state)
                self.assertFalse(resolved['source_focus']);self.assertFalse(resolved['event_continuation'])
    async def test_several_selected_events_do_not_prove_a_generic_rehearsal_reference(self):
        with self.scope():
            state=self.selected();state['read_focus']['task']='What should Mia prepare for Monday?';state['read_focus']['event_focus']*=2
            state['returned_topic']={'tool':'appointments','subjects':['mia'],'question':state['read_focus']['task']}
            with patch('jarvis.companion_read_context.local_json',new=AsyncMock(return_value=frame(purpose='preparation',event_relation='continue'))):
                resolved=await self.a.agent.reads.resolve("Back to Mia's rehearsal, what should she bring?",'appointments',['mia'],state)
            self.assertFalse(resolved['source_focus'])

    def midnight_clock(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        times=[datetime(2026,10,31,23,59,59,tzinfo=ZoneInfo('Europe/Oslo'))]
        self.a.now=lambda:times[0]
        self.profile._data['members'][2]['birth_date']={'status':'confirmed','value':'2017-08-21'}
        return times
    async def test_birthday_survives_midnight_during_interpretation(self):
        times=self.midnight_clock()
        async def decide(*args):times[0]+=timedelta(seconds=2);return plan('profile',members=['mia'])
        with self.scope(),patch.object(self.a.agent,'plan',new=decide):
            r=await self.a.process(AsyncMock()(),"When is Mia's birthday?",'chat','phone')
        self.assertEqual(r['status'],'success');self.assertIn('21 August',r['message'])
    async def test_birthday_read_retries_once_if_midnight_passes_during_execution(self):
        times=self.midnight_clock();execute=self.a.agent.execute
        async def advancing(*args):
            result=await execute(*args);times[0]+=timedelta(seconds=2);return result
        with self.scope(),patch.object(self.a.agent,'plan',new=AsyncMock(return_value=plan('profile',members=['mia']))),patch.object(self.a.agent,'execute',new=advancing),patch.object(self.a.agent,'profile_read',new=AsyncMock(wraps=self.a.agent.profile_read)) as read:
            r=await self.a.process(AsyncMock()(),"When is Mia's birthday?",'chat','phone')
        self.assertEqual(r['status'],'success');self.assertIn('21 August',r['message']);self.assertEqual(read.await_count,2)
    async def test_age_is_refreshed_when_midnight_is_the_birthday(self):
        times=self.midnight_clock();self.profile._data['members'][0]['birth_date']={'status':'confirmed','value':'1985-11-01'}
        execute=self.a.agent.execute;answers=[]
        async def advancing(*args):
            result=await execute(*args);answers.append(result['message']);times[0]+=timedelta(seconds=2);return result
        with self.scope(),patch.object(self.a.agent,'plan',new=AsyncMock(return_value=plan('profile',members=['benny']))),patch.object(self.a.agent,'execute',new=advancing):
            r=await self.a.process(AsyncMock()(),'How old is Benny?','chat','phone')
        self.assertIn('40 years old',answers[0]);self.assertIn('41 years old',r['message']);self.assertEqual(r['status'],'success')
    async def test_midnight_keeps_only_subject_and_introduced_name_not_planning_state(self):
        times=self.midnight_clock()
        with self.scope():
            state=self.selected();state['introduced']='benny';state['planning_review']={'session':'old','token':'old'};state['route_pending']={'awaiting':'mode'}
            times[0]+=timedelta(seconds=2);current=self.a.agent.state('chat','phone')
            self.assertIs(current,state);self.assertEqual(current['subject_reference']['subjects'],['mia']);self.assertEqual(current['introduced'],'benny')
            for field in ('read_focus','topic_references','planning_review','route_pending'):self.assertNotIn(field,current)
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'tool':'household_facts','members':['mia']})) as model:
                p=await self.a.agent.plan('And her birthday?','chat','phone',current)
            self.assertEqual(p['members'],['mia']);self.assertEqual(model.call_args.args[3]['properties']['members']['items']['enum'],['mia'])
    async def test_midnight_does_not_restore_expired_person_reference(self):
        times=self.midnight_clock()
        with self.scope():
            state=self.selected();self.clock[0]=700;times[0]+=timedelta(seconds=2)
            self.assertNotIn('subject_reference',self.a.agent.state('chat','phone'))
    async def test_date_sensitive_plans_are_not_silently_reanchored_or_run_twice(self):
        times=self.midnight_clock();execute=AsyncMock(return_value={'status':'success','message':'old calendar read'})
        async def advancing(*args):times[0]+=timedelta(seconds=2);return await execute(*args)
        with self.scope(),patch.object(self.a.agent,'plan',new=AsyncMock(return_value=plan('plans',members=['mia']))),patch.object(self.a.agent,'execute',new=advancing),patch.object(self.a.agent,'profile_read',new=AsyncMock()) as read:
            r=await self.a.process(AsyncMock()(),'What does Mia have tomorrow?','chat','phone')
        self.assertEqual(r['status'],'clarification_required');self.assertEqual(r['context_change_reason'],'date');self.assertNotIn('journey',r['message']);self.assertEqual(execute.await_count,1);read.assert_not_awaited()
    async def test_date_change_does_not_repeat_a_home_action(self):
        times=self.midnight_clock();execute=AsyncMock(return_value={'status':'success','message':'home tool finished'})
        async def advancing(*args):times[0]+=timedelta(seconds=2);return await execute(*args)
        with self.scope(),patch.object(self.a.agent,'plan',new=AsyncMock(return_value=plan('home'))),patch.object(self.a.agent,'execute',new=advancing):
            r=await self.a.process(AsyncMock()(),'Turn on the fictional light','chat','phone')
        self.assertEqual(execute.await_count,1);self.assertEqual(r['context_change_reason'],'date')
    async def test_profile_revision_change_at_midnight_still_blocks_profile_retry(self):
        times=self.midnight_clock()
        async def advancing(*args):
            times[0]+=timedelta(seconds=2);self.profile._data['revision']+=1;return {'status':'success','message':'old profile'}
        with self.scope(),patch.object(self.a.agent,'plan',new=AsyncMock(return_value=plan('profile',members=['mia']))),patch.object(self.a.agent,'execute',new=advancing),patch.object(self.a.agent,'profile_read',new=AsyncMock()) as read:
            r=await self.a.process(AsyncMock()(),"When is Mia's birthday?",'chat','phone')
        self.assertEqual(r['status'],'unavailable');self.assertEqual(r['context_change_reason'],'scope');read.assert_not_awaited()
    async def test_permissions_changed_at_midnight_still_block_profile_retry(self):
        times=self.midnight_clock()
        async def advancing(*args):
            times[0]+=timedelta(seconds=2);self.container.proactive_allowed_entities=('calendar.changed',);return {'status':'success','message':'old profile'}
        with self.scope(),patch.object(self.a.agent,'plan',new=AsyncMock(return_value=plan('profile',members=['mia']))),patch.object(self.a.agent,'execute',new=advancing),patch.object(self.a.agent,'profile_read',new=AsyncMock()) as read:
            r=await self.a.process(AsyncMock()(),"When is Mia's birthday?",'chat','phone')
        self.assertEqual(r['status'],'unavailable');self.assertEqual(r['context_change_reason'],'access');read.assert_not_awaited()

    async def test_prospective_remember_questions_preserve_person_and_read_intent(self):
        from jarvis.event_activity import preparation_question
        cases={'what should she remember?':'What should she prepare?', 'What should Mia remember to bring?':'What should Mia bring?', 'What does he need to remember':'What should he prepare?', 'Anything we should remember?':'What should we prepare?', 'Does she need to remember anything?':'What should she prepare?', 'What should I not forget?':'What should I prepare?'}
        for text,expected in cases.items():self.assertEqual(preparation_question(text,['Mia']),expected)
    async def test_prospective_read_does_not_rewrite_memory_commands_or_recall(self):
        from jarvis.event_activity import preparation_question
        for text in ('Remember Mia needs water','Can you remember that Mia needs water?','What did Benny tell you to remember?','What should Jarvis remember?','What should she remember? Save her details.','Forget that memory'):
            self.assertIsNone(preparation_question(text,['Mia','Benny']),text)
    async def test_scoped_remember_question_only_offers_preparation_read(self):
        with self.scope():
            state=self.selected();state['last_tool']='plans'
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'tool':'activity_preparation','members':['mia']})) as model:
                result=await self.a.agent.plan('what should she remember?','chat','phone',state)
            self.assertEqual(result['tool'],'appointments');self.assertEqual(model.call_args.args[3]['properties']['tool']['enum'],['activity_preparation'])
    async def test_preparation_read_normalises_remember_before_existing_write_guards(self):
        with self.scope():
            state=self.selected();self.container.event_preparation=SimpleNamespace(handle=AsyncMock(return_value={'status':'success','message':'Bring the instrument.'}))
            with patch.object(self.a.agent.reads,'resolve',new=AsyncMock(return_value=None)) as resolve,patch.object(self.a,'preference_intake',new=AsyncMock()) as memory:
                await self.a.agent.execute(plan('appointments',members=['mia']),'What should she remember?','chat','phone',state,AsyncMock())
            self.assertEqual(resolve.call_args.args[0],'What should she prepare?');self.assertEqual(self.container.event_preparation.handle.call_args.args[0],'What should she prepare?');memory.assert_not_awaited()
    async def test_generic_planning_words_do_not_become_an_activity_label(self):
        from jarvis.event_activity import requirement,requested
        self.assertFalse(requested(requirement('what should mia plan for on monday?',['Mia'])))
        self.assertIn('swimming',requirement('what should Mia plan for swimming on Monday?',['Mia'])['groups'])
    async def test_remember_question_without_active_plans_is_not_forced_to_an_event(self):
        with self.scope():
            state=self.a.agent.state('chat','phone')
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(side_effect=ValueError())) as model:
                with self.assertRaises(ValueError):await self.a.agent.plan('What should she remember?','chat','phone',state)
            self.assertGreater(len(model.call_args.args[3]['properties']['tool']['enum']),1)

    async def semantic_preparation(self,text,quote='',goal='kit',state=None,**kw):
        state=state or self.selected()
        decision=frame(**{**dict(purpose='preparation',event_relation='continue',activity_quote=quote,preparation_goal=goal),**kw})
        with patch('jarvis.companion_read_context.local_json',new=AsyncMock(return_value=decision)):
            return await self.a.agent.reads.resolve(text,'appointments',['mia'],state,force=True)

    async def test_semantic_kit_questions_do_not_become_activity_labels(self):
        with self.scope():
            for text in ('Anything she needs to take along?','Does she need her instrument?','What should she have with her?'):
                r=await self.semantic_preparation(text)
                self.assertEqual(r['activity_question'],'');self.assertEqual(r['source_focus'],self.selected()['read_focus']['event_focus'])
                self.assertEqual(r['preparation_goal'],'kit')

    async def test_semantic_venue_and_organiser_goals_keep_source_reference(self):
        with self.scope():
            for text,goal in (('Where will that be?','venue'),('What did the organiser say?','instructions')):
                r=await self.semantic_preparation(text,goal=goal)
                self.assertTrue(r['event_continuation']);self.assertEqual(r['preparation_goal'],goal)

    async def test_all_set_is_readiness_question_and_never_a_write(self):
        with self.scope():
            before=deepcopy(self.profile._data)
            r=await self.semantic_preparation('Are we all set for that?',goal='status')
            self.assertEqual(r['preparation_goal'],'status');self.assertEqual(before,self.profile._data)
            self.assertIsNone(await self.semantic_preparation('Are we all set and unlock the door?',goal='status'))

    async def test_activity_quote_must_be_verbatim_and_bounded(self):
        with self.scope():
            for quote in ('swimming','x'*101,[],None):
                with self.assertRaises(ValueError):await self.semantic_preparation('What should she take to rehearsal?',quote=quote)

    async def test_semantic_model_cannot_discard_an_explicit_activity_kind(self):
        with self.scope():
            for quote in ('','band rehearsal'):
                with self.assertRaises(ValueError):await self.semantic_preparation('What should she bring for swimming?',quote=quote)
            r=await self.semantic_preparation('What should she bring for swimming?',quote='swimming')
            self.assertEqual(r['activity_question'],'swimming');self.assertFalse(r['source_focus'])

    async def test_unknown_new_activity_is_retained_for_source_matching(self):
        with self.scope():
            r=await self.semantic_preparation('What should she bring for robotics?',quote='robotics',event_relation='new')
            self.assertEqual(r['activity_question'],'robotics');self.assertFalse(r['source_focus'])

    async def test_direct_preparation_can_use_semantic_read_without_legacy_keyword(self):
        with self.scope():
            state=self.a.agent.state('new','phone')
            r=await self.semantic_preparation('Anything Mia needs to take along on Monday?',state=state,date_quote='monday')
            self.assertEqual(r['subjects'],('mia',));self.assertTrue(r['start']);self.assertEqual(r['activity_question'],'')
            self.assertIn('prepare',r['task'])

    async def test_semantic_goal_is_kept_on_date_only_followup(self):
        with self.scope():
            state=self.selected(preparation_goal='venue')
            r=await self.semantic_preparation('And Friday?',state=state,goal='venue',date_quote='friday')
            self.assertEqual(r['preparation_goal'],'venue');self.assertFalse(r['source_focus'])
            with self.assertRaises(ValueError):await self.semantic_preparation('And Friday?',state=state,goal='kit',date_quote='friday')

    async def test_unknown_preparation_goal_is_rejected(self):
        with self.scope():
            with self.assertRaises(ValueError):await self.semantic_preparation('Where is it?',goal='send a message')

    async def test_thanks_preserves_expiry_and_current_read_without_restoring_reviews(self):
        with self.scope():
            state=self.selected();state['last_tool']='appointments';before=deepcopy(state['read_focus'])
            with patch.object(self.a.agent,'plan',new=AsyncMock(return_value=plan('general',operation='answer',answer='You are welcome.'))):
                result=await self.a.process(AsyncMock()(),'Thanks, Jarvis','chat','phone')
            self.assertEqual(result['status'],'success');self.assertEqual(state['read_focus'],before);self.assertEqual(state['last_tool'],'appointments')
            self.assertEqual(len(state['topic_references']),1)

    async def test_definition_and_thanks_are_not_forced_to_old_calendar(self):
        with self.scope():
            state=self.selected()
            for text in ('Thanks, Jarvis','What is rhythmic gymnastics?','What is band rehearsal?'):
                with patch('jarvis.companion_agent.local_json',new=AsyncMock(side_effect=[{'tool':'general_chat','members':[]},{'answer':'A short explanation.'}])) as model:
                    await self.a.agent.plan(text,'chat','phone',state)
                self.assertEqual(model.call_args_list[0].args[3]['properties']['tool']['enum'],['general_chat'])

    async def test_missing_tool_result_asks_relevant_detail(self):
        with self.scope():
            state=self.a.agent.state('new','phone')
            self.assertIn('Which day',self.a.agent.missing_detail('appointments',['mia'],state)['message'])
            self.assertIn('Mia',self.a.agent.missing_detail('plans',['mia'],state)['message'])
            self.assertIn('Whose plans',self.a.agent.missing_detail('plans',[],state)['message'])
            self.assertIn('Which appointment',self.a.agent.missing_detail('calendar',[],state)['message'])
            state=self.selected()
            self.assertIn('what to bring',self.a.agent.missing_detail('appointments',['mia'],state)['message'])

    async def test_shorter_reply_uses_only_expiring_presentation_reference(self):
        with self.scope():
            state=self.selected();before=deepcopy(state['read_focus'])
            state['response_reference']={'text':'Mia has band rehearsal at 17:30. The venue is not confirmed.','expires':300}
            original=state['response_reference']['text']
            answers=[{'answer':'Rehearsal: 17:30; venue not confirmed.'},{'faithful':True}]
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(side_effect=answers)) as model:
                result=await self.a.agent.present_answer('Can you make that shorter?',state)
            self.assertIn('not confirmed',result);self.assertEqual(state['read_focus'],before)
            self.assertEqual(model.call_args_list[0].args[2]['previous_answer'],original)
            self.assertLess(len(result.split()),len(original.split()));self.assertEqual(state['response_reference']['expires'],300)

    async def test_shorter_reply_rejects_new_time_or_number(self):
        with self.scope():
            state=self.selected();state['response_reference']={'text':'Band rehearsal starts at 17:30.','expires':300}
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'answer':'Band rehearsal starts at 18:30.'})):
                with self.assertRaises(ValueError):await self.a.agent.present_answer('Make that shorter',state)

    async def test_presentation_review_cannot_promote_usual_or_ready_claim(self):
        with self.scope():
            state=self.selected();original='The usual kit is an instrument; it has not been reported ready.'
            state['response_reference']={'text':original,'expires':300}
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(side_effect=[{'answer':'Her instrument is ready.'},{'faithful':False}]*2)):
                result=await self.a.agent.present_answer('Summarise that',state)
            self.assertIn('could not shorten',result);self.assertEqual(state['response_reference']['text'],original)

    async def test_expired_reply_is_not_rephrased_or_renewed(self):
        with self.scope():
            state=self.selected();state['response_reference']={'text':'An old answer','expires':1}
            with patch('jarvis.companion_agent.local_json',new=AsyncMock()) as model:
                self.assertIn('original question',await self.a.agent.present_answer('Make it shorter',state));model.assert_not_awaited()
            self.assertEqual(state['response_reference']['expires'],1)

    async def test_style_request_is_whole_question_not_arbitrary_command(self):
        from jarvis.companion_agent import presentation_request,acknowledgement
        for text in ('Can you make that shorter?','Summarise that','Explain it in plain English'):
            self.assertTrue(presentation_request(text))
        for text in ('Make that shorter and unlock the door','Summarise my calendar tomorrow','Thanks, Jarvis. Save this','yes'):
            self.assertFalse(presentation_request(text));self.assertFalse(acknowledgement(text))

    async def test_rephrase_preserves_task_and_does_not_renew_its_expiry(self):
        with self.scope():
            state=self.selected();state['last_tool']='appointments';before=deepcopy(state['read_focus'])
            state['response_reference']={'text':'Old answer','expires':300}
            decision={**plan('general',operation='answer',answer='Bring the instrument and sheet music.'),'presentation':True}
            with patch.object(self.a.agent,'plan',new=AsyncMock(return_value=decision)):
                r=await self.a.process(AsyncMock()(),'Make that shorter','chat','phone')
            self.assertEqual(r['status'],'success');self.assertEqual(state['read_focus'],before);self.assertEqual(state['last_tool'],'appointments')
            self.assertEqual(state['response_reference']['expires'],300)

    async def test_midnight_clears_presentation_reference(self):
        times=self.midnight_clock()
        with self.scope():
            state=self.selected();state['response_reference']={'text':'Yesterday answer','expires':300}
            times[0]+=timedelta(seconds=2)
            self.assertNotIn('response_reference',self.a.agent.state('chat','phone'))

    async def test_direct_dated_remember_question_preserves_quoted_activity_and_day(self):
        from jarvis.event_activity import preparation_question
        self.assertEqual(preparation_question('What should Mia remember for band rehearsal on Monday?',['Mia']), 'What should Mia prepare for band rehearsal on Monday?')
        self.assertIsNone(preparation_question('What should Mia remember for Monday and unlock the door?',['Mia']))
        self.assertIsNone(preparation_question('What should Mia remember about my job?',['Mia']))

    async def test_clear_goal_words_override_prior_venue_without_a_new_activity(self):
        with self.scope():
            state=self.selected(preparation_goal='venue')
            response=frame(purpose='preparation',event_relation='continue',activity_quote='',preparation_goal='kit',event_scope='focused')
            with patch('jarvis.companion_read_context.local_json',new=AsyncMock(return_value=response)) as model:
                r=await self.a.agent.reads.resolve('Anything she needs to take along?','appointments',['mia'],state,force=True)
            schema=model.call_args.args[3]
            self.assertEqual(schema['properties']['preparation_goal']['enum'],['kit']);self.assertEqual(r['preparation_goal'],'kit')

    async def test_organiser_question_changes_overview_to_preparation_executor(self):
        with self.scope():
            state=self.selected();self.container.household_thinking=SimpleNamespace(handle=AsyncMock())
            self.container.event_preparation=SimpleNamespace(handle=AsyncMock(return_value={'status':'success','message':'Bring the instrument.'}))
            resolved={'subjects':('mia',),'purpose':'preparation','start':'2026-10-29','end':'2026-10-30','preparation_goal':'instructions'}
            with patch.object(self.a.agent.reads,'resolve',new=AsyncMock(return_value=resolved)):
                r=await self.a.agent.execute(plan('plans',members=['mia']),'What did the organiser say?','chat','phone',state,AsyncMock())
            self.assertIn('instrument',r['message']);self.container.household_thinking.handle.assert_not_awaited()
            self.container.event_preparation.handle.assert_awaited_once();self.assertEqual(state['_executed_read_tool'],'appointments')

    async def test_singular_event_scope_is_typed_not_a_model_event_id(self):
        with self.scope():
            state=self.selected()
            for value in ('invented-event',True,[]):
                response=frame(purpose='preparation',activity_quote='',preparation_goal='venue',event_scope=value)
                with patch('jarvis.companion_read_context.local_json',new=AsyncMock(return_value=response)):
                    with self.assertRaises(ValueError):await self.a.agent.reads.resolve('Where is it?','appointments',['mia'],state,force=True)

    async def test_current_goal_narrowing_understands_both_organiser_spellings(self):
        from jarvis.companion_read_context import preparation_goals
        for text in ('What did the organiser say?','What did the organizer say?','Any event notes?'):
            self.assertEqual(preparation_goals(text),['instructions'])
        self.assertEqual(preparation_goals('Anything she needs to take along?'),['kit'])
        self.assertEqual(preparation_goals('What time does it finish?'),['timing'])
        self.assertEqual(preparation_goals('When does Mia finish school?'),[])

    async def test_topic_label_is_not_lost_when_model_omits_it_from_activity_quote(self):
        with self.scope():
            state=self.selected();state['returned_topic']={'tool':'appointments'}
            for quote in ('','band rehearsal'):
                r=await self.semantic_preparation("Back to Mia's rehearsal, what should she bring?",quote=quote,state=state)
                self.assertTrue(r['source_focus']);self.assertIn('rehearsal',r['activity_question'])

    async def test_different_return_label_cannot_inherit_selected_event(self):
        with self.scope():
            state=self.selected();state['returned_topic']={'tool':'appointments'}
            r=await self.semantic_preparation("Back to Mia's swimming, what should she bring?",quote='',state=state)
            self.assertFalse(r['source_focus']);self.assertIn('swimming',r['activity_question'])

    async def test_meal_margin_question_keeps_availability_and_duration(self):
        with self.scope():
            state=self.selected(purpose='availability',between=True,duration_minutes=45,task='Can we fit dinner between the appointments?')
            text='How much time is left after dinner and the drives?'
            response=frame(purpose='availability',between=True,activity_quote='',preparation_goal='none',event_scope='all')
            with patch('jarvis.companion_read_context.local_json',new=AsyncMock(return_value=response)) as model:
                r=await self.a.agent.reads.resolve(text,'plans',['mia'],state)
            self.assertEqual(r['purpose'],'availability');self.assertEqual(r['requested_duration'],45);self.assertTrue(r['between'])
            self.assertIn('dinner',r['task']);self.assertEqual(model.call_args.args[3]['properties']['purpose']['enum'],['availability'])
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'tool':'household_plans','members':['mia']})) as model:
                await self.a.agent.plan(text,'chat','phone',state)
            self.assertEqual(model.call_args.args[3]['properties']['tool']['enum'],['household_plans'])

    async def test_current_personal_fact_cannot_be_stolen_by_old_football_topic(self):
        with self.scope():
            state=self.selected();state['last_tool']='identity';state['introduced']='benny';state['football_topic']='news';state['football_focus_until']=500
            for text in ('What is my job?',"What is Benny's occupation?",'And her birthday?'):
                with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'tool':'household_facts','members':['mia'] if text=='And her birthday?' else ['benny']})) as model:
                    await self.a.agent.plan(text,'chat','phone',state)
                self.assertEqual(model.call_args.args[3]['properties']['tool']['enum'],['household_facts'])

    async def test_unknown_speaker_job_read_still_requires_a_name(self):
        with self.scope():
            state=self.a.agent.state('new','phone')
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'tool':'household_facts','members':[]})):
                decision=await self.a.agent.plan('What is my job?','new','phone',state)
            result=await self.a.agent.execute(decision,'What is my job?','new','phone',state,AsyncMock())
            self.assertEqual(result['status'],'clarification_required');self.assertIn('Whose',result['message'])

    async def test_job_interview_and_birthday_party_do_not_become_profile_facts(self):
        with self.scope():
            state=self.selected()
            for text in ("What is Mia's birthday party venue?",'What time is my job interview tomorrow?'):
                with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'tool':'household_plans','members':['mia']})) as model:
                    await self.a.agent.plan(text,'chat','phone',state)
                self.assertGreater(len(model.call_args.args[3]['properties']['tool']['enum']),1)

    async def test_date_only_time_question_keeps_finish_selector(self):
        with self.scope():
            state=self.selected(preparation_goal='timing',timing_kind='finish')
            r=await self.semantic_preparation('And Friday?',goal='timing',state=state,date_quote='friday')
            self.assertEqual(r['timing_kind'],'finish');self.assertFalse(r['source_focus'])

    async def test_generic_preparation_overrides_a_prior_clock_view(self):
        with self.scope():
            state=self.selected(preparation_goal='timing',timing_kind='start')
            response=frame(purpose='preparation',activity_quote='',preparation_goal='prepare',event_scope='focused')
            with patch('jarvis.companion_read_context.local_json',new=AsyncMock(return_value=response)) as model:
                r=await self.a.agent.reads.resolve('What should she prepare?','appointments',['mia'],state,force=True)
            self.assertEqual(model.call_args.args[3]['properties']['preparation_goal']['enum'],['prepare'])
            self.assertEqual(r['preparation_goal'],'prepare');self.assertIsNone(r['timing_kind'])

    async def test_generic_dated_plan_question_is_overview_not_a_clock_selection(self):
        with self.scope():
            state=self.a.agent.state('new','phone')
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'tool':'household_plans','members':['mia']})) as model:
                await self.a.agent.plan('What should Mia plan for on Monday?','new','phone',state)
            self.assertEqual(model.call_args.args[3]['properties']['tool']['enum'],['household_plans'])

    async def test_short_style_verb_tolerates_one_typo_without_rewriting_other_text(self):
        from jarvis.companion_agent import presentation_request
        for text in ('maje that shorter','mkae that shorter','maek it briefer','please mak that more concise','Can you maje that shorter?'):
            self.assertTrue(presentation_request(text),text)
        for text in ('save that shorter','move that shorter','maje that shorter and unlock the door','Mia should make that shorter'):
            self.assertFalse(presentation_request(text),text)

    async def test_typo_style_request_is_routed_to_presentation_not_calendar(self):
        with self.scope():
            state=self.selected()
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'tool':'general_chat','members':[]})) as model,patch.object(self.a.agent,'present_answer',new=AsyncMock(return_value='Bring the instrument and sheet music.')):
                result=await self.a.agent.plan('maje that shorter','chat','phone',state)
            self.assertTrue(result['presentation']);self.assertEqual(model.call_args.args[3]['properties']['tool']['enum'],['general_chat'])

    async def test_long_restatement_retries_with_a_measured_word_budget(self):
        with self.scope():
            state=self.selected();original='Mia should bring her instrument and sheet music for the band rehearsal tomorrow at 17:30.'
            state['response_reference']={'text':original,'expires':300}
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(side_effect=[{'answer':original},{'answer':'Bring her instrument and sheet music.'},{'faithful':True}])) as model:
                result=await self.a.agent.present_answer('maje that shorter',state)
            self.assertEqual(model.await_count,3);self.assertLess(len(result.split()),len(original.split()))
            self.assertIn('too long',model.call_args_list[1].args[2]['feedback']);self.assertEqual(state['response_reference']['expires'],300)

    async def test_restatement_never_silently_returns_a_longer_answer(self):
        with self.scope():
            state=self.selected();original='Bring the instrument and sheet music.'
            state['response_reference']={'text':original,'expires':300}
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(return_value={'answer':original+' There are several useful details to keep in mind.'})):
                result=await self.a.agent.present_answer('Make that shorter',state)
            self.assertIn('could not shorten',result);self.assertNotIn('several useful details',result)
            self.assertEqual(state['response_reference']['text'],original)

    async def test_further_shortening_uses_latest_reply_without_extending_expiry(self):
        with self.scope():
            state=self.selected();state['response_reference']={'text':'Mia should bring her instrument and sheet music for the band rehearsal tomorrow.','expires':300}
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(side_effect=[{'answer':'Bring her instrument and sheet music.'},{'faithful':True},{'answer':'Instrument and sheet music.'},{'faithful':True}])) as model:
                first=await self.a.agent.present_answer('Make that shorter',state)
                second=await self.a.agent.present_answer('Make that shorter',state)
            self.assertLess(len(second.split()),len(first.split()));self.assertEqual(model.call_args_list[2].args[2]['previous_answer'],first)
            self.assertEqual(state['response_reference']['expires'],300)

    async def test_shortening_names_required_kit_instead_of_generic_kit(self):
        with self.scope():
            state=self.selected();self.profile._data['activity_profiles']=[{'equipment':['instrument','sheet music']}]
            state['response_reference']={'text':'For the rehearsal tomorrow, Mia should bring her instrument and sheet music, which have not been reported packed.','expires':300}
            good='Bring instrument and sheet music; neither is reported packed.'
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(side_effect=[{'answer':'Bring the required kit.'},{'answer':good},{'faithful':True}])) as model:
                self.assertEqual(await self.a.agent.present_answer('Make that shorter',state),good)
            self.assertEqual(model.call_args_list[0].args[2]['required_kit'],['instrument','sheet music'])
    async def test_shortening_keeps_explicit_check_when_it_keeps_usual_venue(self):
        with self.scope():
            state=self.selected();self.profile._data['activity_profiles']=[{'usual_venue':'Elm School'}]
            state['response_reference']={'text':'Mia has band rehearsal tomorrow. Bring her instrument and sheet music. It usually takes place at Elm School; check it for this appointment.','expires':300}
            good='Bring instrument and sheet music; usually at Elm School, but confirm the venue.'
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(side_effect=[{'answer':'Bring instrument and sheet music; usually at Elm School.'},{'answer':good},{'faithful':True}])) as model:
                self.assertEqual(await self.a.agent.present_answer('Make that shorter',state),good)
            self.assertIn('explicit request',model.call_args_list[1].args[2]['feedback'])
    async def test_restatement_retry_distinguishes_kit_requirement_from_packed_report(self):
        with self.scope():
            state=self.selected();self.profile._data['activity_profiles']=[{'equipment':['instrument','sheet music']}];state['response_reference']={'text':'For the rehearsal tomorrow, Mia should bring her instrument and sheet music, which have not been reported packed.','expires':300}
            good='Bring instrument and sheet music; neither is reported packed.'
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(side_effect=[{'answer':'Her instrument and sheet music are ready.'},{'faithful':False},{'answer':good},{'faithful':True}])) as model:
                self.assertEqual(await self.a.agent.present_answer('Make that shorter',state),good)
            self.assertIn('NOT a claim',model.call_args_list[2].args[2]['feedback'])
    async def test_shorter_venue_qualification_is_checked_before_model_review(self):
        with self.scope():
            state=self.selected();self.profile._data['activity_profiles']=[{'usual_venue':'Elm School'}]
            original='Mia should bring her instrument and sheet music for band rehearsal tomorrow. It usually takes place at Elm School; check the venue for this appointment.'
            state['response_reference']={'text':original,'expires':300}
            bad='Bring instrument and sheet music to Elm School.'
            good='Bring instrument and sheet music; usually at Elm School, so confirm the venue.'
            with patch('jarvis.companion_agent.local_json',new=AsyncMock(side_effect=[{'answer':bad},{'answer':good},{'faithful':True}])) as model:
                result=await self.a.agent.present_answer('maje that shorter',state)
            self.assertEqual(result,good);self.assertEqual(model.await_count,3)
            self.assertIn('only USUAL',model.call_args_list[1].args[2]['feedback'])

    async def test_generic_overview_typo_does_not_become_a_prior_activity(self):
        with self.scope():
            state=self.selected(purpose='overview',task='what pla s does mia have on monday',event_focus=[])
            r=await self.semantic_preparation('What should she prepare?',goal='prepare',state=state,prior_activity_quote='')
            self.assertEqual(r['activity_reference'],{'groups':[],'literals':[]})
            self.assertFalse(r['source_focus']);self.assertEqual(r['subjects'],('mia',))

    async def test_explicit_unknown_prior_activity_is_kept_for_positive_source_check(self):
        with self.scope():
            state=self.selected(purpose='overview',task='What does Mia have for archery on Monday?',event_focus=[])
            r=await self.semantic_preparation('What should she bring?',state=state,prior_activity_quote='archery')
            self.assertEqual(r['activity_reference']['literals'],['archery'])

    async def test_prior_activity_quote_must_come_from_prior_user_task(self):
        with self.scope():
            state=self.selected(purpose='overview',task='what pla s does mia have on monday',event_focus=[])
            for quote in ('swimming',None,[], 'x'*101):
                with self.assertRaises(ValueError):await self.semantic_preparation('What should she bring?',state=state,prior_activity_quote=quote)

    async def test_new_unknown_activity_does_not_inherit_event_even_if_model_says_continue(self):
        with self.scope():
            state=self.selected()
            r=await self.semantic_preparation('What should she bring for robotics?',quote='robotics',state=state,prior_activity_quote='band rehearsal')
            self.assertFalse(r['source_focus']);self.assertEqual(r['activity_reference']['literals'],['robotics'])

    async def test_new_activity_overrides_a_different_prior_activity(self):
        with self.scope():
            state=self.selected(purpose='overview',task='What does Mia have for swimming on Monday?',event_focus=[])
            r=await self.semantic_preparation('What should she bring for robotics?',quote='robotics',state=state,prior_activity_quote='swimming')
            self.assertEqual(r['activity_reference'],{'groups':[],'literals':['robotics']})

    async def test_prior_reference_can_use_the_entire_single_selected_source_title(self):
        with self.scope():
            state=self.selected(task='what pla s does mia have on monday')
            r=await self.semantic_preparation('What should she bring?',state=state,prior_activity_quote='Band rehearsal')
            self.assertIn('band',r['activity_reference']['groups']);self.assertTrue(r['source_focus'])
            with self.assertRaises(ValueError):await self.semantic_preparation('What should she bring?',state=state,prior_activity_quote='Band')

    async def test_prior_reference_cannot_choose_one_of_multiple_source_titles(self):
        with self.scope():
            state=self.selected(task='what pla s does mia have on monday')
            state['read_focus']['event_focus'].append(['Robotics','family','2026-10-29T17:00:00+01:00','2026-10-29T18:00:00+01:00',['mia']])
            with self.assertRaises(ValueError):await self.semantic_preparation('Where is it?',goal='venue',state=state,prior_activity_quote='Band rehearsal')
