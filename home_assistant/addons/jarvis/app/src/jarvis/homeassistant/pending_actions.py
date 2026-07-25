"""Process-local, one-time confirmations for validated Home Assistant actions."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from secrets import token_urlsafe
from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal,HomeAssistantRisk
@dataclass(frozen=True,slots=True)
class PendingAction: proposal:HomeAssistantActionProposal; risk:HomeAssistantRisk; expires_at:datetime; fingerprint:str
class PendingActionStore:
 def __init__(self,clock=None,ttl_seconds=60):self._clock=clock or (lambda:datetime.now(timezone.utc));self._ttl=timedelta(seconds=ttl_seconds);self._items={}
 def create(self,p,r):
  token=token_urlsafe(24);self._items[token]=PendingAction(p,r,self._clock()+self._ttl,self._fingerprint(p,r));return token
 def consume(self,token,p,r):
  item=self._items.pop(token,None)
  if item is None or item.expires_at<self._clock() or item.risk is not r or item.fingerprint!=self._fingerprint(p,r):return False
  return True
 @staticmethod
 def _fingerprint(p,r):return sha256(repr((p.domain,p.service,p.entity_ids,sorted(p.service_data.items()),p.summary,r.value)).encode()).hexdigest()
