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
