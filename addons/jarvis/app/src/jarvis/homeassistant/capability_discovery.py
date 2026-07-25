"""Read-only discovery of Home Assistant service and entity capabilities."""
from __future__ import annotations
from jarvis.models.home_assistant_gateway import HomeAssistantCapabilityCatalog,HomeAssistantServiceDefinition
class HomeAssistantCapabilityDiscovery:
 def __init__(self,client):self._client=client
 async def discover(self):
  services=[]
  for domain,definitions in (await self._client.get_services()).items():
   for service,definition in definitions.items(): services.append(HomeAssistantServiceDefinition(domain,service,frozenset(definition.get("fields",{}))))
  entities=frozenset(entity["entity_id"] for entity in await self._client.get_states())
  return HomeAssistantCapabilityCatalog(tuple(sorted(services,key=lambda s:(s.domain,s.service))),entities)
