"""Deny-by-default risk policy for Home Assistant actions."""
from __future__ import annotations
from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal,HomeAssistantRisk,HomeAssistantRiskDecision
class HomeAssistantRiskPolicy:
 def __init__(self, allowed=None, high_impact=None, allowed_entities=None): self._allowed=frozenset(allowed or ());self._high=frozenset(high_impact or ());self._entities=frozenset(allowed_entities or ())
 def evaluate(self,p:HomeAssistantActionProposal):
  key=f"{p.domain}.{p.service}"
  if not p.entity_ids or any(entity not in self._entities for entity in p.entity_ids):return HomeAssistantRiskDecision(HomeAssistantRisk.FORBIDDEN,"unauthorized_entity")
  if key in self._high:return HomeAssistantRiskDecision(HomeAssistantRisk.HIGH_IMPACT_CONFIRM_REQUIRED,"high_impact")
  if key in self._allowed:return HomeAssistantRiskDecision(HomeAssistantRisk.CONFIRM_REQUIRED,"confirmation_required")
  return HomeAssistantRiskDecision(HomeAssistantRisk.FORBIDDEN,"unclassified_service")
