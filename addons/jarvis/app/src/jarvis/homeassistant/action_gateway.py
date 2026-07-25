"""Confirmed, policy-controlled Home Assistant service gateway."""
from __future__ import annotations
from jarvis.models.home_assistant_gateway import HomeAssistantRisk
class ConfirmedHomeAssistantActionGateway:
 def __init__(self,capability_gateway,risk_policy,pending,client):self._cap,self._risk,self._pending,self._client=capability_gateway,risk_policy,pending,client
 def request(self,p):
  valid,reason=self._cap.validate(p)
  if not valid:return {"status":"forbidden","reason_code":reason}
  decision=self._risk.evaluate(p)
  if decision.risk is HomeAssistantRisk.FORBIDDEN:return {"status":"forbidden","reason_code":decision.reason_code}
  return {"status":"requires_confirmation","token":self._pending.create(p,decision.risk),"summary":p.summary,"risk":decision.risk.value}
 async def confirm(self,token,p):
  decision=self._risk.evaluate(p)
  if decision.risk is HomeAssistantRisk.FORBIDDEN or not self._pending.consume(token,p,decision.risk):return {"status":"forbidden","reason_code":"invalid_confirmation"}
  await self._client.call_service(p.domain,p.service,{"entity_id":p.entity_ids[0],**p.service_data})
  return {"status":"success"}
