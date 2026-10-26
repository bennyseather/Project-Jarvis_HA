"""Fictional natural preparation contracts. No household data, audio or writes."""
from copy import deepcopy
import unittest
from jarvis.event_preparation import EventPreparation
from jarvis.household_activities import notes
from jarvis.preparation_wording import activity_name,join_words,usual_preparation


class WordingTests(unittest.TestCase):
    def event(self,identifier='F1',**change):
        return {'id':identifier,'text':'Club','owners':['mia'],'owner_name':'Mia','date':'2026-10-24',
                'date_label':'Saturday 24 October','local_start':'14:15','all_day':False,'location':'',
                'description_units':[],'activity_profile':{'activity':'music orchestra practice','equipment':['instrument','sheet music'],
                    'preparation':None,'usual_venue':'Fictional School','duration_minutes':None},**change}
    def selection(self,events,selected_notes=()):
        return {'events':[{'id':e['id'],'excerpts':[]} for e in events],
                'notes':list(selected_notes),'suggestion':'none','question':'none'}
    def render(self,events,selected_notes=True,speaker=None):
        ns=[dict(n,id='N'+str(i)) for i,n in enumerate(notes(events,'preparation'),1)]
        obj=self.selection(events,[n['id'] for n in ns] if selected_notes else [])
        return EventPreparation.render(obj,events,ns,speaker,'2026-10-23')
    def test_combined_day_and_meaning_not_raw_fields(self):
        music=self.event();sport=self.event('F2',text='Workout',local_start='16:55',location='Fictional Gym')
        sport['activity_profile']={'activity':'rhythmic gymnastics','equipment':['water'],
            'preparation':'Wear training clothes and tie her hair back.','usual_venue':'Usual Gym','duration_minutes':None}
        before=deepcopy([music,sport]);text=self.render([music,sport])
        self.assertIn('Tomorrow, Mia has orchestra practice at 14:15 and rhythmic gymnastics at 16:55',text)
        self.assertIn('the instrument and sheet music',text);self.assertIn('wear training clothes and tie her hair back',text)
        self.assertIn('bring water',text);self.assertIn('usually takes place at “Fictional School”',text)
        for raw in ('recorded as','usual equipment for','usual preparation for','usual kit is','“instrument”','“water”','“Workout”'):
            self.assertNotIn(raw,text)
        self.assertEqual(before,[music,sport])
    def test_current_details_override_usual(self):
        event=self.event(location='Current School',description_units=['Do not bring the instrument.'])
        text=self.render([event]);self.assertIn('Current School',text)
        self.assertNotIn('Fictional School',text);self.assertNotIn('sheet music',text)
    def test_unselected_notes_never_added(self):
        text=self.render([self.event()],selected_notes=False)
        self.assertNotIn('instrument',text);self.assertNotIn('Fictional School',text)
    def test_different_owner_or_day_never_combined(self):
        one=self.event();two=self.event('F2',owners=['emrik'],owner_name='Emrik',date='2026-10-25',date_label='Sunday 25 October')
        text=self.render([one,two],selected_notes=False)
        self.assertIn('Tomorrow, Mia has',text);self.assertIn('On Sunday 25 October, Emrik has',text)
    def test_first_person_and_all_day_preserved(self):
        event=self.event(owners=['benny'],owner_name='Benny',date='2026-10-23',all_day=True)
        text=self.render([event],selected_notes=False,speaker='benny')
        self.assertIn('Today, you have',text);self.assertIn('all day',text);self.assertNotIn('14:15',text)
    def test_generic_source_title_kept_without_confirmed_mapping(self):
        event=self.event();event.pop('activity_profile');event['text']='Unclassified rehearsal'
        text=self.render([event],selected_notes=False)
        self.assertIn('“Unclassified rehearsal”',text);self.assertNotIn('orchestra',text)
    def test_negations_and_conditions_stay_whole(self):
        for source in ('Do not bring the instrument.','If the practice moves outdoors, bring a coat.'):
            event=self.event();obj=self.selection([event]);obj['events'][0]['excerpts']=[source]
            text=EventPreparation.render(obj,[event],[],None,'2026-10-23')
            self.assertIn('“'+source+'”',text)
            usual=usual_preparation('club',[],source);self.assertIn('“'+source+'”',usual)
    def test_simple_imperative_does_not_drop_internal_words(self):
        text=usual_preparation('robotics',['project folder'],'Check that the battery is not empty.')
        self.assertIn('check that the battery is not empty',text);self.assertIn('project folder',text)
    def test_no_automatic_sport_or_subtype_alias(self):
        for value in ('training','gymnastics','music rehearsal','band practice'):
            self.assertEqual(activity_name(value),value)
    def test_natural_lists(self):
        self.assertEqual(join_words(['one','two']),'one and two')
        self.assertEqual(join_words(['one','two','three']),'one, two, and three')

    def test_usual_notes_keep_owner_binding_when_activities_match(self):
        one=self.event();two=self.event('F2',owners=['emrik'],owner_name='Emrik')
        text=self.render([one,two]);self.assertIn("For Mia's orchestra practice",text)
        self.assertIn("For Emrik's orchestra practice",text)
