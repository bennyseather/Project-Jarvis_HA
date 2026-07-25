"""Process-local explicit learning proposal review and management."""
from __future__ import annotations
from dataclasses import replace
from jarvis.models.learning import LearningProposal,LearningStatus
class LearningProposalManager:
 def __init__(self,policy):self._policy=policy;self._items={}
 def submit(self,p):
  allowed,reason=self._policy.evaluate(p)
  if not allowed:return replace(p,status=LearningStatus.REJECTED),reason
  self._items[p.proposal_id]=p;return p,"review_required"
 def list_pending(self):return tuple(self._items[k] for k in sorted(self._items) if self._items[k].status is LearningStatus.PENDING)
 def decide(self,proposal_id,approve):
  p=self._items.get(proposal_id)
  if p is None or p.status is not LearningStatus.PENDING:return None
  result=replace(p,status=LearningStatus.APPROVED if approve else LearningStatus.REJECTED)
  self._items[proposal_id]=result;return result
 def cancel(self,proposal_id):
  p=self._items.get(proposal_id)
  if p is None or p.status is not LearningStatus.PENDING:return None
  result=replace(p,status=LearningStatus.CANCELLED);self._items[proposal_id]=result;return result
