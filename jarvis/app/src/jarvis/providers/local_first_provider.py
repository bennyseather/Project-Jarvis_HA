"""Local-first Ollama reasoning with an explicit OpenAI fallback."""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class LocalReasoningPolicy:
    enabled: bool = True
    url: str = "http://192.168.1.105:11434"
    model: str = "qwen3:8b"
    embedding_model: str = "qwen3-embedding:0.6b"
    timeout_seconds: int = 90
    fallback_to_openai: bool = True
    token: str = ""

    @classmethod
    def from_config(cls, value):
        config = {} if value is None else value
        if not isinstance(config, dict):
            raise ValueError("local_reasoning must be a mapping")
        policy = cls(**{name: config.get(name, getattr(cls(), name)) for name in cls.__dataclass_fields__})
        if not policy.url.startswith(("http://", "https://")):
            raise ValueError("local_reasoning.url must be HTTP(S)")
        if not policy.model.strip() or not policy.embedding_model.strip():
            raise ValueError("local reasoning model names must not be empty")
        if not 5 <= policy.timeout_seconds <= 300:
            raise ValueError("local_reasoning.timeout_seconds must be between 5 and 300")
        return policy


class LocalFirstReasoningProvider:
    """Expose Jarvis's provider contract while keeping ordinary reasoning local."""
    local_first = True

    def __init__(self, policy, logger, fallback=None):
        self.policy, self.logger, self.fallback = policy, logger, fallback

    def ask(self, input_data: Any) -> str:
        try:
            instructions, messages = self._request_parts(input_data)
            return self._chat(instructions, messages, json_output="Return JSON only" in instructions)
        except Exception as exc:
            self.logger.warning(f"Local reasoning unavailable: {exc}")
            if self.policy.fallback_to_openai and self.fallback is not None:
                return self.fallback.ask(input_data)
            return "Local reasoning is temporarily unavailable."

    def reason(self, *, instructions, input_messages, model, timeout_seconds):
        try:
            message = self._chat(instructions, input_messages, timeout_seconds=timeout_seconds)
            return {"status": "success", "message": message, "provider": "ollama", "model": self.policy.model, "estimated_cost_usd": 0.0}
        except Exception as exc:
            self.logger.warning(f"Local bounded reasoning unavailable: {exc}")
            if self.policy.fallback_to_openai and self.fallback is not None:
                return self.fallback.reason(instructions=instructions, input_messages=input_messages, model=model, timeout_seconds=timeout_seconds)
            return {"status": "unavailable", "message": "Local reasoning is temporarily unavailable."}

    def research(self, **kwargs):
        if self.fallback is None:
            return {"status": "unavailable", "message": "External research is unavailable.", "sources": ()}
        return self.fallback.research(**kwargs)

    def embed(self, text: str) -> tuple[float, ...]:
        payload = self._post("/api/embed", {"model": self.policy.embedding_model, "input": text, "keep_alive": 0})
        embeddings = payload.get("embeddings", ())
        if not embeddings or not isinstance(embeddings[0], list):
            raise RuntimeError("Ollama returned no embedding")
        return tuple(float(value) for value in embeddings[0])

    def health(self):
        payload = self._post("/api/show", {"model": self.policy.model}, timeout_seconds=10)
        return {"ready": bool(payload), "provider": "ollama", "model": self.policy.model}

    def _chat(self, instructions, messages, *, json_output=False, timeout_seconds=None):
        ollama_messages = []
        if instructions:
            ollama_messages.append({"role": "system", "content": str(instructions)})
        ollama_messages.extend({"role": str(item.get("role", "user")), "content": str(item.get("content", ""))} for item in messages if isinstance(item, dict))
        payload = {"model": self.policy.model, "messages": ollama_messages, "stream": False, "think": False, "keep_alive": "30m", "options": {"temperature": 0.2, "num_ctx": 8192}}
        if json_output:
            payload["format"] = "json"
        response = self._post("/api/chat", payload, timeout_seconds=timeout_seconds)
        message = str(response.get("message", {}).get("content", "")).strip()
        if not message:
            raise RuntimeError("Ollama returned no answer")
        return message

    def _post(self, path, payload, *, timeout_seconds=None):
        node_proxy = self.policy.token or self.policy.url.rstrip("/").endswith(":10550")
        route = "/v1/ollama" + path.removeprefix("/api") if node_proxy else path
        headers = {"Content-Type": "application/json", "User-Agent": "Project-Jarvis/0.45"}
        if self.policy.token:
            headers["Authorization"] = "Bearer " + self.policy.token
        request = Request(self.policy.url.rstrip("/") + route, data=json.dumps(payload).encode(), headers=headers, method="POST")
        with urlopen(request, timeout=timeout_seconds or self.policy.timeout_seconds) as response:
            return json.loads(response.read(16 * 1024 * 1024))

    @staticmethod
    def _request_parts(input_data):
        if isinstance(input_data, dict) and isinstance(input_data.get("input"), list):
            return str(input_data.get("instructions", "")), input_data["input"]
        return "", [{"role": "user", "content": json.dumps(input_data)}]
