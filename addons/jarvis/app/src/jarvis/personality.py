"""Inspectable, safety-subordinate personality preferences."""

from __future__ import annotations

from dataclasses import dataclass, replace

from jarvis.models.knowledge import KnowledgeRecordFactory, KnowledgeSource, KnowledgeType


@dataclass(frozen=True, slots=True)
class PersonalityProfile:
    address: str = ""
    humour: str = "subtle"
    warmth: str = "balanced"
    formality: str = "refined"
    verbosity: str = "concise"
    locale: str = "en-GB"
    voice: str = "original British synthetic"

    def context(self):
        return {
            "address": self.address, "humour": self.humour,
            "warmth": self.warmth, "formality": self.formality,
            "verbosity": self.verbosity,
            "locale": self.locale, "voice": self.voice,
            "presentation": (
                "Use the preferred address sparingly and only when socially natural. "
                "Vary acknowledgements; avoid catchphrases and repeated openings. "
                "Carry clear subjects across the bounded dialogue and honour explicit "
                "corrections without pretending certainty when the referent is ambiguous. "
                "Spoken answers must be shorter than text answers and must not read source URLs. Offer at most one "
                "next step, and only when it is materially useful."
            ),
            "safety": (
                "No humour for failures, safety, confirmations, emergencies, "
                "or sensitive topics. Never claim consciousness or imitate a "
                "fictional character or actor."
            ),
        }


class PersonalityManager:
    TAG = "jarvis:personality-profile"
    OPTIONS = {
        "humour": {"off", "subtle", "moderate"},
        "warmth": {"reserved", "balanced", "warm"},
        "formality": {"relaxed", "refined"},
        "verbosity": {"concise", "balanced", "detailed"},
    }

    def __init__(self, store, *, factory=None):
        self._store = store
        self._factory = factory or KnowledgeRecordFactory()
        self._last_style: dict[str, str] = {}

    def profile(self):
        record = self._record()
        if record is None:
            return PersonalityProfile()
        values = record.metadata
        return PersonalityProfile(
            str(values.get("address", "")),
            str(values.get("humour", "subtle")),
            str(values.get("warmth", "balanced")),
            str(values.get("formality", "refined")),
            str(values.get("verbosity", "concise")),
        )

    def handle(self, text, conversation_id="local-default"):
        normalized = " ".join(text.casefold().strip(" .?!").split())
        if normalized in {"show personality", "explain personality"}:
            profile = self.profile()
            return {"status": "success", "message": (
                f"Personality: {profile.formality}, {profile.warmth}, "
                f"{profile.verbosity}, "
                f"humour {profile.humour}, British English, original subtly "
                f"synthetic voice. Address: {profile.address or 'not set'}."
            )}
        if normalized == "show relationship preferences":
            profile = self.profile()
            return {"status": "success", "message": (
                f"Relationship preferences: address "
                f"{profile.address or 'not set'}, warmth {profile.warmth}. "
                "Only explicitly supplied preferences and approved household "
                "knowledge are used."
            )}
        if normalized == "explain last response style":
            explanation = self._last_style.get(
                conversation_id,
                "No adaptive response style has been applied in this conversation yet.",
            )
            return {"status": "success", "message": explanation}
        if normalized.startswith("address me as "):
            address = text.strip()[len("address me as "):].strip()
            if (
                not address
                or len(address) > 60
                or any(character in address for character in "\r\n{}[]<>")
            ):
                return {
                    "status": "clarification_required",
                    "message": "Please provide a short name or title on one line.",
                }
            return self._save(replace(
                self.profile(), address=address
            ), "Address preference updated.")
        if normalized.startswith("set personality "):
            parts = normalized.split()
            if len(parts) != 4 or parts[2] not in self.OPTIONS or parts[3] not in self.OPTIONS[parts[2]]:
                return {"status": "clarification_required", "message": (
                    "Use: set personality humour off|subtle|moderate, warmth "
                    "reserved|balanced|warm, formality relaxed|refined, or "
                    "verbosity concise|balanced|detailed."
                )}
            return self._save(
                replace(self.profile(), **{parts[2]: parts[3]}),
                f"Personality {parts[2]} updated.",
            )
        if normalized in {"reset personality", "forget personality preferences"}:
            record = self._record()
            if record is not None:
                self._store.delete(record.knowledge_id)
            return {"status": "success", "message": "Personality preferences reset."}
        if normalized == "forget relationship preferences":
            if self._record() is None:
                return {
                    "status": "success",
                    "message": "No relationship preferences were stored.",
                }
            profile = self.profile()
            return self._save(
                replace(profile, address="", warmth="balanced"),
                "Relationship preferences forgotten.",
            )
        return None

    def record_style(self, conversation_id, explanation):
        self._last_style[str(conversation_id)] = str(explanation)

    def _save(self, profile, message):
        record = self._record()
        metadata = profile.context()
        if record is None:
            record = self._factory.create(
                KnowledgeType.USER_APPROVED_REFERENCE,
                "Explicit Jarvis personality preferences",
                KnowledgeSource.USER_PROVIDED,
                title="Jarvis personality preferences",
                tags=(self.TAG,), metadata=metadata,
            )
            self._store.create(record)
        else:
            self._store.update(replace(record, metadata=metadata))
        return {"status": "success", "message": message}

    def _record(self):
        return next(
            (item for item in self._store.list_records() if self.TAG in item.tags),
            None,
        )
