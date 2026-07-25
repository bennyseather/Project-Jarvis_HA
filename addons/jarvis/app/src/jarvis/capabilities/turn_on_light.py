"""
Capability for turning on a light.
"""

from jarvis.homeassistant.client import HomeAssistantClient
from jarvis.homeassistant.entity_resolver import EntityResolver


class TurnOnLightCapability:
    """
    Turns on a light resolved from a user target.
    """

    def __init__(
        self,
        home_assistant: HomeAssistantClient,
        resolver: EntityResolver,
    ):
        self.home_assistant = home_assistant
        self.resolver = resolver

    async def execute(self, target: str) -> bool:
        """
        Turn on the requested light.

        Returns True on success.
        """

        entity = self.resolver.resolve(
            target=target,
            domain="light",
        )

        if entity is None:
            return False

        await self.home_assistant.call_service(
            domain="light",
            service="turn_on",
            service_data={
                "entity_id": entity.entity_id,
            },
        )

        return True