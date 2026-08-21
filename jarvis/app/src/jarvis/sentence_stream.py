"""Request-local completed-sentence delivery hook for voice orchestration."""
from contextvars import ContextVar

sentence_sink = ContextVar("jarvis_sentence_sink", default=None)
