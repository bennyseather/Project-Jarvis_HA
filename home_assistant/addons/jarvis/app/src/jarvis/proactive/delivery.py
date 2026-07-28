"""Home Assistant-owned delivery for bounded proactive suggestions."""

from __future__ import annotations


class HomeAssistantProactiveDelivery:
    def __init__(self, manager, policy, clock) -> None:
        self._manager = manager
        self._policy = policy
        self._clock = clock
        self._voice_route: dict[str, object] | None = None

    def set_voice_route(self, route: dict[str, object] | None) -> None:
        self._voice_route = None if route is None else dict(route)

    async def deliver(self, client) -> None:
        now = self._clock()
        for suggestion in self._manager.pending():
            if (
                self._policy.notification_enabled
                and self._policy.delivery_due(suggestion, "notification", now)
            ):
                await client.call_service(
                    "persistent_notification",
                    "create",
                    {
                        "title": "Project Jarvis",
                        "message": suggestion.message,
                        "notification_id": f"jarvis_{suggestion.suggestion_id}",
                    },
                )
                self._manager.mark_delivered(
                    suggestion.suggestion_id, "notification"
                )
            if (
                self._policy.voice_enabled
                and self._voice_route
                and self._policy.delivery_due(suggestion, "voice", now)
            ):
                route = self._voice_route
                data: dict[str, object] = {
                    "entity_id": route["tts_entity_id"],
                    "media_player_entity_id": route["media_player_entity_id"],
                    "message": suggestion.message,
                    "cache": True,
                }
                if route.get("language"):
                    data["language"] = route["language"]
                if route.get("voice"):
                    data["options"] = {"voice": route["voice"]}
                await client.call_service("tts", "speak", data)
                self._manager.mark_delivered(suggestion.suggestion_id, "voice")
