"""Build bounded natural-name, area, and group references from HA metadata."""
from __future__ import annotations


def build_home_references(entities, areas, registry, devices, permitted_entities):
    permitted = frozenset(permitted_entities)
    friendly_names: dict[str, list[str]] = {}
    for item in entities:
        entity_id = item.get("entity_id")
        friendly_name = item.get("attributes", {}).get("friendly_name")
        if entity_id in permitted and friendly_name:
            friendly_names.setdefault(str(friendly_name), []).append(entity_id)

    area_names = {
        item.get("area_id"): str(item.get("name", "")).casefold()
        for item in areas if item.get("area_id") and item.get("name")
    }
    device_areas = {
        item.get("id"): item.get("area_id")
        for item in devices if item.get("id")
    }
    area_members: dict[str, list[str]] = {}
    for item in registry:
        entity_id = item.get("entity_id", item.get("ei"))
        area_id = item.get("area_id", item.get("ai"))
        device_id = item.get("device_id", item.get("di"))
        area_name = area_names.get(area_id or device_areas.get(device_id))
        if area_name and entity_id in permitted:
            area_members.setdefault(area_name, []).append(entity_id)

    groups = {}
    for item in entities:
        members = item.get("attributes", {}).get("entity_id")
        if isinstance(members, (list, tuple)):
            name = str(item.get("attributes", {}).get("friendly_name", item["entity_id"])).casefold()
            groups[name] = tuple(entity_id for entity_id in members if entity_id in permitted)

    return friendly_names, area_members, groups
