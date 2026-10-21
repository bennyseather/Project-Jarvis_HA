"""Local transport defaults stay unchanged; calendar can request strict JSON."""
import logging
import unittest
from jarvis.providers.local_first_provider import LocalFirstReasoningProvider,LocalReasoningPolicy
from jarvis.household_thinking import ANSWER_SCHEMA,clock_values,HouseholdThinking
from test_calendar_insights import evidence,event


class Captured(LocalFirstReasoningProvider):
    def __init__(self):
        super().__init__(LocalReasoningPolicy(),logging.getLogger('fixture'),fallback=None)
        self.requests=[]
    def _post(self,path,payload,**kwargs):
        self.requests.append(payload)
        return {'message':{'content':'{"answer":"Fixture"}'},'done_reason':'stop'}


class LocalContractTests(unittest.TestCase):
    def test_strict_schema_and_zero_sampling_are_per_request(self):
        p=Captured()
        out=p.reason_local(instructions='Fixture',input_messages=[{'role':'user','content':'Fixture'}],timeout_seconds=3,response_schema=ANSWER_SCHEMA,temperature=0)
        self.assertEqual(out['status'],'success')
        self.assertEqual(p.requests[-1]['format'],ANSWER_SCHEMA)
        self.assertEqual(p.requests[-1]['options']['temperature'],0)
        self.assertFalse(p.requests[-1]['stream'])
        p.reason_local(instructions='Ordinary',input_messages=[{'role':'user','content':'Fixture'}],timeout_seconds=3)
        self.assertNotIn('format',p.requests[-1]);self.assertEqual(p.requests[-1]['options']['temperature'],0.2)

    def test_invalid_contract_never_calls_network(self):
        for schema,temp in [('bad',0),({'description':'x'*5000},0),(ANSWER_SCHEMA,9)]:
            p=Captured();out=p.reason_local(instructions='Fixture',input_messages=[],timeout_seconds=3,response_schema=schema,temperature=temp)
            self.assertEqual(out['status'],'unavailable');self.assertEqual(p.requests,[])

    def test_clock_formats_are_semantic_not_string_equality(self):
        values,_=clock_values('9 AM, 2:30 PM, 4:00–5:00 pm, 11 to 1pm and 12AM')
        self.assertEqual(values,['09:00','14:30','16:00','17:00','13:00','00:00'])

    def test_supported_twelve_hour_answer_and_unsupported_clock(self):
        e=evidence(event())
        self.assertIn('9 AM',HouseholdThinking.validate_compact('{"answer":"Benny has a meeting at 9 AM."}',e,'benny'))
        for text in ('Benny has a meeting at 2 AM.','Benny has a meeting at 9:30 AM.'):
            with self.assertRaises(ValueError):HouseholdThinking.validate_compact('{"answer":"'+text+'"}',e,'benny')

    def test_school_check_is_not_an_attendance_assertion(self):
        e=evidence({'id':'F1','kind':'routine','owners':['mia'],'text':'Usual school 08:15–12:50'})
        self.assertIn('confirm',HouseholdThinking.validate_compact('{"answer":"Consider confirming the school schedule and any necessary materials beforehand."}',e,'benny'))
        with self.assertRaises(ValueError):HouseholdThinking.validate_compact('{"answer":"Mia is definitely attending school."}',e,'benny')


if __name__=='__main__':unittest.main()
