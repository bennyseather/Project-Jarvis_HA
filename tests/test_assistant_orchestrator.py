import unittest
from jarvis.core.assistant_orchestrator import AssistantOrchestrator
from jarvis.models.assistant_slice import AssistantProposal, AssistantProposalKind, HomeAssistantState
from jarvis.homeassistant.entity_reference_resolver import EntityReferenceResolver

class Model:
 def __init__(self,p): self.p=p
 def propose(self,i): return self.p
class Home:
 def __init__(self): self.calls=[]
 async def read_entity_state(self,id): self.calls.append(id); return HomeAssistantState(id,"on")
 async def read_entity_states(self,ids): self.calls.append(tuple(ids)); return tuple(HomeAssistantState(id,"on") for id in ids)
class Gateway:
 def request(self, action): return {"status":"requires_confirmation","token":"token"}
class Tests(unittest.IsolatedAsyncioTestCase):
 async def test_conversation_and_allowlisted_read(self):
  home=Home(); o=AssistantOrchestrator(Model(AssistantProposal(AssistantProposalKind.CONVERSATION,"Hello")),home)
  self.assertEqual((await o.handle("Hi"))["message"],"Hello")
  o=AssistantOrchestrator(Model(AssistantProposal(AssistantProposalKind.READ_ENTITY_STATE,"", "light.kitchen")),home,frozenset({"light.kitchen"}))
  state_result = await o.handle("state")
  self.assertEqual(state_result["state"],"on");self.assertEqual(state_result["message"],"light.kitchen is on.");self.assertEqual(home.calls,["light.kitchen"])
 async def test_blocked_entity_never_calls_home_assistant(self):
  home=Home();o=AssistantOrchestrator(Model(AssistantProposal(AssistantProposalKind.READ_ENTITY_STATE,entity_id="light.secret")),home)
  self.assertEqual((await o.handle("state"))["status"],"not_supported");self.assertEqual(home.calls,[])
 async def test_alias_resolves_only_to_allowed_entity(self):
  home=Home(); resolver=EntityReferenceResolver({"light.kitchen"},{"kitchen lamp":"light.kitchen"})
  orchestrator=AssistantOrchestrator(Model(AssistantProposal(AssistantProposalKind.READ_ENTITY_STATE,entity_id="kitchen lamp")),home,frozenset({"light.kitchen"}),resolver)
  self.assertEqual((await orchestrator.handle("state"))["entity_id"],"light.kitchen")
 async def test_group_read_returns_a_bounded_summary(self):
  home=Home(); resolver=EntityReferenceResolver({"light.kitchen","light.table"},{},groups={"kitchen lights":("light.kitchen","light.table")})
  proposal=AssistantProposal(AssistantProposalKind.READ_ENTITY_STATE,entity_id="kitchen lights")
  result=await AssistantOrchestrator(Model(proposal),home,frozenset({"light.kitchen","light.table"}),resolver).handle("state")
  self.assertEqual(result["status"],"success");self.assertIn("2 devices: 2 on",result["message"])
  self.assertEqual(home.calls,[("light.kitchen","light.table")])
 async def test_explicit_group_and_followup_reads_bypass_model_guessing(self):
  home=Home(); resolver=EntityReferenceResolver(
   {"light.kitchen","light.table"},{},
   groups={"interior lights":("light.kitchen","light.table"),
           "light.interior_lights":("light.kitchen","light.table")})
  model=Model(AssistantProposal(AssistantProposalKind.CONVERSATION,"Wrong"))
  orchestrator=AssistantOrchestrator(model,home,frozenset({"light.kitchen","light.table"}),resolver)
  first=await orchestrator.handle("What is the state of the interior lights?")
  followup=await orchestrator.handle("Are all of them on?")
  exact_group=await orchestrator.handle("What is the state of light.interior_lights?")
  bare_followup=await orchestrator.handle("all of them")
  self.assertIn("2 devices: 2 on",first["message"])
  self.assertIn("2 devices: 2 on",followup["message"])
  self.assertIn("2 devices: 2 on",exact_group["message"])
  self.assertIn("2 devices: 2 on",bare_followup["message"])
 async def test_both_resolves_pending_ambiguous_read_candidates(self):
  home=Home(); resolver=EntityReferenceResolver(
   {"light.porch_1","light.porch_2"},{},
   friendly_names={"Outside Porch 1":"light.porch_1","Outside Porch 2":"light.porch_2"})
  proposal=AssistantProposal(AssistantProposalKind.CONVERSATION,"Wrong")
  orchestrator=AssistantOrchestrator(Model(proposal),home,frozenset({"light.porch_1","light.porch_2"}),resolver)
  clarification=await orchestrator.handle("What is the status of the porch lights?")
  both=await orchestrator.handle("both")
  self.assertEqual(clarification["status"],"clarification_required")
  self.assertIn("Outside Porch 1",clarification["message"])
  self.assertIn("2 devices: 2 on",both["message"])
  self.assertIn("Outside Porch 1 is on",both["message"])
 async def test_oversized_new_reference_clears_prior_and_pending_scopes(self):
  ids={f"sensor.office_{index}" for index in range(21)}
  home=Home(); resolver=EntityReferenceResolver(
   ids|{"light.porch_1","light.porch_2"},{},
   friendly_names={
    **{f"Office {index}":f"sensor.office_{index}" for index in range(21)},
    "Outside Porch 1":"light.porch_1",
    "Outside Porch 2":"light.porch_2",
   },
   areas={"upstairs office":tuple(ids)},
  )
  model=Model(AssistantProposal(AssistantProposalKind.CONVERSATION,"No active selection."))
  orchestrator=AssistantOrchestrator(model,home,frozenset(ids|{"light.porch_1","light.porch_2"}),resolver)
  await orchestrator.handle("What is the status of the porch lights?")
  oversized=await orchestrator.handle("What is the status of the upstairs office?")
  followup=await orchestrator.handle("all of them")
  self.assertIn("21 permitted entities",oversized["message"])
  self.assertEqual(followup["message"],"No active selection.")
  self.assertEqual(home.calls,[])
 async def test_ambiguous_friendly_name_returns_candidates_without_reading(self):
  home=Home(); resolver=EntityReferenceResolver({"light.office","light.office_desk"},{},friendly_names={"Office":("light.office","light.office_desk")})
  proposal=AssistantProposal(AssistantProposalKind.READ_ENTITY_STATE,entity_id="Office")
  result=await AssistantOrchestrator(Model(proposal),home,frozenset({"light.office","light.office_desk"}),resolver).handle("state")
  self.assertEqual(result["status"],"clarification_required");self.assertEqual(result["candidates"],("light.office","light.office_desk"));self.assertEqual(home.calls,[])
 async def test_action_alias_and_unknown_entity_require_clarification(self):
  home=Home(); resolver=EntityReferenceResolver({"light.kitchen"},{"kitchen":"light.kitchen"})
  proposal=AssistantProposal(AssistantProposalKind.HOME_ASSISTANT_ACTION,action={"domain":"light","service":"turn_on","entity_ids":("kitchen",),"service_data":{},"summary":"Turn on"})
  result=await AssistantOrchestrator(Model(proposal),home,resolver=resolver,action_gateway=Gateway()).handle("turn on kitchen")
  self.assertEqual(result["status"],"requires_confirmation")
  unknown=AssistantProposal(AssistantProposalKind.HOME_ASSISTANT_ACTION,action={"domain":"light","service":"turn_on","entity_ids":("other",),"service_data":{},"summary":"Turn on"})
  self.assertEqual((await AssistantOrchestrator(Model(unknown),home,resolver=resolver,action_gateway=Gateway()).handle("turn on other"))["status"],"clarification_required")
