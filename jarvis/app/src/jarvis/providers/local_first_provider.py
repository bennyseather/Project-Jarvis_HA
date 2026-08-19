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
    context_tokens: int = 4096
    maximum_input_messages: int = 8
    maximum_input_characters: int = 12000
    maximum_output_tokens: int = 160
    failure_cooldown_seconds: int = 30

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
        if not 2048 <= policy.context_tokens <= 32768:
            raise ValueError("local_reasoning.context_tokens is invalid")
        if not 2 <= policy.maximum_input_messages <= 30:
            raise ValueError("local_reasoning.maximum_input_messages is invalid")
        if not 2000 <= policy.maximum_input_characters <= 100000:
            raise ValueError("local_reasoning.maximum_input_characters is invalid")
        if not 32 <= policy.maximum_output_tokens <= 1024:
            raise ValueError("local_reasoning.maximum_output_tokens is invalid")
        if not 5 <= policy.failure_cooldown_seconds <= 300:
            raise ValueError("local_reasoning.failure_cooldown_seconds is invalid")
        return policy


class LocalFirstReasoningProvider:
    """Expose Jarvis's provider contract while keeping ordinary reasoning local."""
    local_first = True

    def __init__(self, policy, logger, fallback=None):
        self.policy, self.logger, self.fallback = policy, logger, fallback
        self._local_unavailable_until = 0.0

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

    def reason_local(self, *, instructions, input_messages, timeout_seconds):
        """Run exactly one local pass without invoking the external fallback."""
        try:
            message = self._chat(
                instructions, input_messages, timeout_seconds=timeout_seconds
            )
            return {
                "status": "success",
                "message": message,
                "provider": "ollama",
                "model": self.policy.model,
                "estimated_cost_usd": 0.0,
            }
        except Exception as exc:
            self.logger.warning(f"Local knowledge pass unavailable: {exc}")
            return {
                "status": "unavailable",
                "message": "Local reasoning is temporarily unavailable.",
            }

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

    def warm(self):
        """Load the configured model without generating user-visible content."""
        try:
            payload = self._post(
                "/api/generate",
                {"model": self.policy.model, "prompt": "", "keep_alive": -1},
                timeout_seconds=30,
            )
            return {"ready": bool(payload), "provider": "ollama", "model": self.policy.model}
        except Exception as exc:
            self.logger.warning(f"Local reasoning warm-up deferred: {exc}")
            return {"ready": False, "provider": "ollama", "model": self.policy.model}

    def _chat(self, instructions, messages, *, json_output=False, timeout_seconds=None):
        import time
        if time.monotonic() < self._local_unavailable_until:
            raise RuntimeError("local worker is in a short recovery cooldown")
        ollama_messages = []
        if instructions:
            ollama_messages.append({
                "role": "system",
                "content": str(instructions)[: self.policy.maximum_input_characters // 2],
            })
        remaining = self.policy.maximum_input_characters - sum(
            len(item["content"]) for item in ollama_messages
        )
        bounded = [item for item in messages if isinstance(item, dict)][
            -self.policy.maximum_input_messages:
        ]
        for item in bounded:
            content = str(item.get("content", ""))[:max(0, remaining)]
            if not content:
                continue
            ollama_messages.append({
                "role": str(item.get("role", "user")), "content": content
            })
            remaining -= len(content)
        payload = {
            "model": self.policy.model,
            "messages": ollama_messages,
            "stream": False,
            "think": False,
            "keep_alive": -1,
            "options": {
                "temperature": 0.2,
                "num_ctx": self.policy.context_tokens,
                "num_predict": 512 if json_output else self.policy.maximum_output_tokens,
            },
        }
        if json_output:
            payload["format"] = "json"
        try:
            response = self._post("/api/chat", payload, timeout_seconds=timeout_seconds)
        except Exception:
            self._local_unavailable_until = time.monotonic() + self.policy.failure_cooldown_seconds
            raise
        self._local_unavailable_until = 0.0
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
