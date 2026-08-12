"""Deterministic, bounded whole-home situational reasoning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from jarvis.models.event_timeline import TimelineQuery
from jarvis.models.home_assistant_gateway import HomeAssistantActionProposal


@dataclass(frozen=True, slots=True)
class SituationalIntelligencePolicy:
    enabled: bool = True
    maximum_entities: int = 500
    maximum_details: int = 10
    maximum_timeline_results: int = 20
    low_battery_threshold: int = 20

    @classmethod
    def from_config(cls, config):
        value = {} if config is None else config
        if not isinstance(value, dict):
            raise ValueError("situational_intelligence must be a mapping")
        if "enabled" in value and not isinstance(value["enabled"], bool):
            raise ValueError("situational_intelligence.enabled must be a boolean")
        ranges = {
            "maximum_entities": (20, 2000),
            "maximum_details": (1, 20),
            "maximum_timeline_results": (1, 50),
            "low_battery_threshold": (1, 50),
        }
        for name, (minimum, maximum) in ranges.items():
            item = value.get(name, getattr(cls(), name))
            if (
                not isinstance(item, int)
                or isinstance(item, bool)
                or not minimum <= item <= maximum
            ):
                raise ValueError(
                    f"situational_intelligence.{name} must be between "
                    f"{minimum} and {maximum}"
                )
        return cls(
            enabled=value.get("enabled", True),
            maximum_entities=value.get("maximum_entities", 500),
            maximum_details=value.get("maximum_details", 10),
            maximum_timeline_results=value.get("maximum_timeline_results", 20),
            low_battery_threshold=value.get("low_battery_threshold", 20),
        )


@dataclass(slots=True)
class _ConversationScope:
    label: str
    base_ids: tuple[str, ...]
    result_ids: tuple[str, ...]
    noun: str


class WholeHomeSituationalIntelligence:
    """Answer exact aggregate questions and route exact aggregate actions."""

    _DOMAIN_WORDS = {
        "light": "light",
        "lights": "light",
        "lamp": "light",
        "lamps": "light",
        "switch": "switch",
        "switches": "switch",
        "cover": "cover",
        "covers": "cover",
        "blind": "cover",
        "blinds": "cover",
        "camera": "camera",
        "cameras": "camera",
        "fan": "fan",
        "fans": "fan",
        "lock": "lock",
        "locks": "lock",
        "sensor": "sensor",
        "sensors": "sensor",
        "button": "button",
        "buttons": "button",
        "heater": "climate",
        "heaters": "climate",
        "thermostat": "climate",
        "thermostats": "climate",
    }
    _HOME_WORDS = frozenset({
        "device", "devices", "entity", "entities", "battery", "batteries",
        "door", "doors", "window", "windows", "home", "house", "upstairs",
        "downstairs", "room", "rooms", "floor", "area", "group",
        "washer", "washing", "machine", "dryer", "dishwasher", "appliance",
        *_DOMAIN_WORDS,
    })
    _READ_WORDS = frozenset({
        "state", "status", "which", "any", "all", "everything", "unavailable",
        "unknown", "open", "closed", "on", "off", "low", "changed", "changes",
        "recently", "rest", "list", "show", "name", "what",
    })
    _EXTERNAL_TOPIC_WORDS = frozenset({
        "latest", "release", "version", "update", "news", "website", "web",
        "internet",
    })

    def __init__(
        self,
        client,
        assembler,
        timeline_store,
        action_gateway,
        policy: SituationalIntelligencePolicy,
        *,
        clock=None,
    ) -> None:
        self._client = client
        self._assembler = assembler
        self._timeline = timeline_store
        self._gateway = action_gateway
        self.policy = policy
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._scopes: dict[str, _ConversationScope] = {}
        self._failed_actions: dict[str, tuple[str, ...]] = {}

    async def handle(
        self,
        text: str,
        conversation_id: str,
        *,
        voice_mode: bool = False,
        source_id: str | None = None,
    ):
        normalized = self._norm(text)
        scope_key = self._scope_key(conversation_id, source_id)
        if self._asks_failed_device(normalized):
            failed = self._failed_actions.get(scope_key, ())
            if failed:
                return {
                    "status": "success",
                    "message": "Unavailable: " + ", ".join(failed) + ".",
                    "entity_ids": (),
                }
            return {
                "status": "success",
                "message": "No device failed in the most recent action.",
                "entity_ids": (),
            }
        if not self.policy.enabled or not self._looks_relevant(
            normalized, scope_key
        ):
            return None
        try:
            states = await self._client.get_states()
        except Exception:
            return {
                "status": "unavailable",
                "message": "Home Assistant data is unavailable.",
            }
        snapshot = self._assembler.assemble(states, captured_at=self._clock())
        references = self._references(snapshot)
        scope = self._select_scope(
            normalized, snapshot, references, scope_key
        )
        if scope is None:
            return None
        label, base_ids = scope
        entities = snapshot.entity_map()
        selected = [
            entities[entity_id] for entity_id in base_ids if entity_id in entities
        ]
        category = self._category(normalized)
        group_entity_ids = frozenset(
            name for name in snapshot.groups if "." in name
        )
        selected = self._filter_category(
            selected, category, group_entity_ids
        )
        category_ids = tuple(item.entity_id for item in selected)
        noun = self._noun(normalized, len(selected))
        previous = self._scopes.get(scope_key)
        if (
            noun in {"device", "devices"}
            and previous is not None
            and "rest" not in normalized.split()
            and set(normalized.split()) & {"them", "those", "all", "both"}
        ):
            noun = previous.noun

        if self._is_temporal(normalized):
            self._remember(
                scope_key, label, base_ids, category_ids, noun
            )
            return self._temporal_response(
                normalized, label, frozenset(category_ids), entities
            )

        desired_state = self._desired_state(normalized)
        state_filter = (
            self._action_current_state(normalized)
            if self._is_action(normalized)
            else desired_state
        )
        matching = self._filter_state(selected, normalized, state_filter)
        matching_ids = tuple(item.entity_id for item in matching)
        if self._is_action(normalized):
            self._remember(
                scope_key, label, base_ids, matching_ids, noun
            )
            return await self._perform_action(
                normalized, label, matching, scope_key
            )
        self._remember(
            scope_key,
            label,
            base_ids,
            matching_ids or category_ids,
            noun,
        )
        return self._status_response(
            normalized,
            label,
            selected,
            matching,
            desired_state,
            voice_mode,
            noun,
        )

    def context(self, conversation_id: str):
        scope = self._scopes.get(conversation_id)
        if scope is None:
            return {}
        return {
            "scope": scope.label,
            "selected_entity_count": len(scope.result_ids),
        }

    def _looks_relevant(self, text: str, conversation_id: str) -> bool:
        words = set(text.replace(".", " ").split())
        if words & self._EXTERNAL_TOPIC_WORDS:
            return False
        if self._is_action(text):
            return bool(words & self._HOME_WORDS) or conversation_id in self._scopes
        if "what changed" in text or "everything okay" in text:
            return bool(words & self._HOME_WORDS) or conversation_id in self._scopes
        if not (words & self._READ_WORDS):
            return False
        return (
            bool(words & self._HOME_WORDS)
            or "." in text
            or (
                conversation_id in self._scopes
                and bool(words & {"there", "them", "those", "rest", "all", "both"})
            )
        )

    def _select_scope(self, text, snapshot, references, conversation_id):
        whole_home = (
            "whole home" in text
            or "whole house" in text
            or "everything" in text
            or "all devices" in text
        )
        if whole_home:
            return "the home", tuple(item.entity_id for item in snapshot.entities)
        matches = [
            (reference, ids)
            for reference, ids in references.items()
            if self._contains(text, reference)
        ]
        appliance = self._appliance_reference(text, references)
        if appliance is not None:
            return appliance
        if matches:
            reference, ids = max(
                matches,
                key=lambda item: (
                    len(item[0].split()),
                    len(item[0]),
                    item[0],
                ),
            )
            return reference, ids
        previous = self._scopes.get(conversation_id)
        if previous is not None and set(text.split()) & {
            "there", "them", "those", "rest", "all", "both", "back",
        }:
            if "rest" in text:
                remaining = tuple(
                    entity_id for entity_id in previous.base_ids
                    if entity_id not in frozenset(previous.result_ids)
                )
                return previous.label, remaining
            return previous.label, previous.result_ids or previous.base_ids
        if (
            self._category(text) is not None or self._is_temporal(text)
        ) and not self._unresolved_topics(text):
            return "the home", tuple(item.entity_id for item in snapshot.entities)
        return None

    @staticmethod
    def _appliance_reference(text, references):
        phrases = (
            ("washing machine", {"washing", "machine"}),
            ("washer", {"washer"}),
            ("tumble dryer", {"tumble", "dryer"}),
            ("dryer", {"dryer"}),
            ("dishwasher", {"dishwasher"}),
        )
        requested = next((label for label, words in phrases if words <= set(text.split())), None)
        if requested is None:
            return None
        requested_words = set(requested.split())
        ids = {
            entity_id for reference, entity_ids in references.items()
            if requested_words <= set(reference.replace("_", " ").split())
            for entity_id in entity_ids
        }
        return (requested, tuple(sorted(ids))) if ids else None

    @staticmethod
    def _references(snapshot):
        references = {
            **{name: tuple(ids) for name, ids in snapshot.areas.items()},
            **{name: tuple(ids) for name, ids in snapshot.floors.items()},
            **{name: tuple(ids) for name, ids in snapshot.groups.items()},
        }
        for item in snapshot.entities:
            references.setdefault(item.entity_id.casefold(), (item.entity_id,))
            references.setdefault(item.friendly_name.casefold(), (item.entity_id,))
        return references

    def _category(self, text):
        words = set(text.split())
        if words & {"door", "doors"}:
            return ("device_class", frozenset({"door", "opening", "garage_door"}))
        if words & {"window", "windows"}:
            return ("device_class", frozenset({"window", "opening"}))
        if words & {"battery", "batteries"}:
            return ("battery", frozenset())
        for word, domain in self._DOMAIN_WORDS.items():
            if word in words:
                return ("domain", frozenset({domain}))
        return None

    @staticmethod
    def _filter_category(entities, category, group_entity_ids=()):
        if category is None:
            return list(entities)
        kind, values = category
        if kind == "domain":
            candidates = [
                item for item in entities
                if item.domain in values
            ]
            concrete = [
                item for item in candidates
                if item.entity_id.casefold() not in group_entity_ids
                and not isinstance(
                    item.attributes.get("entity_id"), (list, tuple)
                )
                and not WholeHomeSituationalIntelligence._area_aggregate(item)
            ]
            return concrete or candidates
        if kind == "device_class":
            return [
                item for item in entities
                if item.domain == "binary_sensor" and item.device_class in values
            ]
        return [
            item for item in entities
            if item.device_class == "battery"
            or (
                item.domain == "sensor"
                and "battery" in (
                    item.entity_id + " " + item.friendly_name
                ).casefold()
            )
        ]

    @staticmethod
    def _area_aggregate(item):
        if not item.area_name:
            return False
        area = WholeHomeSituationalIntelligence._norm(item.area_name)
        name = WholeHomeSituationalIntelligence._norm(item.friendly_name)
        return name in {f"{area} lights", f"lights {area}"}

    def _filter_state(self, entities, text, desired_state):
        if "low" in text and set(text.split()) & {"battery", "batteries"}:
            return [item for item in entities if self._is_low_battery(item)]
        if "unavailable" in text:
            return [item for item in entities if item.state == "unavailable"]
        if "unknown" in text:
            return [item for item in entities if item.state == "unknown"]
        if desired_state is None:
            if "everything okay" in text:
                return [
                    item for item in entities
                    if item.state in {"unavailable", "unknown"}
                    or self._is_low_battery(item)
                ]
            return list(entities)
        return [
            item for item in entities
            if self._state_matches(item, desired_state)
        ]

    def _is_low_battery(self, item):
        if not (
            item.device_class == "battery"
            or "battery" in (item.entity_id + " " + item.friendly_name).casefold()
        ):
            return False
        try:
            return float(item.state) <= self.policy.low_battery_threshold
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _state_matches(item, desired):
        if desired == "open":
            return item.state in {"on", "open", "opening"}
        if desired == "closed":
            return item.state in {"off", "closed", "closing"}
        return item.state == desired

    @staticmethod
    def _desired_state(text):
        words = set(text.split())
        if "unavailable" in words:
            return "unavailable"
        if "unknown" in words:
            return "unknown"
        for value in ("closed", "open", "off", "on"):
            if value in words:
                return value
        return None

    @staticmethod
    def _action_current_state(text):
        if "still on" in text or "that are on" in text:
            return "on"
        if "still off" in text or "that are off" in text:
            return "off"
        if "still open" in text or "that are open" in text:
            return "open"
        if "still closed" in text or "that are closed" in text:
            return "closed"
        return None

    def _status_response(
        self, text, label, selected, matching, desired_state, voice_mode, noun
    ):
        if "everything okay" in text:
            if not matching:
                return {
                    "status": "success",
                    "message": (
                        "I found no unavailable, unknown, or low-battery "
                        "permitted devices."
                    ),
                    "entity_ids": (),
                }
            return self._summary(
                matching,
                f"I found {len(matching)} items needing attention",
                voice_mode,
            )
        asks_all = "all" in text.split() or "every" in text.split()
        asks_any = "any" in text.split()
        if desired_state is not None and (asks_all or asks_any):
            if asks_all:
                success = bool(selected) and len(matching) == len(selected)
                if success:
                    message = (
                        f"Yes. All {len(selected)} {noun} in {label} are "
                        f"{desired_state}."
                    )
                else:
                    exceptions = [
                        item for item in selected if item not in matching
                    ]
                    message = (
                        f"No. {len(matching)} of {len(selected)} {noun} in "
                        f"{label} are {desired_state}."
                    )
                    if exceptions:
                        message += " " + self._details(exceptions)
                return {
                    "status": "success",
                    "message": message,
                    "entity_ids": tuple(item.entity_id for item in matching),
                }
            if matching:
                return self._summary(
                    matching,
                    f"Yes. {len(matching)} {noun} in {label} are {desired_state}",
                    voice_mode,
                )
            return {
                "status": "success",
                "message": f"No permitted {noun} in {label} are {desired_state}.",
                "entity_ids": (),
            }
        if not matching:
            qualifier = (
                f" that are {desired_state}" if desired_state is not None else ""
            )
            return {
                "status": "success",
                "message": f"No permitted {noun} in {label}{qualifier} were found.",
                "entity_ids": (),
            }
        if (
            desired_state is None
            and len(matching) > self.policy.maximum_details
            and not self._asks_listing(text)
        ):
            domains: dict[str, int] = {}
            for item in matching:
                domains[item.domain] = domains.get(item.domain, 0) + 1
            domain_summary = ", ".join(
                f"{count} {self._domain_label(domain, count)}"
                for domain, count in sorted(domains.items())
            )
            unavailable = [
                item for item in matching
                if item.state in {"unavailable", "unknown"}
            ]
            message = (
                f"{len(matching)} devices in {label}: {domain_summary}. "
                f"{sum(item.state == 'unavailable' for item in matching)} "
                "unavailable, "
                f"{sum(item.state == 'unknown' for item in matching)} unknown."
            )
            if unavailable:
                message += " " + self._details(unavailable)
            return {
                "status": "success",
                "message": message,
                "entity_ids": tuple(item.entity_id for item in matching),
            }
        counts: dict[str, int] = {}
        for item in matching:
            counts[item.state] = counts.get(item.state, 0) + 1
        count_text = ", ".join(
            f"{count} {state}" for state, count in sorted(counts.items())
        )
        lead = f"{len(matching)} {noun} in {label}: {count_text}"
        return self._summary(matching, lead, voice_mode)

    def _summary(self, entities, lead, voice_mode):
        detail_limit = min(5, self.policy.maximum_details) if voice_mode else self.policy.maximum_details
        details = self._details(entities[:detail_limit])
        omitted = len(entities) - detail_limit
        suffix = f" {omitted} more are omitted." if omitted > 0 else ""
        return {
            "status": "success",
            "message": f"{lead}. {details}{suffix}".strip(),
            "entity_ids": tuple(item.entity_id for item in entities),
        }

    @staticmethod
    def _asks_listing(text):
        words = set(text.split())
        return bool(words & {"list", "show", "name", "which"}) or (
            "what" in words and not words & {"state", "status"}
        )

    def _details(self, entities):
        values = []
        for item in entities[: self.policy.maximum_details]:
            state = item.state
            if self._is_low_battery(item):
                state = f"{state}%"
            values.append(f"{item.friendly_name} is {state}")
        return ", ".join(values) + ("." if values else "")

    def _temporal_response(self, text, label, target_ids, entities):
        candidates = []
        for entity_id in sorted(target_ids):
            candidates.extend(self._timeline.retrieve(TimelineQuery(
                entity_id=entity_id,
                maximum_results=self.policy.maximum_timeline_results,
            )))
        candidates.sort(
            key=lambda event: (event.occurred_at, event.event_id),
            reverse=True,
        )
        relevant = []
        seen = set()
        for event in candidates:
            identity = (event.entity_id, event.state)
            if identity in seen:
                continue
            seen.add(identity)
            relevant.append(event)
            if len(relevant) >= self.policy.maximum_timeline_results:
                break
        if not relevant:
            return {
                "status": "success",
                "message": (
                    f"No permitted changes for {label} are available in the "
                    "recent bounded timeline."
                ),
                "entity_ids": (),
            }
        details = []
        for event in relevant[: self.policy.maximum_details]:
            item = entities.get(event.entity_id)
            name = item.friendly_name if item is not None else event.entity_id
            state = "changed" if event.state is None else f"changed to {event.state}"
            details.append(f"{name} {state}")
        return {
            "status": "success",
            "message": (
                f"{len(relevant)} recent changes in {label}: "
                + "; ".join(details)
                + "."
            ),
            "entity_ids": tuple(event.entity_id for event in relevant),
        }

    async def _perform_action(self, text, label, entities, conversation_id):
        action = self._action_definition(text, entities)
        if action is None:
            return {
                "status": "clarification_required",
                "message": "Please specify one device type and action.",
            }
        domain, service = action
        targets = tuple(
            item.entity_id for item in entities
            if item.domain == domain and item.action_allowed
        )
        if not targets:
            return {
                "status": "not_supported",
                "message": "No authorized matching devices were found.",
            }
        if len(targets) > 20:
            return {
                "status": "clarification_required",
                "message": (
                    f"That action matches {len(targets)} devices. "
                    "Please narrow it to 20 or fewer."
                ),
            }
        proposal = HomeAssistantActionProposal(
            domain=domain,
            service=service,
            entity_ids=targets,
            service_data={},
            summary=f"{service.replace('_', ' ').title()} {len(targets)} devices in {label}",
        )
        result = self._gateway.request(proposal)
        if result.get("status") == "immediate_action":
            outcome = await self._gateway.execute_immediate(proposal)
            names = {item.entity_id: item.friendly_name for item in entities}
            failed_names = tuple(
                names.get(entity_id, entity_id)
                for entity_id in outcome.get("failed", ())
            )
            self._failed_actions[conversation_id] = failed_names
            if failed_names:
                outcome["message"] = (
                    outcome.get("message", "Action partially completed.").rstrip()
                    + " Unavailable: "
                    + ", ".join(failed_names)
                    + "."
                )
            resulting_state = self._resulting_state(service)
            if outcome.get("status") == "success" and resulting_state is not None:
                now = self._clock()
                for entity_id in outcome.get("succeeded", targets):
                    self._timeline.append(
                        "state_changed", entity_id, now, resulting_state
                    )
            return outcome
        if result.get("status") == "requires_confirmation":
            result["action_payload"] = {
                "domain": domain,
                "service": service,
                "entity_ids": targets,
                "service_data": {},
                "summary": proposal.summary,
            }
        return result

    @staticmethod
    def _action_definition(text, entities):
        domains = {item.domain for item in entities}
        if (
            text.startswith(("turn off ", "switch off ", "turn back off"))
            or (text.startswith("turn ") and text.endswith(" off"))
        ):
            candidates = domains & {"light", "switch", "fan", "media_player"}
            return (next(iter(candidates)), "turn_off") if len(candidates) == 1 else None
        if (
            text.startswith(("turn on ", "switch on ", "turn back on"))
            or (text.startswith("turn ") and text.endswith(" on"))
        ):
            candidates = domains & {"light", "switch", "fan", "media_player"}
            return (next(iter(candidates)), "turn_on") if len(candidates) == 1 else None
        if text.startswith(("open ", "raise ")):
            return ("cover", "open_cover") if "cover" in domains else None
        if text.startswith(("close ", "shut ", "lower ")):
            return ("cover", "close_cover") if "cover" in domains else None
        if text.startswith("lock "):
            return ("lock", "lock") if "lock" in domains else None
        if text.startswith("unlock "):
            return ("lock", "unlock") if "lock" in domains else None
        if text.startswith("press "):
            return ("button", "press") if "button" in domains else None
        return None

    @staticmethod
    def _is_action(text):
        return (
            text.startswith((
            "turn on ", "turn off ", "switch on ", "switch off ", "open ",
            "close ", "shut ", "raise ", "lower ", "lock ", "unlock ", "press ",
            "turn back on", "turn back off",
            ))
            or (
                text.startswith("turn ")
                and text.endswith((" on", " off"))
            )
        )

    @staticmethod
    def _scope_key(conversation_id, source_id):
        if isinstance(source_id, str) and source_id.strip():
            return "source:" + source_id.strip()[:200]
        return conversation_id

    @staticmethod
    def _asks_failed_device(text):
        return (
            "which device was unavailable" in text
            or "which devices were unavailable" in text
            or "what device was unavailable" in text
        )

    @staticmethod
    def _resulting_state(service):
        return {
            "turn_on": "on",
            "turn_off": "off",
            "open_cover": "open",
            "close_cover": "closed",
            "lock": "locked",
            "unlock": "unlocked",
        }.get(service)

    @staticmethod
    def _is_temporal(text):
        return (
            "what changed" in text
            or "recent changes" in text
            or ("changed" in text and "recently" in text)
        )

    def _remember(self, conversation_id, label, base_ids, result_ids, noun):
        self._scopes[conversation_id] = _ConversationScope(
            label, tuple(base_ids), tuple(result_ids), noun
        )

    @staticmethod
    def _noun(text, count):
        words = set(text.split())
        for singular, plural in (
            ("light", "lights"), ("switch", "switches"), ("cover", "covers"),
            ("blind", "blinds"), ("camera", "cameras"), ("fan", "fans"),
            ("lock", "locks"), ("sensor", "sensors"), ("button", "buttons"),
            ("door", "doors"), ("window", "windows"),
            ("battery", "batteries"),
        ):
            if singular in words or plural in words:
                return singular if count == 1 else plural
        return "device" if count == 1 else "devices"

    @staticmethod
    def _domain_label(domain, count):
        labels = {
            "binary_sensor": ("binary sensor", "binary sensors"),
            "media_player": ("media player", "media players"),
        }
        singular, plural = labels.get(
            domain, (domain.replace("_", " "), domain.replace("_", " ") + "s")
        )
        return singular if count == 1 else plural

    @staticmethod
    def _norm(value):
        return " ".join(
            str(value).casefold().replace("?", " ").replace(",", " ").split()
        )

    @staticmethod
    def _contains(text, reference):
        return f" {reference} " in f" {text} "

    def _unresolved_topics(self, text):
        ignored = {
            "what", "which", "is", "are", "was", "were", "the", "a", "an",
            "of", "in", "at", "my", "our", "all", "any", "every", "everything",
            "state", "status", "device", "devices", "entity", "entities",
            "on", "off", "open", "closed", "unavailable", "unknown", "low",
            "still", "that", "there", "them", "those", "rest", "both", "and",
            "recently", "changed", "changes", "change", "since", "home", "house",
            "whole", "turn", "switch", "close", "shut", "raise", "lower",
            "lock", "unlock", "press", "to", "for", "belonging", "okay",
            *self._DOMAIN_WORDS,
            "battery", "batteries", "door", "doors", "window", "windows",
        }
        return bool(set(text.replace(".", " ").split()) - ignored)
