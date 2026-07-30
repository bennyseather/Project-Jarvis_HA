"""General reasoning, live research, source continuity, and explicit memory consent."""

from __future__ import annotations

from dataclasses import dataclass

from jarvis.models.memory import MemoryConsentLevel, MemorySource, MemoryType
from jarvis.models.memory_write import ExplicitMemoryWriteRequest


@dataclass(frozen=True, slots=True)
class ResearchPolicy:
    enabled: bool = True
    automatic: bool = True
    search_context_size: str = "medium"
    maximum_sources: int = 5
    timeout_seconds: int = 45
    allowed_domains: tuple[str, ...] = ()

    @classmethod
    def from_config(cls, config: object) -> "ResearchPolicy":
        if not isinstance(config, dict):
            raise ValueError("research must be a mapping")
        enabled = config.get("enabled", True)
        automatic = config.get("automatic", True)
        context_size = config.get("search_context_size", "medium")
        maximum_sources = config.get("maximum_sources", 5)
        timeout_seconds = config.get("timeout_seconds", 45)
        allowed_domains = config.get("allowed_domains", ())
        if not isinstance(enabled, bool) or not isinstance(automatic, bool):
            raise ValueError("research enabled and automatic must be booleans")
        if context_size not in {"low", "medium", "high"}:
            raise ValueError("research.search_context_size must be low, medium, or high")
        if (
            not isinstance(maximum_sources, int)
            or isinstance(maximum_sources, bool)
            or not 1 <= maximum_sources <= 10
        ):
            raise ValueError("research.maximum_sources must be between 1 and 10")
        if (
            not isinstance(timeout_seconds, int)
            or isinstance(timeout_seconds, bool)
            or not 5 <= timeout_seconds <= 120
        ):
            raise ValueError("research.timeout_seconds must be between 5 and 120")
        if (
            not isinstance(allowed_domains, (list, tuple))
            or not all(isinstance(domain, str) and domain.strip() for domain in allowed_domains)
        ):
            raise ValueError("research.allowed_domains must contain domain names")
        return cls(
            enabled,
            automatic,
            context_size,
            maximum_sources,
            timeout_seconds,
            tuple(domain.strip().casefold() for domain in allowed_domains),
        )

    def context(self, conversation_enabled: bool) -> dict[str, object]:
        return {
            "enabled": self.enabled and conversation_enabled,
            "automatic": self.automatic,
            "search_context_size": self.search_context_size,
            "maximum_sources": self.maximum_sources,
            "allowed_domains": self.allowed_domains,
        }


class GeneralResearchProvider:
    """Use OpenAI reasoning with native web search and bounded citations."""

    INSTRUCTIONS = """You are Jarvis's general reasoning and live-research layer.
Answer the user's actual question directly and helpfully in British English.
Use web search when the question is current, niche, uncertain, externally verifiable,
or explicitly asks for research. Prefer primary and authoritative sources. Compare
sources when claims conflict. Clearly distinguish verified facts, source claims,
and your own inference. Never claim that a person or public profile is the user
without adequate disambiguating evidence. Do not imply that research is durable
memory; Jarvis stores it only after an explicit user request. Do not propose or
perform Home Assistant actions. Keep voice-mode answers concise. Source metadata
is returned separately, so do not read URLs aloud."""

    def __init__(self, openai_provider, policy: ResearchPolicy) -> None:
        self._openai = openai_provider
        self._policy = policy

    def answer(
        self,
        query: str,
        context: dict[str, object],
        *,
        force_search: bool = False,
    ) -> dict[str, object]:
        history = context.get("conversation", ())
        messages = [
            {"role": item["role"], "content": item["content"]}
            for item in history
            if isinstance(item, dict)
            and item.get("role") in {"user", "assistant"}
            and isinstance(item.get("content"), str)
        ]
        compact_context = {
            "memory": context.get("memory", ()),
            "knowledge": context.get("knowledge", ()),
            "personality": context.get("personality", {}),
            "interaction": context.get("interaction", {}),
        }
        messages.append({
            "role": "user",
            "content": f"Question: {query}\nJarvis context: {compact_context}",
        })
        return self._openai.research(
            instructions=self.INSTRUCTIONS,
            input_messages=messages,
            force_search=force_search,
            search_context_size=self._policy.search_context_size,
            allowed_domains=self._policy.allowed_domains,
            maximum_sources=self._policy.maximum_sources,
            timeout_seconds=self._policy.timeout_seconds,
        )


class ResearchController:
    """Conversation controls and explicit consent for research-derived memory."""

    def __init__(self, policy: ResearchPolicy, memory_store, memory_writer) -> None:
        self._policy = policy
        self._memory_store = memory_store
        self._memory_writer = memory_writer
        self._disabled: set[str] = set()
        self._last: dict[str, dict[str, object]] = {}
        self._saved: dict[str, str] = {}

    def enabled(self, conversation_id: str) -> bool:
        return self._policy.enabled and conversation_id not in self._disabled

    def record(self, conversation_id: str, result: dict[str, object]) -> None:
        if result.get("researched") or result.get("sources"):
            self._last[conversation_id] = {
                "message": str(result.get("message", "")),
                "sources": tuple(result.get("sources", ())),
            }

    def handle(self, text: str, conversation_id: str) -> dict[str, object] | None:
        command = " ".join(text.casefold().split()).strip(" .?!")
        if command in {
            "do not use web research for this conversation",
            "disable web research for this conversation",
        }:
            self._disabled.add(conversation_id)
            return {
                "status": "success",
                "message": "Web research is disabled for this conversation.",
            }
        if command in {
            "use web research for this conversation",
            "enable web research for this conversation",
        }:
            self._disabled.discard(conversation_id)
            return {
                "status": "success",
                "message": "Web research is enabled for this conversation.",
            }
        if command in {"what sources did you use", "show research sources"}:
            last = self._last.get(conversation_id)
            sources = () if last is None else last["sources"]
            if not sources:
                return {
                    "status": "success",
                    "message": "I have no recorded research sources for this conversation.",
                }
            return {
                "status": "success",
                "message": "Sources: " + "; ".join(
                    f"{source['title']} — {source['url']}" for source in sources
                ),
                "sources": sources,
            }
        if command in {"remember this", "remember this research"}:
            last = self._last.get(conversation_id)
            if last is None:
                return None
            content = str(last["message"]).strip()
            if not content:
                return {"status": "unavailable", "message": "There is no research answer to remember."}
            result = self._memory_writer.create_explicit_memory(
                ExplicitMemoryWriteRequest(
                    content[:4000],
                    MemoryType.FACT,
                    MemorySource.EXPLICIT_USER_REQUEST,
                    MemoryConsentLevel.EXPLICIT,
                    tags=("approved_research",),
                    metadata={"sources": list(last["sources"])},
                )
            )
            if result.record:
                self._saved[conversation_id] = result.record.memory_id
                return {
                    "status": "success",
                    "message": "Understood. I saved that researched information with its sources.",
                }
            return {"status": "unavailable", "message": "I could not save that research memory."}
        if command in {"forget this", "forget this research"} and conversation_id in self._saved:
            self._memory_store.delete(self._saved.pop(conversation_id))
            return {
                "status": "success",
                "message": "Done. I permanently deleted that research memory.",
            }
        return None
