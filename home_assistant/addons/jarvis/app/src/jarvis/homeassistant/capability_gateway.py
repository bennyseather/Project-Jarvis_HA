"""Validation gateway; execution is intentionally not enabled yet."""
from __future__ import annotations
from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal,HomeAssistantCapabilityCatalog
class HomeAssistantCapabilityGateway:
 def __init__(self,catalog:HomeAssistantCapabilityCatalog): self._catalog=catalog
 def validate(self,p:HomeAssistantActionProposal):
  service=next((s for s in self._catalog.services if (s.domain,s.service)==(p.domain,p.service)),None)
  if service is None:return False,"unknown_service"
  if any(e not in self._catalog.entity_ids for e in p.entity_ids):return False,"unknown_entity"
  if not set(p.service_data).issubset(service.fields):return False,"unknown_service_field"
  return True,"valid"
