"""Provider-neutral contracts for policy-controlled Home Assistant actions."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
class HomeAssistantRisk(str,Enum): READ_ONLY="read_only"; IMMEDIATE="immediate"; CONFIRM_REQUIRED="confirm_required"; HIGH_IMPACT_CONFIRM_REQUIRED="high_impact_confirm_required"; FORBIDDEN="forbidden"
@dataclass(frozen=True,slots=True)
class HomeAssistantActionProposal:
 domain:str; service:str; entity_ids:tuple[str,...]=(); service_data:Mapping[str,object]=field(default_factory=dict); summary:str=""
@dataclass(frozen=True,slots=True)
class HomeAssistantRiskDecision:
 risk:HomeAssistantRisk; reason_code:str
@dataclass(frozen=True,slots=True)
class HomeAssistantServiceDefinition:
 domain:str; service:str; fields:frozenset[str]=frozenset()
@dataclass(frozen=True,slots=True)
class HomeAssistantCapabilityCatalog:
 services:tuple[HomeAssistantServiceDefinition,...]=(); entity_ids:frozenset[str]=frozenset()
