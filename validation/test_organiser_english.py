"""Fictional bilingual source checks, rejection and no-mutation contracts."""
from copy import deepcopy
import json
import unittest
from jarvis.organiser_english import validate,translate,strict

SOURCE='Kom klar med turndrakt eller tettsittende klær, oppsatt hår og ta med drikkeflaske. Ein får ikkje gå i apparat før treninga startar.'
GOOD='Arrive in a leotard or close-fitting clothes with hair tied up, and bring a water bottle. Stay off the apparatus until training starts.'


class Guards(unittest.TestCase):
    def test_supported_translation(self):self.assertEqual(validate(GOOD,SOURCE),GOOD)
    def test_missing_distinct_requirements_rejected(self):
        for value in ('leotard','close-fitting','hair tied up','water bottle','apparatus'):
            with self.subTest(value=value),self.assertRaises(ValueError):validate(GOOD.replace(value,''),SOURCE)
    def test_negation_timing_and_alternative_cannot_disappear(self):
        for text in (GOOD.replace('off','on'),GOOD.replace('until','as'),GOOD.replace(' or ',' and ')):
            with self.assertRaises(ValueError):validate(text,SOURCE)
    def test_condition_must_remain(self):
        with self.assertRaises(ValueError):validate('Bring a water bottle.','Hvis det er ute, ta med drikkeflaske.')
        validate('If it is outdoors, bring a water bottle.','Hvis det er ute, ta med drikkeflaske.')
    def test_numbers_cannot_be_added_or_removed(self):
        for text,source in ((GOOD+' Arrive at 16:30.',SOURCE),(GOOD,SOURCE+' Klokka 17:00.')):
            with self.assertRaises(ValueError):validate(text,source)
    def test_exact_source_time_is_not_changed_to_a_deadline(self):
        source='Møt klokka 16:45. Ta med drikkeflaske.'
        with self.assertRaises(ValueError):validate('Arrive by 16:45 and bring a water bottle.',source)
        validate('Meet at 16:45 and bring a water bottle.',source)
    def test_unsafe_output_and_non_english_rejected(self):
        for suffix in (' See https://invalid.example.',' I booked transport.',' Ta med drikkeflaske.',' What next?','\n- Bring kit.'):
            with self.assertRaises(ValueError):validate(GOOD+suffix,SOURCE)
    def test_strict_ids_and_duplicate_keys(self):
        for raw in ('{"notes":{"F1":"a","F1":"b"}}','{"notes":{"F2":"a"}}','{"notes":{"F1":"a"},"other":1}'):
            with self.assertRaises(ValueError):strict(raw,'notes',{'F1'})


class Translation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.facts={'events':[{'id':'F1','protected_instructions':[SOURCE]}],
                    'verified_summary':'Tomorrow: '+SOURCE,'usual_notes':[]}
    async def run_translation(self,summary=GOOD,verdict=True,valid=lambda:True):
        calls=[]
        async def request(instructions,payload,schema,tokens):
            calls.append(json.loads(payload))
            return json.dumps({'notes':{'F1':summary}} if len(calls)==1 else {'checks':{'F1':verdict}})
        result=await translate(self.facts,request,valid)
        return result,calls
    async def test_two_separate_calls_and_source_retained_for_review_only(self):
        before=deepcopy(self.facts);(facts,calls),requests=await self.run_translation()
        self.assertEqual(calls,2);self.assertEqual(self.facts,before)
        self.assertEqual(facts['events'][0]['protected_instructions'],[GOOD])
        self.assertNotIn(SOURCE,facts['verified_summary']);self.assertIn(SOURCE,json.dumps(requests[1],ensure_ascii=False))
    async def test_reviewer_can_reject_fluent_but_invented_equipment(self):
        with self.assertRaises(ValueError):await self.run_translation(GOOD+' Bring a towel.',False)
    async def test_reviewer_booleans_are_strict(self):
        for value in ('true',1,None,False):
            with self.subTest(value=value),self.assertRaises(ValueError):await self.run_translation(verdict=value)
    async def test_one_correction_is_bounded_and_then_reviewed(self):
        calls=[]
        async def request(instructions,payload,schema,tokens):
            calls.append(payload)
            return json.dumps({'notes':{'F1':GOOD.replace('water bottle','drikkeflaske')}} if len(calls)==1 else
                {'notes':{'F1':GOOD}} if len(calls)==2 else {'checks':{'F1':True}})
        (facts,count)=await translate(self.facts,request,lambda:True)
        self.assertEqual(count,3);self.assertIn('correction',calls[1]);self.assertEqual(facts['events'][0]['protected_instructions'],[GOOD])
    async def test_context_race_discards_draft(self):
        with self.assertRaises(ValueError):await self.run_translation(valid=lambda:False)
    async def test_english_sources_need_no_translation_calls(self):
        self.facts['events'][0]['protected_instructions']=['Do not enter before 17:00.']
        (_,calls),requests=await self.run_translation();self.assertEqual(calls,0);self.assertEqual(requests,[])
    async def test_only_selected_non_english_event_translated(self):
        self.facts['events'].append({'id':'F2','protected_instructions':['Bring a folder.']})
        (facts,_),requests=await self.run_translation()
        self.assertEqual(set(requests[0]['sources']),{'F1'});self.assertEqual(facts['events'][1],self.facts['events'][1])
