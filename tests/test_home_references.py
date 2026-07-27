import unittest

from jarvis.homeassistant.home_references import build_home_references


class HomeReferenceTests(unittest.TestCase):
    def test_light_group_and_device_inherited_area_are_discovered(self):
        entities = [
            {"entity_id": "light.interior", "attributes": {
                "friendly_name": "Interior lights",
                "entity_id": ["light.office", "light.hall"],
            }},
            {"entity_id": "light.office", "attributes": {"friendly_name": "Office"}},
            {"entity_id": "light.hall", "attributes": {"friendly_name": "Hall"}},
        ]
        areas = [{"area_id": "upstairs_office", "name": "Upstairs Office"}]
        registry = [
            {"ei": "light.office", "di": "office_device"},
            {"ei": "light.hall", "ai": "upstairs_office"},
        ]
        devices = [{"id": "office_device", "area_id": "upstairs_office"}]
        names, area_members, groups = build_home_references(
            entities, areas, registry, devices,
            {"light.interior", "light.office", "light.hall"},
        )
        self.assertEqual(names["Office"], ["light.office"])
        self.assertEqual(area_members["upstairs office"], ["light.office", "light.hall"])
        self.assertEqual(groups["interior lights"], ("light.office", "light.hall"))
