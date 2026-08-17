"""Fast, local Home Assistant weather forecasts."""

from __future__ import annotations


class LocalWeatherIntelligence:
    """Answer ordinary forecasts without an LLM or public web search."""

    def __init__(self, client, registry, allowed_entities) -> None:
        self._client = client
        self._registry = registry
        self._allowed = frozenset(allowed_entities)

    async def handle(self, text: str):
        normalized = " ".join(text.casefold().strip(" .?!").split())
        if not any(word in normalized for word in ("weather", "forecast")):
            return None
        if any(word in normalized for word in ("card", "entity", "integration")):
            return None
        entities = [
            entity for entity in self._registry.all()
            if entity.domain == "weather" and entity.entity_id in self._allowed
        ]
        if not entities:
            return None
        preferred = next(
            (entity for entity in entities if entity.entity_id == "weather.forecast_home"),
            entities[0],
        )
        day_index = 1 if "tomorrow" in normalized else 0
        try:
            response = await self._client.call_service_response(
                "weather",
                "get_forecasts",
                {"entity_id": preferred.entity_id, "type": "daily"},
            )
            forecast = response.get(preferred.entity_id, {}).get("forecast", ())
        except Exception:
            forecast = ()
        if len(forecast) <= day_index:
            return {
                "status": "unavailable",
                "message": "The Home Assistant weather forecast is currently unavailable.",
            }
        item = forecast[day_index]
        day = "Tomorrow" if day_index else "Today"
        condition = str(item.get("condition", "unknown")).replace("_", " ")
        high = item.get("temperature")
        low = item.get("templow")
        rain = item.get("precipitation_probability")
        details = [f"{day} will be {condition}"]
        if high is not None and low is not None:
            details.append(f"with temperatures between {low:g} and {high:g} degrees")
        elif high is not None:
            details.append(f"with a high of {high:g} degrees")
        if rain is not None:
            details.append(f"and a {rain:g} percent chance of precipitation")
        return {
            "status": "success",
            "message": ", ".join(details) + ".",
            "source": preferred.entity_id,
        }
