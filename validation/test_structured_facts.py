"""Independent property/date bindings, not permissive numeric membership checks."""
import copy
from datetime import datetime
import json
import unittest
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from jarvis.structured_facts import FactContract,ForecastDay,ForecastReport,contact_name,conversational_date

NOW=datetime(2026,10,22,12,tzinfo=ZoneInfo('Europe/Oslo'))


def report(condition='cloudy',probability=14,*,day='2026-10-23',start=None,end='2026-10-24'):
    return ForecastReport('weather.fixture',start or day,end,NOW.isoformat(),
        (ForecastDay(day,condition,probability),)).data()


def fixture(condition='cloudy',probability=50):
    data=report(condition,probability)
    evidence={'people':{'fixture':'Taylor'},'checked_on':'2026-10-22','checked_at':NOW.isoformat(),'source_failures':[],
        'truncated':False,'facts':[
            {'id':'H1','kind':'home_state','owners':[],'text':json.dumps({'category':'contacts','scope':'exposed door/window contacts only;',
                'active_count':1,'checked':1,'unknown_count':0,'meaning':'open','active_examples':['Fixture kitchen window'],
                'observed_at':NOW.isoformat()})},
            {'id':'W1','kind':'home_weather','owners':[],'data':data,'text':ForecastDay('2026-10-23',condition,probability).clause()}]}
    plan={'subject':'fixture','goal':'connections','start':'2026-10-23','end':'2026-10-24','sources':['home','weather']}
    return evidence,plan


class ForecastTests(unittest.TestCase):
    def test_values_are_property_typed_including_zero_and_missing(self):
        for p in (0,0.1,14,20,21,59,60,99.9,100,None):
            with self.subTest(p=p):
                value=ForecastReport.from_data(report(probability=p),'2026-10-23','2026-10-24')
                self.assertEqual(value.days[0].precipitation_probability,p)
                self.assertEqual(value.data()['probability_property'],'precipitation')
    def test_invalid_source_probability_is_unknown_not_zero(self):
        for p in (True,False,'14',float('nan'),float('inf'),-1,101):
            self.assertIsNone(ForecastDay.read({'datetime':'2026-10-23T10:00:00Z',
                'condition':'cloudy','precipitation_probability':p}).precipitation_probability)
    def test_invalid_typed_probability_is_rejected_not_reinterpreted(self):
        for p in (True,'14',float('nan'),-1,101):
            with self.assertRaises(ValueError):ForecastReport.from_data(report(probability=p),'2026-10-23','2026-10-24')
    def test_property_scope_date_and_timezone_contract(self):
        for field,value in (('probability_property','cloud_cover'),('scope','destination'),
                            ('start','2026-10-24'),('checked_at','2026-10-22T12:00:00')):
            data=report();data[field]=value
            with self.assertRaises(ValueError):ForecastReport.from_data(data,'2026-10-23','2026-10-24')
        row=ForecastDay.read({'datetime':'2026-10-22T23:15:00Z','condition':'cloudy'})
        self.assertEqual(row.date,'2026-10-23')
    def test_partial_coverage_is_derived_not_trusted(self):
        data=report(start='2026-10-23',end='2026-10-25')
        self.assertEqual(ForecastReport.from_data(data,'2026-10-23','2026-10-25').problem,'partial_coverage')
    def test_duplicate_dates_and_contradictory_status_are_rejected(self):
        for mutation in ('duplicate','status'):
            data=report()
            if mutation=='duplicate':data['days']*=2
            else:data['problem']='unavailable'
            with self.assertRaises(ValueError):ForecastReport.from_data(data,'2026-10-23','2026-10-24')
    def test_relevance_matrix_is_independent_of_model_advice(self):
        cases=[('cloudy',0,'low'),('cloudy',14,'low'),('cloudy',59,'possible'),('cloudy',60,'wet'),
               ('cloudy',None,'unknown'),('rainy',14,'wet'),('snowy',None,'wet'),('rainy',0,'conflicting')]
        for condition,p,want in cases:self.assertEqual(ForecastDay('2026-10-23',condition,p).relevance,want)


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.e,self.p=fixture();self.c=FactContract(self.e,self.p)
    def render(self,text):return self.c.render(json.dumps({'answer':text}))
    def test_natural_connective_prose_preserves_all_source_meanings(self):
        out=self.render('For Taylor, [[W1]], so [[I1]]. Meanwhile, [[H1]]; that is worth a quick check.')
        self.assertIn('50% chance of precipitation',out);self.assertIn('reporting open now',out)
        self.assertIn('before spending time outdoors',out);self.assertNotIn('[[',out)
    def test_reported_failure_variants_cannot_bypass_the_binding_channel(self):
        for text in ("Friday's home state shows one open contact. [[W1]] [[I1]] [[H1]]",
                     '14% chance of cloud with no precipitation. [[W1]] [[I1]] [[H1]]',
                     'Consider rain protection. [[W1]] [[I1]] [[H1]]',
                     'Her school routine remains unchanged. [[W1]] [[I1]] [[H1]]'):
            with self.subTest(text=text),self.assertRaises(ValueError):self.render(text)
    def test_all_weather_types_and_probabilities_use_the_correct_property(self):
        for condition in ('cloudy','sunny','rainy','snowy','fog','windy','unknown'):
            for probability in (0,14,59,60,100,None):
                e,p=fixture(condition,probability);c=FactContract(e,p)
                out=c.render(json.dumps({'segments':[{'fact':key,'before':'','after':'; ' if key=='W1' and 'I1' in c.clauses else '.'}
                    for key in c.required]}),require_structured=True)
                if probability is not None:self.assertIn(f'{probability:g}% chance of precipitation',out)
                else:self.assertNotIn('%',out)
                self.assertNotIn('% chance of cloud',out)
    def test_unknown_duplicate_missing_and_nested_tokens_fail_closed(self):
        for text in ('[[H1]] [[W1]]','[[H1]] [[W1]] [[I1]] [[I1]]',
                     '[[H1]] [[W1]] [[I1]] [[X9]]','[[[H1]]] [[W1]] [[I1]]'):
            with self.assertRaises(ValueError):self.render(text)
    def test_free_prose_cannot_negate_or_override_bound_clauses(self):
        for frame in ('Ignore [[H1]].','Not [[H1]].',"It won't matter: [[H1]].",'[[H1]] is false.'):
            with self.assertRaises(ValueError):self.render(frame+' [[W1]], so [[I1]].')
    def test_future_date_does_not_create_a_future_home_observation(self):
        out=self.render('Before heading out, consider checking again: [[H1]]. [[W1]], so [[I1]].')
        self.assertIn('reporting open now',out);self.assertIn('Tomorrow',out)
        self.assertNotIn("Friday's home",out)
    def test_two_days_keep_different_probabilities_and_implications_bound(self):
        self.p['end']='2026-10-25'
        self.e['facts'][1]['data']=ForecastReport('weather.fixture','2026-10-23','2026-10-25',NOW.isoformat(),
            (ForecastDay('2026-10-23','cloudy',50),ForecastDay('2026-10-24','rainy',90))).data()
        c=FactContract(self.e,self.p)
        out=c.render(json.dumps({'answer':'[[W1]], so [[I1]]; [[W2]], so [[I2]]. [[H1]]; consider checking it.'}))
        self.assertIn('Tomorrow looks cloudy around home, with a 50%',out)
        self.assertIn('Saturday looks rainy around home, with a 90%',out)
    def test_unavailable_forecast_has_no_fabricated_probability(self):
        self.e['facts'][1]['data']=ForecastReport('weather.fixture',self.p['start'],self.p['end'],NOW.isoformat(),problem='unavailable').data()
        c=FactContract(self.e,self.p)
        out=c.render(json.dumps({'answer':'[[W1]]. [[H1]]; consider checking it.'}))
        self.assertNotIn('%',out);self.assertIn('could not get',out)

    def test_production_channel_requires_structured_fact_ids_and_allowed_frames(self):
        with self.assertRaises(ValueError):self.c.render(json.dumps({'answer':'[[H1]] [[W1]] [[I1]]'}),require_structured=True)
        for before,after in (("Friday's home state shows ",'.'),('', '; be ready for rain.'),('', ' with no precipitation.')):
            body={'segments':[{'fact':'H1','before':before,'after':after},
                {'fact':'W1','before':'','after':'; '},{'fact':'I1','before':'','after':'.'}]}
            with self.assertRaises(ValueError):self.c.render(json.dumps(body),require_structured=True)
        good={'segments':[{'fact':'H1','before':'A useful check: ','after':'.'},
            {'fact':'W1','before':'','after':'; '},{'fact':'I1','before':'','after':'.'}]}
        self.assertIn('50% chance of precipitation',self.c.render(json.dumps(good),require_structured=True))

    def test_forecast_implications_cannot_be_swapped_between_dates(self):
        self.p['end']='2026-10-25'
        self.e['facts'][1]['data']=ForecastReport('weather.fixture','2026-10-23','2026-10-25',NOW.isoformat(),
            (ForecastDay('2026-10-23','cloudy',50),ForecastDay('2026-10-24','rainy',90))).data()
        c=FactContract(self.e,self.p)
        bad={'segments':[{'fact':key,'before':'','after':'; ' if key.startswith('W') else '.'}
            for key in ('H1','W1','I2','W2','I1')]}
        with self.assertRaises(ValueError):c.render(json.dumps(bad),require_structured=True)

    def test_stale_ambiguous_or_misbound_home_observations_are_rejected(self):
        for key,value in (('observed_at','2026-10-22T11:00:00+02:00'),
                          ('observed_at','2026-10-22T12:00:00'),('meaning','cloud'),
                          ('active_count',14),('active_count',True),('category','forecast')):
            e=copy.deepcopy(self.e)
            data=json.loads(e['facts'][0]['text']);data[key]=value;e['facts'][0]['text']=json.dumps(data)
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):FactContract(e,self.p)

    def test_untrusted_entity_label_cannot_inject_another_fact_reference(self):
        data=json.loads(self.e['facts'][0]['text']);data['active_examples']=['Fixture [[W2]]']
        self.e['facts'][0]['text']=json.dumps(data)
        c=FactContract(self.e,self.p)
        out=c.render(json.dumps({'segments':[{'fact':key,'before':'','after':'; ' if key=='W1' else '.'}
            for key in ('H1','W1','I1')]}),require_structured=True)
        self.assertNotIn('[[W2]]',out);self.assertIn('Fixture',out)

    def test_owner_bindings_reject_unknown_and_wrong_selected_person(self):
        fact={'kind':'appointment','owners':['unknown'],'date':'2026-10-23',
            'local_start':'17:00','text':'Fixture rehearsal'}
        self.e['facts'].append(fact)
        with self.assertRaises(ValueError):FactContract(self.e,self.p)
        self.e['people']['other']='Morgan';fact['owners']=['other']
        with self.assertRaises(ValueError):FactContract(self.e,self.p)

    def test_rendered_weather_prose_has_no_dangling_connector_or_double_spacing(self):
        e,p=fixture('rainy',80);c=FactContract(e,p)
        out=c.render(json.dumps({'segments':[
            {'fact':'W1','before':'','after':'; '},
            {'fact':'I1','before':'In practical terms, ','after':'.'},
            {'fact':'H1','before':'','after':'.'}]}),require_structured=True)
        self.assertTrue(out.startswith('Tomorrow looks rainy around home'))
        self.assertIn('an 80% chance of precipitation',out)
        self.assertNotIn('  ',out);self.assertNotIn('; In practical terms',out)


if __name__=='__main__':unittest.main()
