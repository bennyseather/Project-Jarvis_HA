"""Deterministic request classification for the Context Engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from jarvis.models.request import Request, RequestClassification, RequestType
from jarvis.models.request_context import RequestContext
from jarvis.models.request_state import RequestState


class RequestClassifier(Protocol):
    """Classifies an incoming request without executing it."""

    def classify(self, request: Request) -> RequestClassification:
        """Return a classification outcome for ``request``."""


@dataclass(frozen=True, slots=True)
class ClassificationRule:
    """A request type and the phrases that identify it."""

    request_type: RequestType
    phrases: tuple[str, ...]


DEFAULT_RULES: tuple[ClassificationRule, ...] = (
    ClassificationRule(RequestType.MEMORY, ("remember", "do you remember", "forget")),
    ClassificationRule(
        RequestType.AUTOMATION,
        ("automate", "automation", "schedule", "every day", "when "),
    ),
    ClassificationRule(RequestType.PLANNING, ("plan ", "help me plan", "schedule my")),
    ClassificationRule(
        RequestType.COMMAND,
        ("turn on", "turn off", "set ", "open ", "close ", "lock ", "unlock "),
    ),
    ClassificationRule(
        RequestType.QUERY,
        ("what is", "what's", "is the", "are the", "how many", "show me"),
    ),
    ClassificationRule(
        RequestType.INFORMATION,
        ("tell me about", "explain", "how does", "what are"),
    ),
    ClassificationRule(
        RequestType.CONVERSATION,
        ("hello", "hi", "hey", "thanks", "thank you", "good morning"),
    ),
)


class KeywordRequestClassifier:
    """Classify requests using an ordered, extensible set of phrase rules."""

    def __init__(self, rules: Sequence[ClassificationRule] = DEFAULT_RULES) -> None:
        self._rules = tuple(rules)

    def classify(self, request: Request) -> RequestClassification:
        """Classify a request, returning ``UNKNOWN`` when no rule applies."""

        normalized_content = request.content.casefold()

        for rule in self._rules:
            if any(phrase in normalized_content for phrase in rule.phrases):
                return RequestClassification(request, rule.request_type)

        return RequestClassification(request, RequestType.UNKNOWN)

    def classify_context(self, request_context: RequestContext) -> RequestClassification:
        """Classify and enrich a request context without changing classification rules."""

        try:
            classification = self.classify(request_context.request)
        except Exception:
            request_context.state = RequestState.FAILED
            raise

        request_context.classification = classification
        request_context.state = RequestState.CLASSIFIED
        return classification
