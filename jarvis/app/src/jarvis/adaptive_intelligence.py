"""Adaptive, bounded local response planning and dialogue subject continuity."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class AdaptiveResponsePlan:
    tier: str
    maximum_output_tokens: int
    voice_sentence_limit: int
    reason: str
    expand_detail: bool = False

    def context(self):
        return {
            "tier": self.tier,
            "maximum_output_tokens": self.maximum_output_tokens,
            "voice_sentence_limit": self.voice_sentence_limit,
            "expand_detail": self.expand_detail,
        }


class AdaptiveLocalIntelligence:
    """Choose local effort and retain only a bounded non-sensitive subject hint."""

    _EXPAND = re.compile(r"\b(tell me more|more detail|expand|go deeper|elaborate)\b", re.I)
    _FOLLOW_UP = re.compile(
        r"^(?:and |also |but )?(?:which|what about|how about|why|how|is it|are they|"
        r"which one|what else|tell me more)\b", re.I
    )
    _WORDS = re.compile(r"[a-z0-9][a-z0-9'-]*", re.I)
    _STOP = {
        "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "compare",
        "do", "does", "explain", "for", "from", "how", "i", "in", "is", "it", "me",
        "of", "on", "or", "please", "tell", "than", "that", "the", "they", "this",
        "to", "what", "which", "who", "why", "with", "you",
    }

    def __init__(self, maximum_subjects=128):
        self._subjects = OrderedDict()
        self._maximum_subjects = maximum_subjects

    def plan(self, text, *, route, voice_mode, metrics=None):
        value = " ".join(str(text).casefold().split())
        expand = bool(self._EXPAND.search(value))
        if route in {"home_assistant", "local_facts", "memory_knowledge"}:
            return AdaptiveResponsePlan("deterministic", 0, 2, "local_capability")
        if route == "current_information":
            return AdaptiveResponsePlan("verified_current", 96, 2, "bounded_verified_synthesis")
        if expand:
            return AdaptiveResponsePlan("detailed_local", 220, 4, "explicit_detail_request", True)
        p95 = int((metrics or {}).get("p95_ms", 0) or 0)
        if voice_mode:
            tokens = 96 if p95 < 8000 else 72
            return AdaptiveResponsePlan("quick_voice", tokens, 2, "voice_latency_budget")
        return AdaptiveResponsePlan("standard_local", 180, 4, "text_reasoning")

    def subject_context(self, text, conversation_id):
        identifier = str(conversation_id or "local-default")
        value = " ".join(str(text).strip().split())
        previous = self._subjects.get(identifier, "")
        follow_up = bool(previous and self._FOLLOW_UP.search(value))
        extracted = self._extract_subject(value)
        subject = previous if follow_up else (extracted or previous)
        if extracted and not follow_up:
            self._remember(identifier, extracted)
        elif previous:
            self._subjects.move_to_end(identifier)
        return {
            "subject": subject,
            "is_follow_up": follow_up,
            "instruction": (
                f"Resolve this turn as a follow-up about: {subject}."
                if follow_up and subject else ""
            ),
        }

    def clear(self, conversation_id=None):
        if conversation_id is None:
            self._subjects.clear()
        else:
            self._subjects.pop(str(conversation_id), None)

    def _remember(self, identifier, subject):
        self._subjects[identifier] = subject[:180]
        self._subjects.move_to_end(identifier)
        while len(self._subjects) > self._maximum_subjects:
            self._subjects.popitem(last=False)

    def _extract_subject(self, text):
        words = [word.casefold() for word in self._WORDS.findall(text)]
        content = [word for word in words if word not in self._STOP and len(word) > 1]
        return " ".join(content[:12])
