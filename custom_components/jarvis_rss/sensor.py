"""Home Assistant entities for the Project Jarvis RSS cache."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

from . import DOMAIN, load_cache


async def async_setup_platform(hass, _config, async_add_entities, _discovery_info=None):
    entities = [JarvisRSSStories(hass), JarvisRSSHealth(hass)]
    async_add_entities(entities, True)

    @callback
    def async_refresh(_now):
        for entity in entities:
            entity.async_schedule_update_ha_state(True)

    async_track_time_interval(hass, async_refresh, timedelta(minutes=1))


class JarvisRSSStories(SensorEntity):
    _attr_name = "Jarvis RSS Top Stories"
    _attr_unique_id = "jarvis_rss_top_stories"
    _attr_icon = "mdi:rss"

    def __init__(self, hass): self.hass = hass; self._cache = {}
    async def async_update(self): self._cache = await self.hass.async_add_executor_job(load_cache)
    @property
    def native_value(self): return len(self._cache.get("stories", ()))
    @property
    def extra_state_attributes(self):
        read = self.hass.data[DOMAIN]["read"]
        # HA recorder limits state attributes to 16 KiB. Keep the complete cache
        # on disk for Jarvis, while exposing a compact dashboard window here.
        stories = [
            {
                "id": item.get("id"),
                "title": str(item.get("title", ""))[:240],
                "source": str(item.get("source", ""))[:80],
                "url": str(item.get("url", ""))[:500],
                "published": item.get("published"),
                "read": item.get("id") in read,
            }
            for item in self._cache.get("stories", ())[:16]
        ]
        return {"updated_at": self._cache.get("updated_at"), "stories": stories, "unread": sum(not item["read"] for item in stories)}


class JarvisRSSHealth(SensorEntity):
    _attr_name = "Jarvis RSS Feed Health"
    _attr_unique_id = "jarvis_rss_feed_health"
    _attr_icon = "mdi:rss-box"

    def __init__(self, hass): self.hass = hass; self._cache = {}
    async def async_update(self): self._cache = await self.hass.async_add_executor_job(load_cache)
    @property
    def native_value(self):
        feeds = self._cache.get("feeds", ())
        return "ok" if feeds and all(item.get("status") == "ok" for item in feeds) else "degraded" if feeds else "unavailable"
    @property
    def extra_state_attributes(self): return {"feeds": self._cache.get("feeds", ()), "updated_at": self._cache.get("updated_at")}
