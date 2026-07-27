"""Safe coordinator for the first end-to-end Jarvis assistant slice."""

from __future__ import annotations

from jarvis.models.assistant_slice import AssistantInput, AssistantProposalKind, HomeAssistantReadProvider, LanguageModelProvider


class AssistantOrchestrator:
    """Accept only conversational and allow-listed read-only proposals."""

    def __init__(self, language_model: LanguageModelProvider, home_assistant: HomeAssistantReadProvider,
                 allowed_entity_ids: frozenset[str] = frozenset(), resolver=None, action_gateway=None) -> None:
        self._language_model, self._home_assistant = language_model, home_assistant
        self._allowed_entity_ids = allowed_entity_ids
        self._resolver = resolver
        self._action_gateway = action_gateway
        self._last_read_targets: tuple[str, ...] = ()
        self._pending_read_targets: tuple[str, ...] = ()
        self._pending_narrow_reference: str | None = None

    def set_action_gateway(self, action_gateway) -> None:
        """Attach the discovered runtime action gateway after Home Assistant connects."""
        self._action_gateway = action_gateway

    async def handle(self, request_text: str, context: dict[str, object] | None = None) -> dict[str, object]:
        deterministic_read = await self._resolve_read_followup(request_text)
        if deterministic_read is not None:
            return deterministic_read
        proposal = self._language_model.propose(AssistantInput(request_text, {} if context is None else context))
        if proposal.kind is AssistantProposalKind.CONVERSATION:
            return {"status": "success", "message": proposal.message}
        if proposal.kind is AssistantProposalKind.HOME_ASSISTANT_ACTION:
            if self._action_gateway is None or not proposal.action:
                return {"status": "not_supported", "message": "Actions are unavailable."}
            from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal
            action_data = dict(proposal.action)
            if self._resolver is not None:
                resolved = []
                for reference in action_data.get("entity_ids", ()):
                    matches = self._resolver.resolve(reference, action_data.get("domain"))
                    if not matches:
                        return {"status": "clarification_required", "message": "Please specify a configured action entity."}
                    if len(matches) > 1 and not self._resolver.is_collective(reference):
                        return self._clarification(matches)
                    resolved.extend(matches)
                action_data["entity_ids"] = tuple(dict.fromkeys(resolved))
            action = HomeAssistantActionProposal(**action_data)
            result = self._action_gateway.request(action)
            if result.get("reason_code") == "unknown_entity":
                return {"status": "clarification_required", "message": "Please specify a configured action entity."}
            if result.get("reason_code") == "unknown_service":
                return {"status": "clarification_required", "message": "Please specify a configured service."}
            if result.get("reason_code") == "too_many_entities":
                return {"status": "clarification_required", "message": "Please specify a group or area with 20 devices or fewer."}
            if result.get("status") == "requires_confirmation":
                result["action_payload"] = dict(action_data)
            if result.get("status") == "immediate_action":
                return await self._action_gateway.execute_immediate(action)
            return result
        if proposal.kind is AssistantProposalKind.READ_ENTITY_STATE:
            if self._resolver is not None:
                matches = self._resolver.resolve(proposal.entity_id or "")
                if not matches:
                    self._clear_read_context()
                    return {"status": "not_supported", "message": "That entity is not available."}
                if len(matches) > 20:
                    if self._resolver.is_collective(proposal.entity_id or ""):
                        self._set_pending_narrowing(proposal.entity_id or "")
                    else:
                        self._clear_read_context()
                    return self._too_many(matches)
                if len(matches) > 1 and not self._resolver.is_collective(proposal.entity_id or ""):
                    self._pending_read_targets = tuple(matches)
                    return self._clarification(matches)
                if len(matches) > 1:
                    self._remember_read_targets(matches)
                    return await self._read_summary(matches)
                proposal = type(proposal)(proposal.kind, proposal.message, matches[0])
            if proposal.entity_id not in self._allowed_entity_ids:
                return {"status": "not_supported", "message": "That entity is not available."}
            try:
                state = await self._home_assistant.read_entity_state(proposal.entity_id)
            except Exception:
                return {"status": "unavailable", "message": "Home Assistant data is unavailable."}
            self._remember_read_targets((state.entity_id,))
            return {"status": "success", "message": f"{self._display_name(state.entity_id)} is {state.state}.", "entity_id": state.entity_id,
                    "state": state.state, "attributes": dict(state.attributes)}
        return {"status": "not_supported", "message": "That request is not supported."}

    async def _resolve_read_followup(self, request_text):
        """Resolve explicit status targets and unambiguous read follow-ups locally."""
        if self._resolver is None:
            return None
        normalized = " ".join(request_text.casefold().split()).strip(" .?!")
        domain = self._resolver.infer_domain(request_text)
        if (
            self._pending_narrow_reference
            and domain is not None
            and not self._looks_like_action(normalized)
        ):
            reference = self._pending_narrow_reference
            targets = self._resolver.resolve(reference, domain)
            if not targets:
                self._clear_read_context()
                return {
                    "status": "not_supported",
                    "message": f"No permitted {domain} entities were found in {reference}.",
                }
            if len(targets) > 20:
                return self._too_many(targets)
            self._remember_read_targets(targets)
            return await self._read_summary(targets)
        if self._pending_read_targets and normalized in {
            "all", "all of them", "both", "both of them", "every one", "everyone",
        }:
            targets = self._pending_read_targets
            if len(targets) > 20:
                self._clear_read_context()
                return self._too_many(targets)
            self._remember_read_targets(targets)
            return await self._read_summary(targets)
        explicit = self._resolver.find_in_text(request_text)
        if explicit is not None:
            reference, targets, collective = explicit
            bare_reference = normalized in {reference, f"the {reference}"}
            if not (self._looks_like_read(normalized) or bare_reference):
                return None
            self._pending_read_targets = ()
            if collective and domain is not None:
                targets = self._resolver.resolve(reference, domain)
                if not targets:
                    self._clear_read_context()
                    return {
                        "status": "not_supported",
                        "message": f"No permitted {domain} entities were found in {reference}.",
                    }
            if len(targets) > 20:
                if collective:
                    self._set_pending_narrowing(reference)
                else:
                    self._clear_read_context()
                return self._too_many(targets)
            if len(targets) > 1 and not collective:
                self._pending_read_targets = tuple(targets)
                return self._clarification(targets)
            self._remember_read_targets(targets)
            if len(targets) > 1:
                return await self._read_summary(targets)
            try:
                state = await self._home_assistant.read_entity_state(targets[0])
            except Exception:
                return {"status": "unavailable", "message": "Home Assistant data is unavailable."}
            return {
                "status": "success",
                "message": f"{self._display_name(state.entity_id)} is {state.state}.",
                "entity_id": state.entity_id,
                "state": state.state,
                "attributes": dict(state.attributes),
            }
        if self._last_read_targets and self._looks_like_read_followup(normalized):
            return await self._read_summary(self._last_read_targets)
        return None

    @staticmethod
    def _looks_like_read(text):
        return (
            "state" in text
            or "status" in text
            or text.startswith(("is ", "are ", "what about "))
        )

    @staticmethod
    def _looks_like_read_followup(text):
        if text in {"all", "all of them", "both", "both of them"}:
            return True
        words = set(text.split())
        return (
            bool(words & {"them", "those", "there", "rest", "all", "both"})
            and (
                text.startswith(("is ", "are ", "what about "))
                or "status" in words
                or "state" in words
            )
        )

    @staticmethod
    def _looks_like_action(text):
        return text.startswith((
            "turn ", "switch ", "set ", "open ", "close ", "lock ", "unlock ",
            "start ", "stop ", "press ",
        ))

    def _remember_read_targets(self, targets):
        self._last_read_targets = tuple(targets)
        self._pending_read_targets = ()
        self._pending_narrow_reference = None

    def _set_pending_narrowing(self, reference):
        self._last_read_targets = ()
        self._pending_read_targets = ()
        self._pending_narrow_reference = reference

    def _clear_read_context(self):
        self._last_read_targets = ()
        self._pending_read_targets = ()
        self._pending_narrow_reference = None

    async def _read_summary(self, entity_ids):
        permitted = tuple(entity_id for entity_id in entity_ids if entity_id in self._allowed_entity_ids)
        if len(permitted) > 20:
            self._clear_read_context()
            return self._too_many(permitted)
        try:
            if hasattr(self._home_assistant, "read_entity_states"):
                states = list(await self._home_assistant.read_entity_states(permitted))
            else:
                states = [await self._home_assistant.read_entity_state(entity_id) for entity_id in permitted]
        except Exception:
            return {"status": "unavailable", "message": "Home Assistant data is unavailable."}
        returned = {state.entity_id for state in states}
        unavailable = [entity_id for entity_id in permitted if entity_id not in returned]
        if not states:
            return {"status": "unavailable", "message": "Home Assistant data is unavailable."}
        counts = {}
        for state in states: counts[state.state] = counts.get(state.state, 0) + 1
        summary = ", ".join(f"{count} {value}" for value, count in sorted(counts.items()))
        details = ", ".join(
            f"{self._display_name(state.entity_id)} is {state.state}"
            for state in states[:5]
        )
        suffix = "" if not unavailable else f"; {len(unavailable)} unavailable"
        return {"status": "success", "message": f"{len(states)} devices: {summary}. {details}{suffix}", "entity_ids": tuple(state.entity_id for state in states)}

    def _clarification(self, matches):
        candidates = ", ".join(self._display_name(entity_id) for entity_id in matches[:5])
        return {
            "status": "clarification_required",
            "message": f"Please specify one of: {candidates}.",
            "candidates": tuple(matches[:5]),
        }

    def _display_name(self, entity_id):
        if self._resolver is None:
            return entity_id
        return self._resolver.display_name(entity_id)

    @staticmethod
    def _too_many(matches):
        return {
            "status": "clarification_required",
            "message": (
                f"That selection contains {len(matches)} permitted entities. "
                "Please narrow it to a group or device type with 20 or fewer."
            ),
        }

    async def confirm_action(self, token: str, action: dict[str, object]) -> dict[str, object]:
        """Execute one exact, previously confirmed action payload."""
        from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal
        if self._action_gateway is None:
            return {"status": "not_supported", "message": "Actions are unavailable."}
        return await self._action_gateway.confirm(token, HomeAssistantActionProposal(**action))
