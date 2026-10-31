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
            state=self.selected();self.clock[0]=602
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
                result=await self.a.agent.plan('And her birthday?','chat','phone',state)
            self.assertEqual(result['tool'],'profile');self.assertEqual(model.await_count,1)

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
