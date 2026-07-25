"""Explicit, review-only learning proposal contracts."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
class LearningDestination(str,Enum): MEMORY="memory"; KNOWLEDGE="knowledge"
class LearningStatus(str,Enum): PENDING="pending"; APPROVED="approved"; REJECTED="rejected"; CANCELLED="cancelled"
@dataclass(frozen=True,slots=True)
class LearningProposal:
 proposal_id:str; summary:str; content:str; destination:LearningDestination; source_category:str; status:LearningStatus=LearningStatus.PENDING
