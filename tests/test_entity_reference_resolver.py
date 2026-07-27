import unittest
from jarvis.homeassistant.entity_reference_resolver import EntityReferenceResolver
class Tests(unittest.TestCase):
 def test_alias_and_identifier_resolution(self):
  r=EntityReferenceResolver({"light.kitchen"},{"kitchen light":"light.kitchen"})
  self.assertEqual(r.resolve("kitchen light"),("light.kitchen",))
  self.assertEqual(r.resolve("light.kitchen"),("light.kitchen",))
 def test_unknown_and_ambiguous_are_deterministic(self):
  r=EntityReferenceResolver({"light.kitchen","light.kitchen_table"},{"kitchen":"light.kitchen","kitchen":"light.kitchen_table"})
  self.assertEqual(r.resolve("missing"),())
 def test_friendly_name_area_and_group_resolution_are_bounded_to_allowed_entities(self):
  r=EntityReferenceResolver({"light.kitchen","light.table"},friendly_names={"Kitchen lamp":"light.kitchen"},areas={"kitchen":("light.kitchen","light.private")},groups={"kitchen lights":("light.kitchen","light.table")})
  self.assertEqual(r.resolve("kitchen lamp"),("light.kitchen",))
  self.assertEqual(r.resolve("kitchen"),("light.kitchen",))
  self.assertEqual(r.resolve("kitchen lights"),("light.kitchen","light.table"))
 def test_duplicate_friendly_names_remain_ambiguous_and_domain_filter_is_deterministic(self):
  r=EntityReferenceResolver(
   {"light.office","light.office_desk","switch.office"},
   friendly_names={"Office":("light.office","light.office_desk")},
   areas={"upstairs office":("light.office","switch.office")},
  )
  self.assertEqual(r.resolve("office"),("light.office","light.office_desk"))
  self.assertFalse(r.is_collective("office"))
  self.assertEqual(r.resolve("upstairs office","light"),("light.office",))
  self.assertTrue(r.is_collective("upstairs office"))
 def test_finds_longest_explicit_reference_in_natural_text(self):
  r=EntityReferenceResolver(
   {"light.office","switch.heater"},
   friendly_names={"Office":"light.office"},
   areas={"upstairs office":("light.office","switch.heater")},
  )
  reference,matches,collective=r.find_in_text("What is the status of the upstairs office?")
  self.assertEqual(reference,"upstairs office")
  self.assertEqual(matches,("light.office","switch.heater"))
  self.assertTrue(collective)
 def test_finds_bounded_friendly_name_candidates_for_a_category_phrase(self):
  r=EntityReferenceResolver(
   {"light.porch_1","light.porch_2","camera.porch"},
   friendly_names={
    "Outside Porch 1":"light.porch_1",
    "Outside Porch 2":"light.porch_2",
    "Porch camera":"camera.porch",
   },
  )
  reference,matches,collective=r.find_in_text("What is the status of the porch lights?")
  self.assertEqual(reference,"porch")
  self.assertEqual(matches,("light.porch_1","light.porch_2"))
  self.assertFalse(collective)
  self.assertEqual(r.display_name("light.porch_1"),"Outside Porch 1")
  self.assertEqual(r.display_name("sensor.missing"),"sensor.missing")
