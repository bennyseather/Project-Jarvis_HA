"""Fictional explicit-equivalence memory and display-only contracts."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from jarvis import household_activities as activities
from jarvis.activity_presentation import prepared
from jarvis.event_preparation import EventPreparation
from jarvis.event_composition import board
from jarvis.household_profile import HouseholdProfile
from test_planning_preparation_bundle import profile
import test_preparation_wording as wording


class LinkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'profile.json';self.path.write_text(json.dumps(profile()._data))
        self.p=HouseholdProfile.load(self.path)
        for title in ('Club A','Club B'):
            self.command(title,'means "gymnastics"')
    def command(self,title,tail):
        out=self.p.edit_request('Remember Mia\'s activity "'+title+'" in the family calendar '+tail,'link')
        self.assertEqual(out['status'],'clarification_required',out)
        out=self.p.edit_request('confirm household change','link');self.assertEqual(out['status'],'success',out)
    def test_explicit_relation_proposed_confirmed_reloaded_and_undoable(self):
        before=self.path.read_bytes()
        out=self.p.edit_request('Remember Mia\'s activity "Club B" in the family calendar is the same activity as "Club A"','link')
        self.assertEqual(out['status'],'clarification_required');self.assertEqual(before,self.path.read_bytes())
        self.p.edit_request('confirm household change','link');reloaded=HouseholdProfile.load(self.path)
        records=reloaded._data['activity_profiles'];self.assertEqual(activities.equivalence_key(reloaded._data,records[0]),activities.equivalence_key(reloaded._data,records[1]))
        self.assertIn('same activity as',activities.view('Show Mia\'s activity profiles',reloaded)['message'])
        self.p.edit_request('undo last household change','link');self.p.edit_request('confirm household change','link')
        self.assertTrue(all(activities.equivalence_key(self.p._data,r) is None for r in self.p._data['activity_profiles']))
    def test_same_kind_is_not_a_link(self):
        self.assertTrue(all(activities.equivalence_key(self.p._data,r) is None for r in self.p._data['activity_profiles']))
    def test_missing_self_different_kind_or_scope_rejected(self):
        self.command('Music','means "music practice"')
        for title in ('Missing','Club B','Music'):
            before=self.path.read_bytes();out=self.p.edit_request('Remember Mia\'s activity "Club B" in the family calendar is the same activity as "'+title+'"','link')
            self.assertEqual(out['status'],'clarification_required');self.assertEqual(before,self.path.read_bytes())
            self.assertNotIn('Proposed shared household change',out['message'])
    def test_deleted_or_redefined_target_severs_link_without_dangling_reference(self):
        self.command('Club B','is the same activity as "Club A"')
        for operation in ('delete','meaning'):
            if operation=='delete':
                self.p.edit_request('Forget Mia\'s activity "Club A" in the family calendar','link')
                self.p.edit_request('confirm household change','link')
            else:self.command('Club A','means "swimming"')
            self.assertTrue(all('same_activity_as' not in r for r in self.p._data['activity_profiles']))
            self.p.edit_request('undo last household change','link');self.p.edit_request('confirm household change','link')
    def test_invalid_equivalence_schema_rejected(self):
        original=self.p._data['activity_profiles']
        for value in (True,'ffffffff',original[0]['id']):
            data=deepcopy(self.p._data);data['activity_profiles'][0]['same_activity_as']=value
            with self.assertRaises(ValueError):HouseholdProfile(data)


class DisplayTests(unittest.TestCase):
    def setUp(self):
        factory=wording.WordingTests();self.one=factory.event(text='Club A',source='family',start='2026-10-24T17:00:00+02:00',end='2026-10-24T18:00:00+02:00',local_start='17:00',location='Current Hall')
        self.one['activity_profile']['activity']='gymnastics';self.one['activity_equivalence']=('aaaaaaaa','bbbbbbbb')
        self.two={**deepcopy(self.one),'id':'F2','text':'Club B'}
        self.events=[self.one,self.two]
        self.obj=factory.selection(self.events);self.obj['events'][0]['excerpts']=['Bring water.']
        self.obj['events'][1]['excerpts']=['Bring water.','Do not use the apparatus before training starts.']
    def test_display_coalesces_once_without_touching_sources_or_dropping_negation(self):
        snapshot=deepcopy((self.obj,self.events));obj,events,notes=prepared(self.obj,self.events,[])
        self.assertEqual(len(events),1);self.assertEqual(events[0]['presented_source_ids'],['F1','F2'])
        self.assertEqual(obj['events'][0]['excerpts'],['Bring water.','Do not use the apparatus before training starts.'])
        self.assertEqual(snapshot,(self.obj,self.events))
        text=EventPreparation.render(self.obj,self.events,[],None,'2026-10-23')
        self.assertEqual(text.count('gymnastics at 17:00'),1);self.assertEqual(text.count('Bring water.'),1)
        self.assertIn('Do not use the apparatus before training starts.',text)
    def test_no_equivalence_or_changed_scope_keeps_two_entries(self):
        for mutation in ('relation','owner','source','start','end','all_day','venue','usual'):
            other=deepcopy(self.two)
            if mutation=='relation':other.pop('activity_equivalence')
            elif mutation=='owner':other['owners']=['emrik']
            elif mutation=='source':other['source']='work'
            elif mutation=='start':other['start']='2026-10-24T18:00:00+02:00'
            elif mutation=='end':other['end']='2026-10-24T19:00:00+02:00'
            elif mutation=='all_day':other['all_day']=True
            elif mutation=='venue':other['location']='Other Hall'
            else:other['activity_profile']['equipment']=['goggles']
            self.assertEqual(len(prepared(self.obj,[self.one,other],[])[1]),2,mutation)
    def test_missing_venue_can_use_current_matching_source_not_usual_venue(self):
        self.one['location']='';out=prepared(self.obj,self.events,[])[1]
        self.assertEqual(len(out),1);self.assertEqual(out[0]['location'],'Current Hall')
    def test_unselected_alias_is_never_added(self):
        self.obj['events']=self.obj['events'][:1]
        obj,events,_=prepared(self.obj,self.events,[])
        self.assertEqual(events[0]['presented_source_ids'],['F1']);self.assertNotIn('apparatus',str(obj))
    def test_grouped_board_retains_whole_instructions_and_one_event(self):
        obj,events,ns=prepared(self.obj,self.events,[])
        by_id={i['id']:i['excerpts'] for i in obj['events']}
        facts=board('prepare',[dict(e,selected_excerpts=by_id[e['id']]) for e in events],[],None,'2026-10-23')
        self.assertEqual(len(facts['events']),1);self.assertEqual(len(facts['events'][0]['protected_instructions']),2)
    def test_distinct_selected_usual_notes_deduplicate_only_after_explicit_link(self):
        ns=[{'id':'N1','text':'Usual kit: water.','events':['F1'],'origin':'activity_profile'},
            {'id':'N2','text':'Usual kit: water.','events':['F2'],'origin':'activity_profile'}]
        self.obj['notes']=['N1','N2'];self.assertEqual(len(prepared(self.obj,self.events,ns)[2]),1)
        self.two.pop('activity_equivalence');self.assertEqual(len(prepared(self.obj,self.events,ns)[2]),2)


class ApplicationTests(unittest.IsolatedAsyncioTestCase):
    async def ask(self,question,linked=False,two=False):
        from datetime import datetime
        from test_planning_preparation_bundle import Client,ZONE,scope
        import test_event_preparation as fixtures
        p=profile();client=Client();provider=fixtures.Provider()
        for title in ('Sports A','Sports B'):
            activities.install(p._data,activities.proposal('Remember Mia\'s activity "'+title+'" in the family calendar means "gymnastics"',p._data))
        if linked:activities.install(p._data,activities.proposal('Remember Mia\'s activity "Sports B" in the family calendar is the same activity as "Sports A"',p._data))
        event={'summary':'Sports A','start':'2026-10-24T17:00:00+02:00','end':'2026-10-24T18:00:00+02:00',
            'location':'Fictional Hall','description':'Bring water. Do not use the apparatus before class. If class moves outdoors, bring a coat.'}
        client.events['calendar.familiekalender']=[event]+([{**event,'summary':'Sports B'}] if two else [])
        def select(context):return {'status':'success','message':json.dumps({'events':{e['id']:{'use':True,'units':[0]} for e in context['events']},
            'notes':{n['id']:False for n in context['approved_notes']},'suggestion':'none','question':'none'})}
        provider.respond=select;before=deepcopy((p._data,client.events))
        h=EventPreparation(p,client,tuple(client.events),provider,now=lambda:datetime(2026,10,23,12,tzinfo=ZONE))
        with scope(p,None,'s'):out=await h.handle(question,'s')
        self.assertEqual(before,(p._data,client.events));self.assertEqual(out['status'],'success')
        return out
    async def test_kit_selection_cannot_drop_negative_or_conditional_source_clauses(self):
        out=await self.ask('What should Mia bring for gymnastics tomorrow?')
        self.assertIn('Do not use the apparatus before class.',out['message'])
        self.assertIn('If class moves outdoors, bring a coat.',out['message'])
    async def test_direct_location_stays_short_without_instructions(self):
        out=await self.ask('Where is Mia\'s gymnastics tomorrow?')
        self.assertIn('Fictional Hall',out['message']);self.assertNotIn('apparatus',out['message']);self.assertNotIn('coat',out['message'])
    async def test_confirmed_same_occurrence_coalesces_in_full_handler(self):
        out=await self.ask('What should Mia prepare for tomorrow?',linked=True,two=True)
        self.assertEqual(out['selected_source_event_count'],2);self.assertEqual(out['presented_event_count'],1)
        self.assertEqual(out['message'].count('gymnastics at 17:00'),1)
        self.assertEqual(out['message'].count('Do not use the apparatus before class.'),1)
    async def test_unlinked_same_kind_and_time_stays_separate(self):
        out=await self.ask('What should Mia prepare for tomorrow?',two=True)
        self.assertEqual(out['selected_source_event_count'],2);self.assertEqual(out['presented_event_count'],2)
