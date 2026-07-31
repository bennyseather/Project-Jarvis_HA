"""Inspectable, safety-subordinate personality preferences."""

from __future__ import annotations

from dataclasses import dataclass, replace

from jarvis.models.knowledge import KnowledgeRecordFactory, KnowledgeSource, KnowledgeType


@dataclass(frozen=True, slots=True)
class PersonalityProfile:
    address: str = ""
    humour: str = "subtle"
    formality: str = "refined"
    verbosity: str = "concise"
    locale: str = "en-GB"
    voice: str = "original British synthetic"

    def context(self):
        return {
            "address": self.address, "humour": self.humour,
            "formality": self.formality, "verbosity": self.verbosity,
            "locale": self.locale, "voice": self.voice,
            "safety": (
                "No humour for failures, safety, confirmations, emergencies, "
                "or sensitive topics. Never claim consciousness or imitate a "
                "fictional character or actor."
            ),
        }


class PersonalityManager:
    TAG = "jarvis:personality-profile"
    OPTIONS = {
        "humour": {"off", "subtle"},
        "formality": {"relaxed", "refined"},
        "verbosity": {"concise", "balanced"},
    }

    def __init__(self, store, *, factory=None):
        self._store = store
        self._factory = factory or KnowledgeRecordFactory()

    def profile(self):
        record = self._record()
        if record is None:
            return PersonalityProfile()
        values = record.metadata
        return PersonalityProfile(
            str(values.get("address", "")),
            str(values.get("humour", "subtle")),
            str(values.get("formality", "refined")),
            str(values.get("verbosity", "concise")),
        )

    def handle(self, text):
        normalized = " ".join(text.casefold().strip(" .?!").split())
        if normalized in {"show personality", "explain personality"}:
            profile = self.profile()
            return {"status": "success", "message": (
                f"Personality: {profile.formality}, {profile.verbosity}, "
                f"humour {profile.humour}, British English, original subtly "
                f"synthetic voice. Address: {profile.address or 'not set'}."
            )}
        if normalized.startswith("address me as "):
            return self._save(replace(
                self.profile(), address=text.strip()[len("address me as "):].strip()
            ), "Address preference updated.")
        if normalized.startswith("set personality "):
            parts = normalized.split()
            if len(parts) != 4 or parts[2] not in self.OPTIONS or parts[3] not in self.OPTIONS[parts[2]]:
                return {"status": "clarification_required", "message": (
                    "Use: set personality humour off|subtle, formality "
                    "relaxed|refined, or verbosity concise|balanced."
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
        return None

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
