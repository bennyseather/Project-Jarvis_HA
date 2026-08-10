"""Durable, user-controlled vocabulary for goal-based orchestration."""

from __future__ import annotations

from dataclasses import replace

from jarvis.models.contextual_goal import ContextualGoal, GoalInterpretation
from jarvis.models.knowledge import (
    KnowledgeRecordFactory,
    KnowledgeSource,
    KnowledgeType,
)


class ContextualGoalManager:
    TAG = "jarvis:contextual-goal"

    def __init__(self, knowledge_store, compound_orchestration, *, factory=None):
        self._store = knowledge_store
        self._compound = compound_orchestration
        self._factory = factory or KnowledgeRecordFactory()
        self._last_goal_by_conversation: dict[str, str] = {}

    def manage(self, text, conversation_id="local-default"):
        normalized = self._norm(text)
        if normalized in {"show goal", "show goals"}:
            goals = self.goals()
            if len(goals) == 1:
                self._last_goal_by_conversation[conversation_id] = goals[0].goal_id
            return {
                "status": "success",
                "message": (
                    "No contextual goals are configured."
                    if not goals else "Configured goals: " + ", ".join(
                        f"{goal.name} ({goal.goal_id})" for goal in goals
                    ) + "."
                ),
                "items": tuple(goal.__dict__ if hasattr(goal, "__dict__") else {
                    "id": goal.goal_id, "name": goal.name, "command": goal.command
                } for goal in goals),
            }
        if normalized.startswith("teach goal ") and "|" in text:
            name, command = self._parts(text, "teach goal ")
            if self._find(name):
                return {"status": "clarification_required", "message": "That goal already exists; correct it instead."}
            record = self._factory.create(
                KnowledgeType.HOUSEHOLD_PROCEDURE,
                command,
                KnowledgeSource.USER_PROVIDED,
                title=name,
                tags=(self.TAG,),
                metadata={"goal_name": name, "goal_command": command},
            )
            self._store.create(record)
            return {"status": "success", "message": f"I learned the goal '{name}'.", "id": record.knowledge_id}
        if normalized.startswith("correct goal ") and "|" in text:
            name, command = self._parts(text, "correct goal ")
            record = self._find(name)
            if record is None:
                return {"status": "no_match", "message": "Goal not found."}
            self._store.update(replace(
                record,
                content=command,
                metadata={"goal_name": name, "goal_command": command},
            ))
            return {"status": "success", "message": f"I corrected the goal '{name}'."}
        deletion_prefix = next(
            (
                prefix for prefix in (
                    "forget goal ", "delete goal ", "forget ", "delete "
                )
                if normalized.startswith(prefix)
            ),
            None,
        )
        if normalized in {"forget this goal", "delete this goal"}:
            goal_id = self._last_goal_by_conversation.get(conversation_id)
            record = next(
                (item for item in self._records() if item.knowledge_id == goal_id),
                None,
            )
            if record is None:
                return {
                    "status": "clarification_required",
                    "message": "Please name the goal to delete.",
                }
            name = self._goal_name(record)
        elif deletion_prefix is not None:
            name = self._norm(normalized[len(deletion_prefix):])
            record = self._find(name)
            if record is None:
                return None if deletion_prefix in {"forget ", "delete "} else {
                    "status": "no_match", "message": "Goal not found."
                }
        else:
            record = None
        if record is not None:
            self._store.delete(record.knowledge_id)
            self._last_goal_by_conversation.pop(conversation_id, None)
            return {"status": "success", "message": f"I deleted the goal '{name}'."}
        if normalized.startswith("explain goal "):
            name = self._norm(text[len("explain goal "):])
            record = self._find(name)
            if record is None:
                return {"status": "no_match", "message": "Goal not found."}
            return {
                "status": "success",
                "message": f"I understand '{name}' as: {record.content}",
            }
        return None

    async def handle(self, text, conversation_id):
        normalized = self._norm(text)
        matches = [
            record for record in self._records()
            if self._contains(normalized, self._goal_name(record))
        ]
        if not matches:
            return None
        longest = max(len(self._goal_name(record)) for record in matches)
        matches = [
            record for record in matches
            if len(self._goal_name(record)) == longest
        ]
        if len(matches) != 1:
            return {
                "status": "clarification_required",
                "message": "That request matches multiple configured goals. Please name one.",
            }
        record = matches[0]
        self._last_goal_by_conversation[conversation_id] = record.knowledge_id
        goal = ContextualGoal(
            record.knowledge_id,
            self._goal_name(record),
            str(record.metadata.get("goal_command", record.content)),
        )
        interpretation = GoalInterpretation(
            goal,
            ("explicit user-provided goal vocabulary", "current permitted Home Assistant state"),
            (),
            f"I understand '{goal.name}' as: {goal.command}",
        )
        force = any(
            word in goal.name.split()
            for word in ("secure", "security", "bedtime", "lock")
        )
        result = await self._compound.handle(
            goal.command,
            conversation_id,
            allow_single=True,
            state_aware=True,
            force_confirmation=force,
        )
        if result is None:
            return {
                "status": "clarification_required",
                "message": interpretation.explanation + ". Please correct this goal with executable actions.",
            }
        result["interpretation"] = interpretation.explanation
        result["goal_context"] = {
            "goal_id": goal.goal_id,
            "goal_name": goal.name,
            "confidence": goal.confidence,
            "evidence": interpretation.evidence,
            "assumptions": interpretation.assumptions,
        }
        if result.get("status") == "requires_confirmation":
            result["summary"] = interpretation.explanation + ". " + str(result.get("summary", ""))
        return result

    def goals(self):
        return tuple(
            ContextualGoal(
                record.knowledge_id,
                self._goal_name(record),
                str(record.metadata.get("goal_command", record.content)),
            )
            for record in self._records()
        )

    def _records(self):
        return tuple(
            record for record in self._store.list_records()
            if self.TAG in record.tags
        )

    def _find(self, name):
        wanted = self._norm(name)
        return next(
            (record for record in self._records() if self._goal_name(record) == wanted),
            None,
        )

    @staticmethod
    def _goal_name(record):
        return ContextualGoalManager._norm(
            str(record.metadata.get("goal_name", record.title or ""))
        )

    @classmethod
    def _parts(cls, text, prefix):
        remainder = text.strip()[len(prefix):]
        name, command = remainder.split("|", 1)
        return cls._norm(name), command.strip()

    @staticmethod
    def _contains(text, phrase):
        return f" {phrase} " in f" {text} "

    @staticmethod
    def _norm(text):
        return " ".join(str(text).casefold().strip(" .?!").split())
