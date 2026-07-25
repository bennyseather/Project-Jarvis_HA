"""Deterministic console grammar for approved Memory and Knowledge operations."""
from __future__ import annotations
from datetime import datetime, timezone
from secrets import token_urlsafe

from jarvis.knowledge.store import KnowledgeNotFoundError
from jarvis.models.knowledge import KnowledgeSource, KnowledgeType
from jarvis.models.knowledge_write import ExplicitKnowledgeWriteRequest, KnowledgeCorrectionRequest
from jarvis.models.memory import MemoryConsentLevel, MemorySource, MemoryType
from jarvis.models.memory_management import MemoryManagementAction, MemoryManagementQuery, MemoryManagementRequest
from jarvis.models.memory_write import ExplicitMemoryWriteRequest, MemoryCorrectionRequest


class ExplicitDataConsole:
    """Handle explicit management commands without language-model involvement."""
    def __init__(self, memory_writer, memory_manager, knowledge_writer, knowledge_store) -> None:
        self._memory_writer, self._memory_manager = memory_writer, memory_manager
        self._knowledge_writer, self._knowledge_store = knowledge_writer, knowledge_store
        self._pending_sensitive: dict[str, str] = {}
        self._pending_sensitive_deletions: dict[str, str] = {}

    def handle(self, text: str) -> dict[str, object] | None:
        command, _, remainder = text.strip().partition(" ")
        if command == "memory": return self._memory(remainder)
        if command == "knowledge": return self._knowledge(remainder)
        return None

    def _memory(self, remainder: str) -> dict[str, object]:
        action, _, value = remainder.partition(" ")
        if action == "remember" and value.strip():
            return self._memory_result(self._memory_writer.create_explicit_memory(self._memory_request(value)))
        if action == "remember-sensitive" and value.strip():
            token = token_urlsafe(18); self._pending_sensitive[token] = value.strip()
            return {"status":"requires_confirmation","message":"Sensitive memory requires confirmation.","token":token}
        if action == "confirm" and value.strip():
            content = self._pending_sensitive.pop(value.strip(), None)
            if content is None: return {"status":"forbidden","message":"Sensitive memory confirmation is invalid."}
            return self._memory_result(self._memory_writer.create_explicit_memory(self._memory_request(content, sensitive=True, confirmed=True)))
        if action == "forget-sensitive" and value.strip():
            token = token_urlsafe(18); self._pending_sensitive_deletions[token] = value.strip()
            return {"status":"requires_confirmation","message":"Sensitive memory deletion requires confirmation.","token":token,"confirmation_command":"memory confirm-delete"}
        if action == "confirm-delete" and value.strip():
            memory_id = self._pending_sensitive_deletions.pop(value.strip(), None)
            if memory_id is None: return {"status":"forbidden","message":"Sensitive memory deletion confirmation is invalid."}
            result = self._memory_manager.manage(MemoryManagementRequest(MemoryManagementAction.DELETE_ONE, MemoryManagementQuery(memory_id=memory_id, include_sensitive=True), has_confirmation=True))
            return {"status":result.status.value,"message":result.reason_code,"deleted":result.deleted_count}
        if action == "list":
            result = self._memory_manager.manage(MemoryManagementRequest(MemoryManagementAction.LIST, MemoryManagementQuery()))
            return {"status":result.status.value,"message":"Memory list ready.","items":tuple({"id":item.memory_id,"type":item.memory_type.value,"tags":item.tags} for item in result.candidates)}
        if action == "forget" and value.strip():
            result = self._memory_manager.manage(MemoryManagementRequest(MemoryManagementAction.DELETE_ONE, MemoryManagementQuery(memory_id=value.strip())))
            return {"status":result.status.value,"message":result.reason_code,"deleted":result.deleted_count}
        if action == "correct" and "|" in value:
            memory_id, content = (part.strip() for part in value.split("|", 1))
            return self._memory_result(self._memory_writer.correct_memory(MemoryCorrectionRequest(memory_id, content, MemorySource.USER_CORRECTION, MemoryConsentLevel.EXPLICIT)))
        return {"status":"not_supported","message":"Use: memory remember, remember-sensitive, confirm, list, forget, forget-sensitive, confirm-delete, or correct."}

    def _knowledge(self, remainder: str) -> dict[str, object]:
        action, _, value = remainder.partition(" ")
        if action == "add" and value.strip():
            result = self._knowledge_writer.create_explicit_knowledge(ExplicitKnowledgeWriteRequest(value.strip(), KnowledgeType.HOME_REFERENCE, KnowledgeSource.USER_PROVIDED))
            return self._knowledge_result(result)
        if action == "list":
            return {"status":"success","message":"Knowledge list ready.","items":tuple({"id":record.knowledge_id,"title":record.title} for record in self._knowledge_store.list_records())}
        if action == "forget" and value.strip():
            try: self._knowledge_store.delete(value.strip())
            except KnowledgeNotFoundError: return {"status":"no_match","message":"Knowledge not found."}
            return {"status":"success","message":"Knowledge deleted."}
        if action == "correct" and "|" in value:
            knowledge_id, content = (part.strip() for part in value.split("|", 1))
            return self._knowledge_result(self._knowledge_writer.correct_knowledge(KnowledgeCorrectionRequest(knowledge_id, content, KnowledgeSource.USER_PROVIDED)))
        return {"status":"not_supported","message":"Use: knowledge add, list, forget, or correct."}

    @staticmethod
    def _memory_request(content: str, sensitive=False, confirmed=False) -> ExplicitMemoryWriteRequest:
        return ExplicitMemoryWriteRequest(content.strip(), MemoryType.FACT, MemorySource.EXPLICIT_USER_REQUEST, MemoryConsentLevel.EXPLICIT, is_sensitive=sensitive, has_sensitive_confirmation=confirmed)

    @staticmethod
    def _memory_result(result) -> dict[str, object]:
        return {"status":result.status.value,"message":result.reason_code,"id":None if result.record is None else result.record.memory_id,"requires_confirmation":result.requires_confirmation}

    @staticmethod
    def _knowledge_result(result) -> dict[str, object]:
        return {"status":result.status.value,"message":result.reason_code,"id":None if result.record is None else result.record.knowledge_id}
