"""Fictional household gap continuity and multi-person calendar constraints."""
from copy import deepcopy
from datetime import datetime
import unittest
from types import SimpleNamespace
from jarvis.calendar_insights import insights,grounded_reply
from jarvis.household_thinking import HouseholdThinking
from jarvis.household_planner import HouseholdPlanner,CALENDAR,ZONE
from jarvis.household_briefing import HouseholdBriefing,Brief
from jarvis.calendar_evidence import calendar_evidence
from jarvis.calendar_membership import description
from test_planning_preparation_bundle import profile,scope
from test_calendar_insights import event,evidence
from test_household_planner import Client

class GapTests(unittest.TestCase):
    def facts(self):
        out=evidence(event(owner='mia',title='Band rehearsal',start='2026-10-29T15:40:00+01:00',end='2026-10-29T16:30:00+01:00'),
            event('F2',owner='mia',title='Gymnastics',start='2026-10-29T17:00:00+01:00',end='2026-10-29T18:30:00+01:00'))
        out['between_requested']=True;return out
    def test_missing_duration_asks_how_long_not_for_another_time_window(self):
        board=insights(self.facts(),'Can we fit dinner between those?',None)
        self.assertEqual(board['between_appointment_gaps'][0]['calendar_gap_minutes'],30)
        self.assertEqual(board['required_question'],'How long would you like it to take?')
        self.assertFalse(board['window_clarification_needed'])
    def test_shorter_activity_is_only_a_calendar_possibility(self):
        board=insights(self.facts(),'20 minutes',None,'availability')
        self.assertTrue(board['requested_minutes_fit_recorded_gap']);self.assertEqual(len(board['candidate_calendar_gaps']),1)
        self.assertIn('not confirmed',board['candidate_calendar_gaps'][0]['basis'])
    def test_longer_activity_cannot_be_claimed_to_fit(self):
        board=insights(self.facts(),'45 minutes',None,'availability')
        self.assertFalse(board['requested_minutes_fit_recorded_gap']);self.assertFalse(board['candidate_calendar_gaps'])
        self.assertIn('does not fit',grounded_reply(board,None))
        with self.assertRaises(ValueError):HouseholdThinking.validate_goal('A 45-minute dinner could fit in that recorded gap.',board)
        with self.assertRaises(ValueError):HouseholdThinking.validate_goal('Can we fit the 45-minute dinner in that gap?',board)
    def test_duration_followup_must_answer_the_duration(self):
        board=insights(self.facts(),'20 minutes',None,'availability')
        with self.assertRaises(ValueError):HouseholdThinking.validate_goal('There is a recorded gap before Gymnastics. It could work for dinner.',board)
        HouseholdThinking.validate_goal('A 20-minute activity could fit in the recorded gap before Gymnastics, if other commitments allow.',board)
    def test_ambiguous_pair_is_not_silently_selected(self):
        data=self.facts();data['facts'].append(event('F3',owner='mia',title='Third event',start='2026-10-29T19:30:00+01:00',end='2026-10-29T20:00:00+01:00'))
        board=insights(data,'Can we fit dinner between those?',None)
        self.assertEqual(board['required_question'],'Which two appointments do you mean?');self.assertFalse(board['duration_clarification_needed'])
    def test_all_day_event_does_not_become_available_clock_time(self):
        data=self.facts();data['facts'].append({**event('F3',owner='mia'), 'start':'2026-10-29T00:00:00+01:00','end':'2026-10-30T00:00:00+01:00','all_day':True})
        self.assertFalse(insights(data,'Can we fit dinner between those?',None)['candidate_calendar_gaps'])
    def test_shared_appointment_counts_for_each_named_participant(self):
        shared={**event(),'owners':['linda','mia']}
        loads=insights(evidence(shared),'How busy is the household?',None)['calendar_load']
        self.assertEqual({r['owner'] for r in loads},{'Linda','Mia'});self.assertTrue(all(r['scheduled_minutes_without_double_counting']==60 for r in loads))
    def test_between_followup_keeps_the_same_person_and_day(self):
        p=profile();route=HouseholdThinking(p,None,[],None,now=lambda:datetime(2026,10,27,12,tzinfo=ZONE))
        with scope(p,None,'s'):
            first=route.request('What does Mia\'s day look like on Thursday?','s');route.sessions['s']=first
            follow=route.request('Can we fit dinner between those?','s');route.sessions['s']=follow
            duration=route.request('45 minutes','s')
        self.assertEqual(follow['subjects'],('mia',));self.assertEqual(follow['start'],'2026-10-29')
        self.assertEqual(duration['start'],follow['start']);self.assertTrue(duration['between'])

class OwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_mia_and_explicit_linda_events_reach_the_right_evidence(self):
        p=profile();client=Client();planner=HouseholdPlanner(p,client,[CALENDAR]);self.addCleanup(planner.db.close)
        old={'summary':'Old club','start':'2026-10-29T15:40:00+01:00','end':'2026-10-29T16:30:00+01:00'}
        planner.bootstrap([old]);client.events=[old,{**old,'summary':'Linda club','description':description(['linda'],'sport','fictional-id','')}]
        async def routines(*a,**kw):raise RuntimeError('Fictional routines unavailable')
        client.get_household_today=routines
        route=HouseholdBriefing(p,client,[CALENDAR],now=lambda:datetime(2026,10,27,12,tzinfo=ZONE))
        for person,title in (('mia','Old club'),('linda','Linda club')):
            out=await route.handle('planner',None,resolved=Brief(person,'2026-10-29','2026-10-30'),structured_only=True)
            appointments=[f for f in out['evidence']['facts'] if f['kind']=='appointment']
            self.assertEqual([f['text'] for f in appointments],[title]);self.assertEqual(appointments[0]['owners'],[person])
