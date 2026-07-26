"""Fail-closed expansion of explicit Home Assistant access policy."""
from __future__ import annotations


PROTECTED_DOMAINS = frozenset({"camera", "lock", "alarm_control_panel", "automation", "script", "device_tracker"})


def resolve_entities(catalog, entity_ids=(), domains=(), excluded_entities=(), read_only_exceptions=()):
    """Return discovered entities allowed by exact IDs or domains, minus exclusions."""
    exact, permitted_domains, excluded, exceptions = frozenset(entity_ids), frozenset(domains), frozenset(excluded_entities), frozenset(read_only_exceptions)
    return frozenset(
        entity_id for entity_id in catalog.entity_ids
        if entity_id not in excluded and (entity_id in exceptions or (entity_id.partition(".")[0] not in PROTECTED_DOMAINS and (entity_id in exact or entity_id.partition(".")[0] in permitted_domains)))
    )
