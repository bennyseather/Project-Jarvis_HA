"""Fictional geocoder identity and member school language-alias regressions."""
import unittest
from types import SimpleNamespace
from jarvis.companion_transport import EnturTransport
from jarvis.companion_routing import CompanionRouting
from test_planning_preparation_bundle import profile
class PlaceTests(unittest.TestCase):
 def feature(self,label,lon=6,name=None):return {'geometry':{'coordinates':[lon,62]},'properties':{'label':label,'name':name or label}}
 def place(self,query,features):return EnturTransport(http=lambda *_:{'features':features}).place(query)
 def test_unrelated_single_school_result_is_not_a_destination(self):
  self.assertIsNone(self.place('Elm School',[self.feature('Discovery International School, Other Town')]))
 def test_distinctive_name_and_school_language_equivalence(self):
  self.assertEqual(self.place('Elm School',[self.feature('Elm skule, Town')])['label'],'Elm skule, Town')
 def test_address_number_is_not_silently_changed(self):
  self.assertIsNone(self.place('Examplegate 15, Town',[self.feature('Examplegate 5, Town')]))
 def test_multiple_matching_distant_places_are_ambiguous(self):
  with self.assertRaises(ValueError):self.place('Exampletown',[self.feature('Exampletown, North',6),self.feature('Exampletown, South',7)])
 def test_generic_school_without_a_name_is_not_geocoded(self):
  self.assertIsNone(self.place('school',[self.feature('Other School')]))
 def router(self):
  p=profile();next(m for m in p._data['members'] if m['id']=='mia')['schedule']={'school':{'name':'Elm Skule'}};return CompanionRouting(SimpleNamespace(profile=p))
 def event(self,owners=None,venue='Elm School'):return {'text':'School activity','description':'','owners':owners or ['mia'],'source':'family','location':venue}
 def test_member_school_supplies_its_canonical_query_without_changing_source_venue(self):
  result=self.router().venue(self.event());self.assertEqual(result['planning_place_quote'],'Elm Skule');self.assertEqual(result['current_venue'],'Elm School')
 def test_another_person_or_specific_venue_is_not_replaced_by_mia_school(self):
  self.assertEqual(self.router().venue(self.event(['emrik']))['planning_place_quote'],'Elm School')
  self.assertEqual(self.router().venue(self.event(venue='Oak School'))['planning_place_quote'],'Oak School')
if __name__=='__main__':unittest.main()
