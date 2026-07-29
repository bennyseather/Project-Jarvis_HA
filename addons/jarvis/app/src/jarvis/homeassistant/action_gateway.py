"""Confirmed, policy-controlled Home Assistant service gateway."""
from __future__ import annotations
import asyncio
from jarvis.models.home_assistant_gateway import HomeAssistantRisk
class ConfirmedHomeAssistantActionGateway:
 def __init__(self,capability_gateway,risk_policy,pending,client,audit_store=None):
  self._cap,self._risk,self._pending,self._client,self._audit=capability_gateway,risk_policy,pending,client,audit_store
  self._background=set()
 def request(self,p):
  if len(p.entity_ids)>20:return {"status":"forbidden","reason_code":"too_many_entities"}
  valid,reason=self._cap.validate(p)
  if not valid:return {"status":"forbidden","reason_code":reason}
  decision=self._risk.evaluate(p)
  if decision.risk is HomeAssistantRisk.FORBIDDEN:return {"status":"forbidden","reason_code":decision.reason_code}
  if decision.risk is HomeAssistantRisk.IMMEDIATE:return {"status":"immediate_action","summary":p.summary}
  return {"status":"requires_confirmation","token":self._pending.create(p,decision.risk),"summary":p.summary,"risk":decision.risk.value}
 async def execute_immediate(self,p):
  valid,reason=self._cap.validate(p)
  if not valid:return {"status":"forbidden","reason_code":reason}
  decision=self._risk.evaluate(p)
  if decision.risk is not HomeAssistantRisk.IMMEDIATE:return {"status":"forbidden","reason_code":"immediate_action_not_authorized"}
  succeeded,failed=[],[]
  target=self._entity_target(p)
  if hasattr(self._client,"dispatch_service"):
   task=await self._client.dispatch_service(
    p.domain,p.service,{"entity_id":target,**p.service_data}
   )
   done,_=await asyncio.wait({task},timeout=1.0)
   if not done:
    completion=asyncio.create_task(self._complete_deferred(task,p))
    self._background.add(completion)
    completion.add_done_callback(self._background.discard)
    return {
     "status":"success",
     "message":f"Action sent to {self._device_count(len(p.entity_ids))}.",
     "succeeded":tuple(p.entity_ids),
     "failed":(),
     "completion_pending":True,
    }
   try:task.result()
   except Exception:succeeded,failed=await self._reconcile(p)
   else:succeeded=list(p.entity_ids)
  else:
   try:
    await self._client.call_service(p.domain,p.service,{"entity_id":target,**p.service_data})
   except Exception:
    succeeded,failed=await self._reconcile(p)
   else:
    succeeded=list(p.entity_ids)
  for entity_id in succeeded:self._record_one(p,entity_id,"success")
  for entity_id in failed:self._record_one(p,entity_id,"unavailable","home_assistant_service_failed")
  if not succeeded:return {"status":"unavailable","message":f"Action failed for {self._device_count(len(failed))}.","succeeded":(),"failed":tuple(failed)}
  message=f"Action completed for {self._device_count(len(succeeded))}."
  if failed:message+=f" {self._device_count(len(failed))} {'was' if len(failed)==1 else 'were'} unavailable."
  return {"status":"success","message":message,"succeeded":tuple(succeeded),"failed":tuple(failed)}
 async def confirm(self,token,p):
  decision=self._risk.evaluate(p)
  if decision.risk is HomeAssistantRisk.FORBIDDEN or not self._pending.consume(token,p,decision.risk):
   self._record(p,"forbidden","invalid_confirmation")
   return {"status":"forbidden","reason_code":"invalid_confirmation"}
  try: await self._client.call_service(p.domain,p.service,{"entity_id":self._entity_target(p),**p.service_data})
  except Exception:
   self._record(p,"unavailable","home_assistant_service_failed")
   return {"status":"unavailable","reason_code":"home_assistant_service_failed"}
  self._record(p,"success")
  return {"status":"success"}
 def _record(self,p,outcome,reason_code=None):
  if self._audit is not None:self._audit.record(p.domain,p.service,p.entity_ids,outcome,reason_code)
 def _record_one(self,p,entity_id,outcome,reason_code=None):
  if self._audit is not None:self._audit.record(p.domain,p.service,(entity_id,),outcome,reason_code)
 async def _complete_deferred(self,task,p):
  try:await task
  except Exception:succeeded,failed=await self._reconcile(p)
  else:succeeded,failed=list(p.entity_ids),[]
  for entity_id in succeeded:self._record_one(p,entity_id,"success")
  for entity_id in failed:self._record_one(p,entity_id,"unavailable","home_assistant_service_failed")
 async def _reconcile(self,p):
  expected=self._expected_state(p.service)
  if expected is None or not hasattr(self._client,"get_states"):
   return [],list(p.entity_ids)
  try:
   states=await self._client.get_states()
   current=self._states(states)
   unresolved=[
    entity_id for entity_id in p.entity_ids
    if current.get(entity_id) not in expected
   ]
   if unresolved:
    await asyncio.sleep(0.2)
    current=self._states(await self._client.get_states())
  except Exception:return [],list(p.entity_ids)
  succeeded=[
   entity_id for entity_id in p.entity_ids
   if current.get(entity_id) in expected
  ]
  return succeeded,[entity_id for entity_id in p.entity_ids if entity_id not in succeeded]
 @staticmethod
 def _states(states):
  return {
   item.get("entity_id"):str(item.get("state","unknown"))
   for item in states if isinstance(item,dict)
  }
 @staticmethod
 def _expected_state(service):
  return {
   "turn_on":frozenset({"on"}),
   "turn_off":frozenset({"off"}),
   "open_cover":frozenset({"open","opening"}),
   "close_cover":frozenset({"closed","closing"}),
   "lock":frozenset({"locked"}),
   "unlock":frozenset({"unlocked"}),
  }.get(service)
 @staticmethod
 def _device_count(count):return f"{count} {'device' if count==1 else 'devices'}"
 @staticmethod
 def _entity_target(p):return p.entity_ids[0] if len(p.entity_ids)==1 else list(p.entity_ids)
