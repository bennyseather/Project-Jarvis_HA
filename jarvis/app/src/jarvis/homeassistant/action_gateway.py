"""Confirmed, policy-controlled Home Assistant service gateway."""
from __future__ import annotations
from jarvis.models.home_assistant_gateway import HomeAssistantRisk
class ConfirmedHomeAssistantActionGateway:
 def __init__(self,capability_gateway,risk_policy,pending,client,audit_store=None):self._cap,self._risk,self._pending,self._client,self._audit=capability_gateway,risk_policy,pending,client,audit_store
 def request(self,p):
  valid,reason=self._cap.validate(p)
  if not valid:return {"status":"forbidden","reason_code":reason}
  decision=self._risk.evaluate(p)
  if decision.risk is HomeAssistantRisk.FORBIDDEN:return {"status":"forbidden","reason_code":decision.reason_code}
  return {"status":"requires_confirmation","token":self._pending.create(p,decision.risk),"summary":p.summary,"risk":decision.risk.value}
 async def confirm(self,token,p):
  decision=self._risk.evaluate(p)
  if decision.risk is HomeAssistantRisk.FORBIDDEN or not self._pending.consume(token,p,decision.risk):
   self._record(p,"forbidden","invalid_confirmation")
   return {"status":"forbidden","reason_code":"invalid_confirmation"}
  try: await self._client.call_service(p.domain,p.service,{"entity_id":p.entity_ids[0],**p.service_data})
  except Exception:
   self._record(p,"unavailable","home_assistant_service_failed")
   return {"status":"unavailable","reason_code":"home_assistant_service_failed"}
  self._record(p,"success")
  return {"status":"success"}
 def _record(self,p,outcome,reason_code=None):
  if self._audit is not None:self._audit.record(p.domain,p.service,p.entity_ids,outcome,reason_code)
