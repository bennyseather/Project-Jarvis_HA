"""Project Jarvis RSS cache integration."""
from __future__ import annotations

import json
from pathlib import Path

from homeassistant.const import Platform
from homeassistant.helpers import discovery

DOMAIN = "jarvis_rss"
PLATFORMS = (Platform.SENSOR,)
CACHE = Path("/share/jarvis_rss/stories.json")
RSS_ENTITIES = (
    "sensor.jarvis_rss_top_stories",
    "sensor.jarvis_rss_feed_health",
)


def load_cache():
    try:
        value = json.loads(CACHE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {"read": set()})

    async def refresh(_call):
        hass.bus.async_fire("jarvis_rss_refresh_requested")
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": list(RSS_ENTITIES)},
            blocking=True,
        )

    async def mark_read(call):
        story_id = str(call.data.get("story_id", ""))
        if story_id:
            hass.data[DOMAIN]["read"].add(story_id)
            hass.bus.async_fire("jarvis_rss_read_changed")
            await hass.services.async_call(
                "homeassistant",
                "update_entity",
                {"entity_id": "sensor.jarvis_rss_top_stories"},
                blocking=True,
            )

    hass.services.async_register(DOMAIN, "refresh", refresh)
    hass.services.async_register(DOMAIN, "mark_read", mark_read)
    hass.async_create_task(discovery.async_load_platform(hass, "sensor", DOMAIN, {}, config))
    return True
