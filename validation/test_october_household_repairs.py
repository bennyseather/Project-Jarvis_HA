"""Synthetic date-boundary regressions; no real household profile required."""
from datetime import date
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from jarvis.household_speaker import age_fields, birthday_answer
from jarvis.household_profile import HouseholdProfile


def profile():
    return HouseholdProfile({'schema_version':1,'revision':1,'roster_complete':False,
        'assistant':{'name':'Jarvis'},'members':[{'id':'fixture','preferred_name':'Casey',
        'birth_date':{'value':'2000-10-21','status':'confirmed'}}],
        'sharing_policy':{'directory_enabled':True,'source':'Synthetic fixture',
        'recorded_on':'2026-10-21','relationships':[],
        'knowledge_access':{'mode':'shared_household','source':'Synthetic fixture','recorded_on':'2026-10-21'}}})


class AgeTests(unittest.TestCase):
    def test_before_on_after_birthday_and_next_year(self):
        record={'value':'2000-10-21','status':'confirmed'}
        for day,expected in ((date(2026,10,20),25),(date(2026,10,21),26),
                             (date(2026,10,22),26),(date(2027,10,20),26),(date(2027,10,21),27)):
            self.assertEqual(age_fields(record,today=day),{'age_years':expected,'age_as_of':day.isoformat()})

    def test_unconfirmed_invalid_and_future_dates_not_invented(self):
        for record in ({},{'value':'2000-01-01','status':'unconfirmed'},
                       {'value':'bad','status':'confirmed'},{'value':'2030-01-01','status':'confirmed'}):
            self.assertEqual(age_fields(record,today=date(2026,10,21)),{})

    def test_same_profile_context_recalculates_without_mutating_birth_record(self):
        p=profile()
        for day,expected in ((date(2026,10,20),25),(date(2026,10,21),26)):
            with patch('jarvis.household_speaker.age_fields',side_effect=lambda record:age_fields(record,today=day)):
                details=p.context()['approved_personal_details']['Casey']
            self.assertEqual(details['age_years'],expected)
            self.assertEqual(details['age_as_of'],day.isoformat())
        self.assertEqual(p._data['revision'],1)
        self.assertEqual(p._data['members'][0]['birth_date'],{'value':'2000-10-21','status':'confirmed'})

    def test_age_question_variants_and_birthday_are_not_model_arithmetic(self):
        for question in ('How old is Casey?',"What is Casey's age?","What's Casey's age?"):
            result=birthday_answer(question,profile()._data,today=date(2026,10,21))
            self.assertEqual(result['message'],'Casey is 26 years old.')
            self.assertFalse(result['cacheable'])
        self.assertEqual(birthday_answer("When is Casey's birthday?",profile()._data)['message'],"Casey's birthday is on 21 October.")
        self.assertIsNone(birthday_answer("How old is Casey's school?",profile()._data))


class DashboardPlanTests(unittest.TestCase):
    def test_only_confirmed_mower_door_and_calendar_settings_change(self):
        spec=importlib.util.spec_from_file_location('october_plan',Path('deployment/diagnostics/october_dashboard_repairs.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        cards=[{'type':'custom:jarvis-mower-card','entity':module.MOWER,'name':'Fixture'} for _ in range(2)]
        cards += [{'type':'custom:jarvis-entity-badge','entity':entity} for entity in sorted(module.DOORS)]
        cards += [{'type':'custom:jarvis-calendar-card','entities':['calendar.fixture'],'appointment_limit':1},
                  {'type':'tile','entity':'light.fixture','name':'Leave alone'}]
        original={'views':[{'cards':cards}]};before=deepcopy(original)
        result,counts=module.plan(original)
        self.assertEqual(original,before)
        self.assertEqual(counts,{'mower':2,'door_badges':4,'calendar':1})
        self.assertEqual(result['views'][0]['cards'][-1],cards[-1])
        self.assertTrue(all(c['out_of_season'] for c in result['views'][0]['cards'][:2]))
        self.assertTrue(all(c['display_class']=='door' for c in result['views'][0]['cards'][2:6]))
        self.assertEqual(result['views'][0]['cards'][6]['view'],'day')
        self.assertEqual(module.plan(result)[0],result)
        original['views'][0]['cards'].pop(0)
        with self.assertRaises(ValueError):module.plan(original)


if __name__=='__main__':unittest.main()
