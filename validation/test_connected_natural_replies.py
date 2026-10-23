"""Purpose-first prose without losing source/property/date and permission guards."""
import copy
from datetime import datetime
import json
import unittest
from jarvis.structured_facts import FactContract,ForecastDay,ForecastReport,contact_name,conversational_date
from test_structured_facts import fixture

STAMP='2026-10-23T12:00:00+02:00'

def pilot(probability=0.4, *, person=True, appointments=1, condition='partlycloudy'):
    e,p=fixture();e['people']={'fixture':'Taylor'}
    e['checked_on']='2026-10-23';e['checked_at']=STAMP
    p.update(start='2026-10-24',end='2026-10-25',subject='fixture' if person else 'all',
        goal='connections' if person else 'predeparture',sources=['calendar','weather'] if person else ['home','calendar','weather'])
    home=json.loads(e['facts'][0]['text']);home.update(observed_at=STAMP,
        active_examples=['Magnet Sensor Master Bedroom'],
        active_details=[{'name':'Magnet Sensor Master Bedroom','device_class':'opening'}])
    e['facts'][0]['data']=home
    e['facts'][1]['data']=ForecastReport('weather.fixture',p['start'],p['end'],STAMP,
        (ForecastDay(p['start'],condition,probability),)).data()
    if person:e['facts'].pop(0)
    e['facts'].append({'kind':'coverage','owners':['fixture'],'text':'Connected entries only.',
        'returned_entries':appointments})
    for i in range(appointments):
        e['facts'].append({'kind':'appointment','owners':['fixture'],'text':'Fiktiv musikkonkurranse' if i==0 else 'Fixture event '+str(i),
            'date':p['start'],'local_start':str(10+i).zfill(2)+':00','all_day':False})
    return e,p

def compose(contract,keys=None):
    keys=keys or list(dict.fromkeys(contract.lead+contract.required))
    return contract.render(json.dumps({'segments':[{'fact':key,'before':'',
        'after':'; ' if key.startswith('W') and 'I'+key[1:] in contract.clauses else '.'}
        for key in keys]}),require_structured=True)

class NaturalReplyTests(unittest.TestCase):
    def test_dates_use_norway_evidence_anchor_across_dst_and_year_end(self):
        for value,reference,want in [('2026-10-23','2026-10-23','today'),
            ('2026-10-24','2026-10-23','tomorrow'),('2026-10-25','2026-10-23','Sunday'),
            ('2027-01-01','2026-12-31','tomorrow'),('2026-11-01','2026-10-23','Sunday 01 November')]:
            self.assertEqual(conversational_date(value,reference),want)
    def test_verified_contact_types_control_friendly_names(self):
        for kind,want in [('opening','master bedroom contact'),('window','master bedroom window'),
                          ('door','master bedroom door'),(None,'Magnet Sensor Master Bedroom')]:
            self.assertEqual(contact_name('Magnet Sensor Master Bedroom',kind),want)
    def test_custom_names_are_not_reinvented(self):
        self.assertEqual(contact_name('Fixture kitchen window','opening'),'Fixture kitchen window')
        self.assertEqual(contact_name('Sensor','opening'),'Sensor')
        self.assertEqual(contact_name('Door Sensor Master Bedroom','window'),'Door Sensor Master Bedroom')
        self.assertEqual(contact_name('Window Sensor Master Bedroom','door'),'Window Sensor Master Bedroom')
    def test_departure_leads_with_reported_actionable_contact_not_raw_sensor_name(self):
        e,p=pilot(person=False,appointments=0);out=compose(FactContract(e,p))
        self.assertTrue(out.startswith('I would check the master bedroom contact before you leave'))
        self.assertIn('reporting open now',out);self.assertNotIn('Magnet Sensor',out)
        self.assertNotIn('bedroom window',out);self.assertNotIn('safe',out)
    def test_unverified_metadata_does_not_silently_become_window(self):
        e,p=pilot(person=False,appointments=0);e['facts'][0]['data'].pop('active_details')
        out=compose(FactContract(e,p));self.assertIn('Magnet Sensor Master Bedroom',out)
        self.assertNotIn('bedroom window',out)
    def test_contact_metadata_must_bind_to_the_actual_example(self):
        e,p=pilot(person=False,appointments=0)
        e['facts'][0]['data']['active_details'][0]['name']='Different window'
        with self.assertRaises(ValueError):FactContract(e,p)
    def test_person_weather_leads_with_the_actual_calendar_entry(self):
        e,p=pilot();out=compose(FactContract(e,p))
        self.assertTrue(out.startswith('Taylor has “Fiktiv musikkonkurranse” in the calendar for 10:00 tomorrow.'))
        self.assertIn('If those plans involve time outside near home tomorrow',out)
        self.assertIn('only a 0.4% chance of precipitation',out)
        for wrong in ('attending','indoors','will not affect','rain preparation','Meanwhile','Alongside that','HA currently'):
            self.assertNotIn(wrong,out)
    def test_focus_is_enforced_independently_of_the_model(self):
        e,p=pilot();c=FactContract(e,p)
        with self.assertRaisesRegex(ValueError,'Question focus order'):compose(c,['W1','A1'])
    def test_low_probability_has_no_separate_weather_advice_slot(self):
        for probability in (0,0.4,14,20):
            e,p=pilot(probability);c=FactContract(e,p);out=compose(c)
            self.assertNotIn('I1',c.clauses)
            self.assertIn(f'{probability}% chance of precipitation',out)
            self.assertNotIn('rain preparation',out);self.assertNotIn('waterproof',out)
    def test_possible_precipitation_has_conditional_local_advice(self):
        e,p=pilot(50);c=FactContract(e,p);out=compose(c)
        self.assertIn('a 50% chance of precipitation',out)
        self.assertIn('before spending time outdoors here',out)
        for wrong in ('will rain','must','need to','indoors','cancel'):self.assertNotIn(wrong,out)
    def test_wet_and_snowy_advice_is_not_a_venue_or_attendance_claim(self):
        for condition in ('rainy','snowy'):
            e,p=pilot(90,condition=condition);out=compose(FactContract(e,p))
            self.assertIn('could be useful for any time outside near home',out)
            self.assertNotIn('competition is outdoors',out)
    def test_missing_probability_is_not_zero_and_conflicting_weather_still_rechecks(self):
        for probability,condition,phrase in [(None,'cloudy','does not give a precipitation probability'),
            (0,'rainy','condition and precipitation probability disagree')]:
            e,p=pilot(probability,condition=condition);out=compose(FactContract(e,p))
            self.assertIn(phrase,out)
            if probability is None:self.assertNotIn('%',out)
    def test_two_dates_keep_low_forecast_and_advice_on_the_correct_day(self):
        e,p=pilot();p['end']='2026-10-26'
        e['facts'][0]['data']=ForecastReport('weather.fixture',p['start'],p['end'],STAMP,
            (ForecastDay('2026-10-24','partlycloudy',0.4),ForecastDay('2026-10-25','rainy',90))).data()
        c=FactContract(e,p);out=compose(c)
        self.assertNotIn('I1',c.clauses);self.assertIn('I2',c.clauses)
        self.assertIn('Tomorrow looks partly cloudy around home, with only a 0.4%',out)
        self.assertIn('Sunday looks rainy around home, with a 90%',out)
        with self.assertRaises(ValueError):compose(c,['A1','W1','I2','W2'])
    def test_empty_calendar_means_no_returned_entry_not_no_plans(self):
        e,p=pilot(appointments=0);out=compose(FactContract(e,p))
        self.assertTrue(out.startswith('I did not find an appointment for Taylor in the connected calendar tomorrow.'))
        self.assertNotIn('no plans',out);self.assertNotIn('free day',out)
    def test_unavailable_calendar_is_not_described_as_empty(self):
        e,p=pilot(appointments=0);e['facts']=[f for f in e['facts'] if f['kind']!='coverage']
        out=compose(FactContract(e,p));self.assertTrue(out.startswith("I could not check Taylor's calendar"))
        self.assertNotIn('did not find',out)
    def test_multiple_appointments_are_chronological_and_not_silently_discarded(self):
        e,p=pilot(appointments=5);c=FactContract(e,p);out=compose(c)
        self.assertEqual(c.lead,['A1']);self.assertIn('2 more calendar entries',out)
        self.assertEqual(out.count("Taylor's calendar has"),1)
        self.assertNotIn('Meanwhile',out)
        self.assertLess(out.index('10:00'),out.index('11:00'));self.assertLess(out.index('12:00'),out.index('0.4%'))
    def test_bogus_venue_advice_and_probability_rewrites_cannot_use_connectors(self):
        e,p=pilot();c=FactContract(e,p)
        for extra in ('The competition is indoors, ','It will not affect her event, ','0.4% chance of cloud, '):
            with self.assertRaises(ValueError):c.render(json.dumps({'segments':[
                {'fact':'A1','before':extra,'after':'.'},{'fact':'W1','before':'','after':'.'}]}),require_structured=True)
    def test_empty_owner_cannot_become_a_personal_appointment(self):
        e,p=pilot();e['facts'][-1]['owners']=[]
        with self.assertRaises(ValueError):FactContract(e,p)
    def test_all_day_entry_does_not_become_midnight_or_attendance(self):
        e,p=pilot();e['facts'][-1].update(all_day=True,local_start='00:00')
        out=compose(FactContract(e,p));self.assertIn('as an all-day calendar entry tomorrow',out)
        self.assertNotIn('00:00',out);self.assertNotIn('attending',out)
    def test_empty_multi_day_calendar_keeps_the_requested_period(self):
        e,p=pilot(appointments=0);p['end']='2026-10-26'
        e['facts'][0]['data']=ForecastReport('weather.fixture',p['start'],p['end'],STAMP,
            (ForecastDay('2026-10-24','cloudy',14),ForecastDay('2026-10-25','rainy',90))).data()
        out=compose(FactContract(e,p));self.assertIn('connected calendar from tomorrow to Sunday',out)

if __name__=='__main__':unittest.main()
