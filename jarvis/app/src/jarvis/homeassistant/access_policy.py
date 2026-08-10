"""Fail-closed expansion of explicit Home Assistant access policy."""
from __future__ import annotations


PROTECTED_DOMAINS = frozenset({"camera", "lock", "alarm_control_panel", "automation", "script", "device_tracker"})

# These domains change Home Assistant itself rather than operate a discovered device.
CONTROL_PLANE_SERVICE_DOMAINS = frozenset({
    "automation", "backup", "config", "conversation", "frontend", "hassio", "history",
    "homeassistant", "logbook", "logger", "lovelace", "notify", "persistent_notification",
    "python_script", "recorder", "rest_command", "script", "system_log", "tts", "webhook",
})


def resolve_entities(catalog, entity_ids=(), domains=(), excluded_entities=(), read_only_exceptions=(), all_entities=False):
    """Return discovered entities allowed by exact IDs or domains, minus exclusions."""
    exact, permitted_domains, excluded, exceptions = frozenset(entity_ids), frozenset(domains), frozenset(excluded_entities), frozenset(read_only_exceptions)
    return frozenset(
        entity_id for entity_id in catalog.entity_ids
        if entity_id not in excluded and (
            all_entities or entity_id in exceptions or (
                entity_id.partition(".")[0] not in PROTECTED_DOMAINS
                and (entity_id in exact or entity_id.partition(".")[0] in permitted_domains)
            )
        )
    )


def resolve_device_services(catalog, all_device_services=False, configured_services=()):
    """Return entity-targeted services, never Home Assistant control-plane services."""
    configured = frozenset(configured_services)
    entity_domains = {entity_id.partition(".")[0] for entity_id in catalog.entity_ids}
    return frozenset(
        f"{service.domain}.{service.service}"
        for service in catalog.services
        if service.domain in entity_domains
        and service.domain not in CONTROL_PLANE_SERVICE_DOMAINS
        and (all_device_services or f"{service.domain}.{service.service}" in configured or f"{service.domain}.*" in configured)
    )
