"""Deterministic, bounded multi-action orchestration for Home Assistant."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from jarvis.models.compound_orchestration import (
    CompoundCondition,
    CompoundPlan,
    CompoundPlanStep,
    CompoundStepOutcome,
    CompoundStepStatus,
)
from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal


@dataclass(frozen=True, slots=True)
class CompoundOrchestrationPolicy:
    enabled: bool = True
    maximum_actions: int = 10
    confirmation_ttl_seconds: int = 60

    @classmethod
    def from_config(cls, value):
        value = {} if value is None else value
        if not isinstance(value, dict):
            raise ValueError("compound_orchestration must be a mapping")
        if "enabled" in value and not isinstance(value["enabled"], bool):
            raise ValueError("compound_orchestration.enabled must be a boolean")
        maximum = value.get("maximum_actions", 10)
        if not isinstance(maximum, int) or isinstance(maximum, bool) or not 2 <= maximum <= 10:
            raise ValueError("compound_orchestration.maximum_actions must be between 2 and 10")
        ttl = value.get("confirmation_ttl_seconds", 60)
        if not isinstance(ttl, int) or isinstance(ttl, bool) or not 30 <= ttl <= 300:
            raise ValueError(
                "compound_orchestration.confirmation_ttl_seconds must be between 30 and 300"
            )
        return cls(value.get("enabled", True), maximum, ttl)


@dataclass(slots=True)
class _PendingPlan:
    plan: CompoundPlan
    confirmation_tokens: dict[str, str]
    expires_at: datetime


class CompoundHomeOrchestrator:
    """Build and execute validated compound plans without persistent automation."""

    _ACTION_START = re.compile(
        r"^(turn on|turn off|switch on|switch off|open|close|shut|raise|lower|"
        r"lock|unlock|press|start|stop|pause|activate)\b"
    )
    _ACTION_BOUNDARY = re.compile(
        r"\s+and\s+(?=(?:turn on|turn off|switch on|switch off|open|close|shut|"
        r"raise|lower|lock|unlock|press|start|stop|pause|activate)\b)"
    )
    _DOMAIN_WORDS = {
        "light": "light", "lights": "light", "lamp": "light", "lamps": "light",
        "switch": "switch", "switches": "switch", "fan": "fan", "fans": "fan",
        "blind": "cover", "blinds": "cover", "cover": "cover", "covers": "cover",
        "lock": "lock", "locks": "lock", "vacuum": "vacuum", "mower": "lawn_mower",
        "scene": "scene", "script": "script", "speaker": "media_player",
        "speakers": "media_player", "media": "media_player",
    }

    def __init__(self, client, assembler, gateway, policy, *, clock=None):
        self._client = client
        self._assembler = assembler
        self._gateway = gateway
        self.policy = policy
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._pending: dict[str, _PendingPlan] = {}
        self._latest_by_conversation: dict[str, str] = {}

    async def handle(
        self, text: str, conversation_id: str, *,
        allow_single: bool = False, state_aware: bool = False,
        force_confirmation: bool = False,
    ):
        if not self.policy.enabled or not (
            self._looks_compound(text)
            or (allow_single and self._ACTION_START.match(self._norm(text)))
        ):
            return None
        try:
            states = await self._client.get_states()
        except Exception:
            return {"status": "unavailable", "message": "Home Assistant data is unavailable."}
        snapshot = self._assembler.assemble(states, captured_at=self._clock())
        built = self._build_plan(
            text, conversation_id, snapshot,
            allow_single=allow_single, state_aware=state_aware,
        )
        if isinstance(built, dict):
            return built
        plan = built
        previous = self._latest_by_conversation.pop(conversation_id, None)
        if previous is not None:
            self._pending.pop(previous, None)
        decisions: dict[str, dict[str, object]] = {}
        confirmation_tokens: dict[str, str] = {}
        highest_risk = "confirm_required"
        risk_rank = {
            "confirm_required": 1,
            "high_impact_confirm_required": 2,
        }
        for step in plan.steps:
            decision = self._gateway.request(step.proposal)
            decisions[step.step_id] = decision
            status = decision.get("status")
            if status == "forbidden":
                return {
                    "status": "forbidden",
                    "message": (
                        f"I cannot authorize {self._step_label(step)} "
                        f"({decision.get('reason_code', 'policy denied')})."
                    ),
                }
            if status == "requires_confirmation":
                confirmation_tokens[step.step_id] = str(decision["token"])
                candidate = str(decision.get("risk", "confirm_required"))
                if risk_rank.get(candidate, 1) > risk_rank.get(highest_risk, 1):
                    highest_risk = candidate
        if confirmation_tokens or force_confirmation:
            token = token_urlsafe(24)
            self._pending[token] = _PendingPlan(
                plan,
                confirmation_tokens,
                self._clock() + timedelta(seconds=self.policy.confirmation_ttl_seconds),
            )
            self._latest_by_conversation[conversation_id] = token
            return {
                "status": "requires_confirmation",
                "token": token,
                "summary": plan.summary,
                "risk": (
                    highest_risk if confirmation_tokens
                    else "goal_confirmation_required"
                ),
                "action_payload": {"kind": "compound_plan", "conversation_id": conversation_id},
            }
        return await self._execute(plan, decisions)

    async def confirm(self, token: str, payload: dict[str, object]):
        pending = self._pending.pop(token, None)
        if (
            pending is None
            or pending.expires_at < self._clock()
            or payload.get("kind") != "compound_plan"
            or payload.get("conversation_id") != pending.plan.conversation_id
        ):
            return {"status": "forbidden", "message": "Confirmation is invalid or expired."}
        self._latest_by_conversation.pop(pending.plan.conversation_id, None)
        decisions = {
            step.step_id: (
                {"status": "requires_confirmation", "token": pending.confirmation_tokens[step.step_id]}
                if step.step_id in pending.confirmation_tokens
                else {"status": "immediate_action"}
            )
            for step in pending.plan.steps
        }
        return await self._execute(pending.plan, decisions)

    def cancel(self, token: str) -> None:
        pending = self._pending.pop(token, None)
        if pending is not None:
            self._latest_by_conversation.pop(pending.plan.conversation_id, None)

    def _build_plan(
        self, text, conversation_id, snapshot, *,
        allow_single=False, state_aware=False,
    ):
        normalized = self._norm(text)
        condition_text = None
        if normalized.startswith("if "):
            pieces = normalized.split(",", 1)
            if len(pieces) != 2:
                return {
                    "status": "clarification_required",
                    "message": "Put the condition before a comma, followed by the actions.",
                }
            condition_text, normalized = pieces[0][3:].strip(), pieces[1].strip()
        clauses = self._split_actions(normalized)
        if len(clauses) < (1 if condition_text is not None or allow_single else 2):
            return None
        references = self._references(snapshot)
        entities = snapshot.entity_map()
        condition = self._resolve_condition(condition_text, references, entities)
        if condition_text and condition is None:
            return {
                "status": "clarification_required",
                "message": "Please specify one permitted entity and state for the condition.",
            }
        steps = []
        total_targets = 0
        for index, (clause, sequence) in enumerate(clauses, 1):
            resolved = self._resolve_action(
                clause, references, entities, state_aware=state_aware
            )
            if isinstance(resolved, dict):
                return resolved
            if resolved is None:
                continue
            proposal, names = resolved
            total_targets += len(proposal.entity_ids)
            if total_targets > self.policy.maximum_actions:
                return {
                    "status": "clarification_required",
                    "message": (
                        f"That plan resolves to {total_targets} actions. "
                        f"Please narrow it to {self.policy.maximum_actions} or fewer."
                    ),
                }
            steps.append(CompoundPlanStep(
                step_id=f"step-{index}",
                sequence=sequence,
                proposal=proposal,
                friendly_names=names,
                condition=condition,
            ))
        if not steps:
            return {
                "status": "success",
                "message": "That goal is already satisfied by the current Home Assistant state.",
                "succeeded_steps": (),
                "skipped_steps": (),
                "failed_steps": (),
            }
        summary = "; then ".join(
            self._step_label(step)
            for step in steps
        )
        if condition is not None:
            expected = "/".join(sorted(condition.expected_states))
            summary = f"If {condition.friendly_name} is {expected}: {summary}"
        return CompoundPlan(conversation_id, tuple(steps), summary)

    def _resolve_action(
        self, clause, references, entities, *, state_aware=False
    ):
        exclusion_text = None
        if " except " in clause:
            clause, exclusion_text = clause.split(" except ", 1)
        target_ids = self._match_reference(clause, references)
        if target_ids is None:
            target_ids = tuple(
                item.entity_id for item in entities.values()
                if self._contains(clause, item.friendly_name.casefold())
                or item.entity_id.casefold() in clause
            )
        resolved_domains = {
            entities[entity_id].domain for entity_id in (target_ids or ())
            if entity_id in entities
        }
        action = self._service_for(clause, resolved_domains)
        if action is None:
            return {
                "status": "clarification_required",
                "message": f"Please clarify this action: {clause}.",
            }
        domain, service = action
        targets = [
            entities[entity_id] for entity_id in (target_ids or ())
            if entity_id in entities
            and entities[entity_id].domain == domain
            and entities[entity_id].action_allowed
        ]
        if exclusion_text:
            excluded = set(self._match_reference(exclusion_text, references) or ())
            targets = [item for item in targets if item.entity_id not in excluded]
        if state_aware:
            desired = {
                "turn_on": {"on"},
                "turn_off": {"off"},
                "open_cover": {"open", "opening"},
                "close_cover": {"closed", "closing"},
                "lock": {"locked"},
                "unlock": {"unlocked"},
            }.get(service)
            if desired is not None:
                targets = [item for item in targets if item.state not in desired]
                if not targets:
                    return None
        if not targets:
            return {
                "status": "clarification_required",
                "message": f"No authorized {domain.replace('_', ' ')} target was resolved for: {clause}.",
            }
        ids = tuple(dict.fromkeys(item.entity_id for item in targets))
        names = tuple(item.friendly_name for item in targets)
        proposal = HomeAssistantActionProposal(
            domain, service, ids, {},
            f"{service.replace('_', ' ').title()} {', '.join(names)}",
        )
        return proposal, names

    def _resolve_condition(self, text, references, entities):
        if text is None:
            return None
        desired = next(
            (state for state in ("unlocked", "locked", "closed", "open", "off", "on")
             if state in text.split()),
            None,
        )
        target_ids = self._match_reference(text, references)
        if desired is None or target_ids is None or len(target_ids) != 1:
            return None
        entity = entities.get(target_ids[0])
        if entity is None:
            return None
        expected = {
            "closed": frozenset({"closed", "off"}),
            "open": frozenset({"open", "on"}),
        }.get(desired, frozenset({desired}))
        return CompoundCondition(entity.entity_id, entity.friendly_name, expected)

    async def _execute(self, plan, decisions):
        outcomes: list[CompoundStepOutcome] = []
        for sequence in sorted({step.sequence for step in plan.steps}):
            group = [step for step in plan.steps if step.sequence == sequence]
            current = await self._current_states()
            runnable = []
            for step in group:
                condition = step.condition
                if condition is not None and current.get(condition.entity_id) not in condition.expected_states:
                    outcomes.append(CompoundStepOutcome(
                        step.step_id, CompoundStepStatus.SKIPPED,
                        f"Skipped {self._step_label(step)} because "
                        f"{condition.friendly_name} is {current.get(condition.entity_id, 'unknown')}.",
                        step.proposal.entity_ids,
                    ))
                else:
                    runnable.append(step)
            results = await asyncio.gather(
                *(self._execute_step(step, decisions[step.step_id]) for step in runnable),
                return_exceptions=True,
            )
            for step, result in zip(runnable, results):
                if isinstance(result, Exception):
                    outcomes.append(CompoundStepOutcome(
                        step.step_id, CompoundStepStatus.FAILED,
                        f"Failed: {self._step_label(step)}.", step.proposal.entity_ids,
                    ))
                else:
                    outcomes.append(result)
        succeeded = [item for item in outcomes if item.status is CompoundStepStatus.SUCCEEDED]
        skipped = [item for item in outcomes if item.status is CompoundStepStatus.SKIPPED]
        failed = [item for item in outcomes if item.status is CompoundStepStatus.FAILED]
        details = " ".join(item.message for item in outcomes)
        status = "success" if succeeded and not failed else ("unavailable" if failed else "success")
        return {
            "status": status,
            "message": (
                f"Compound plan complete: {len(succeeded)} succeeded, "
                f"{len(skipped)} skipped, {len(failed)} failed. {details}"
            ),
            "succeeded_steps": tuple(item.step_id for item in succeeded),
            "skipped_steps": tuple(item.step_id for item in skipped),
            "failed_steps": tuple(item.step_id for item in failed),
        }

    async def _execute_step(self, step, decision):
        if decision.get("status") == "requires_confirmation":
            result = await self._gateway.confirm(str(decision["token"]), step.proposal)
        else:
            result = await self._gateway.execute_immediate(step.proposal)
        failed_entities = tuple(result.get("failed", ()))
        succeeded_entities = tuple(result.get("succeeded", ()))
        succeeded = result.get("status") == "success" and not failed_entities
        if failed_entities and succeeded_entities:
            message = (
                f"Partially completed {self._step_label(step)}: "
                f"{len(succeeded_entities)} succeeded and "
                f"{len(failed_entities)} failed."
            )
        elif succeeded:
            message = f"Succeeded: {self._step_label(step)}."
        else:
            message = f"Failed: {self._step_label(step)}."
        return CompoundStepOutcome(
            step.step_id,
            CompoundStepStatus.SUCCEEDED if succeeded else CompoundStepStatus.FAILED,
            message,
            failed_entities or step.proposal.entity_ids,
        )

    async def _current_states(self):
        try:
            states = await self._client.get_states()
        except Exception:
            return {}
        return {
            item.get("entity_id"): str(item.get("state", "unknown")).casefold()
            for item in states if isinstance(item, dict)
        }

    @classmethod
    def _looks_compound(cls, text):
        normalized = cls._norm(text)
        if normalized.startswith("if "):
            return True
        clauses = cls._split_actions(normalized)
        return len(clauses) >= 2 and all(
            cls._ACTION_START.match(clause) for clause, _ in clauses
        )

    @classmethod
    def _split_actions(cls, text):
        text = re.sub(r",\s*then\s+", " then ", text)
        text = re.sub(
            r",\s*(?=(?:turn on|turn off|switch on|switch off|open|close|shut|"
            r"raise|lower|lock|unlock|press|start|stop|pause|activate)\b)",
            " and ",
            text,
        )
        parts = []
        sequence = 0
        for sequential in re.split(r"\s+then\s+", text):
            for parallel in cls._ACTION_BOUNDARY.split(sequential):
                item = parallel.strip(" ,")
                if item:
                    parts.append((item, sequence))
            sequence += 1
        return parts

    @classmethod
    def _service_for(cls, text, resolved_domains=()):
        domain = next(
            (domain for word, domain in cls._DOMAIN_WORDS.items() if word in text.split()),
            None,
        )
        if domain is None and len(resolved_domains) == 1:
            domain = next(iter(resolved_domains))
        if text.startswith(("turn off ", "switch off ")):
            candidates = set(resolved_domains) & {"light", "switch", "fan", "media_player"}
            if domain is None and len(candidates) == 1:
                domain = next(iter(candidates))
            return (domain, "turn_off") if domain in {"light", "switch", "fan", "media_player"} else None
        if text.startswith(("turn on ", "switch on ")):
            candidates = set(resolved_domains) & {
                "light", "switch", "fan", "media_player", "scene", "script"
            }
            if domain is None and len(candidates) == 1:
                domain = next(iter(candidates))
            return (domain, "turn_on") if domain in {
                "light", "switch", "fan", "media_player", "scene", "script"
            } else None
        if text.startswith(("open ", "raise ")):
            return ("cover", "open_cover")
        if text.startswith(("close ", "shut ", "lower ")):
            return ("cover", "close_cover")
        if text.startswith("lock "):
            return ("lock", "lock")
        if text.startswith("unlock "):
            return ("lock", "unlock")
        if text.startswith("press "):
            return ("button", "press")
        if text.startswith("activate "):
            return (domain, "turn_on") if domain in {"scene", "script"} else None
        if text.startswith("start "):
            return (
                (domain, "start_mowing" if domain == "lawn_mower" else "start")
                if domain in {"vacuum", "lawn_mower"} else None
            )
        if text.startswith(("stop ", "pause ")):
            service = (
                "pause"
                if text.startswith("pause ")
                else ("dock" if domain == "lawn_mower" else "return_to_base")
            )
            return (domain, service) if domain in {"vacuum", "lawn_mower"} else None
        return None

    @staticmethod
    def _references(snapshot):
        references = {
            **{name.casefold(): tuple(ids) for name, ids in snapshot.areas.items()},
            **{name.casefold(): tuple(ids) for name, ids in snapshot.floors.items()},
            **{name.casefold(): tuple(ids) for name, ids in snapshot.groups.items()},
        }
        for item in snapshot.entities:
            references[item.entity_id.casefold()] = (item.entity_id,)
            references[item.friendly_name.casefold()] = (item.entity_id,)
        all_ids = tuple(item.entity_id for item in snapshot.entities)
        references.update({
            "everything": all_ids,
            "whole home": all_ids,
            "whole house": all_ids,
            "home": all_ids,
            "house": all_ids,
        })
        return references

    @classmethod
    def _match_reference(cls, text, references):
        matches = [
            (reference, ids) for reference, ids in references.items()
            if cls._contains(text, reference)
        ]
        return max(matches, key=lambda item: (len(item[0].split()), len(item[0])))[1] if matches else None

    @staticmethod
    def _contains(text, reference):
        return re.search(rf"(?<!\w){re.escape(reference)}(?!\w)", text) is not None

    @staticmethod
    def _norm(text):
        return " ".join(str(text).casefold().strip(" .?!").split())

    @staticmethod
    def _step_label(step):
        return (
            f"{step.proposal.service.replace('_', ' ')} "
            f"{', '.join(step.friendly_names)}"
        )
