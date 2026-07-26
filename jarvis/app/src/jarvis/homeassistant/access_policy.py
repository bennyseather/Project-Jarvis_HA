"""Fail-closed expansion of explicit Home Assistant access policy."""
from __future__ import annotations


def resolve_entities(catalog, entity_ids=(), domains=(), excluded_entities=()):
    """Return discovered entities allowed by exact IDs or domains, minus exclusions."""
    exact, permitted_domains, excluded = frozenset(entity_ids), frozenset(domains), frozenset(excluded_entities)
    return frozenset(
        entity_id for entity_id in catalog.entity_ids
        if entity_id not in excluded and (entity_id in exact or entity_id.partition(".")[0] in permitted_domains)
    )
