"""OpenAI provider for Project Jarvis."""

from typing import Any
import json

from openai import OpenAI


class OpenAIProvider:
    """
    Handles communication with OpenAI.
    """

    PRICES_PER_MILLION = {
        "gpt-5.6-luna": (1.0, 6.0),
        "gpt-5.6-terra": (2.5, 15.0),
        "gpt-5.6-sol": (5.0, 30.0),
        "gpt-5.5": (5.0, 30.0),
    }

    def __init__(
        self, api_key: str, logger, *, default_model="gpt-5.6-luna",
        usage_ledger=None,
    ):
        self.logger = logger
        self.client = OpenAI(api_key=api_key)
        self.default_model = default_model
        self.usage_ledger = usage_ledger

    def ask(self, input_data: Any) -> str:
        """
        Send input to OpenAI.
        """

        if self.usage_ledger is not None and not self.usage_ledger.permitted(0.01):
            self.logger.warning("OpenAI request blocked by the monthly AI budget.")
            return "External AI budget reached."
        try:
            self.logger.info("Sending request to OpenAI.")
            request: dict[str, Any] = {"model": self.default_model}
            if (
                isinstance(input_data, dict)
                and isinstance(input_data.get("instructions"), str)
                and isinstance(input_data.get("input"), list)
            ):
                request["instructions"] = input_data["instructions"]
                request["input"] = input_data["input"]
            else:
                request["input"] = json.dumps(input_data)
            response = self.client.responses.create(**request)
            self._record_usage(response, self.default_model)
            return response.output_text

        except Exception as exc:
            self.logger.error(f"OpenAI request failed: {exc}")
            return "I'm sorry, I couldn't contact OpenAI."

    def reason(
        self,
        *,
        instructions: str,
        input_messages: list[dict[str, str]],
        model: str,
        timeout_seconds: int,
    ) -> dict[str, object]:
        """Implement the provider-neutral reasoning contract."""
        if self.usage_ledger is not None and not self.usage_ledger.permitted(0.01):
            self.logger.warning("OpenAI reasoning blocked by the monthly AI budget.")
            return {
                "status": "unavailable",
                "message": "The monthly external AI budget has been reached.",
                "provider": "openai",
                "model": model,
            }
        try:
            self.logger.info(f"Sending bounded reasoning request using {model}.")
            response = self.client.responses.create(
                model=model,
                instructions=instructions,
                input=input_messages,
                timeout=timeout_seconds,
            )
            cost = self._record_usage(response, model)
            message = str(getattr(response, "output_text", "")).strip()
            if not message:
                return {
                    "status": "unavailable",
                    "message": "The reasoning provider returned no answer.",
                }
            return {
                "status": "success",
                "message": message,
                "provider": "openai",
                "model": model,
                "estimated_cost_usd": cost,
            }
        except Exception as exc:
            self.logger.error(f"OpenAI reasoning request failed: {exc}")
            return {
                "status": "unavailable",
                "message": "External reasoning is temporarily unavailable.",
                "provider": "openai",
                "model": model,
            }

    def research(
        self,
        *,
        instructions: str,
        input_messages: list[dict[str, str]],
        force_search: bool,
        search_context_size: str,
        allowed_domains: tuple[str, ...] = (),
        maximum_sources: int = 5,
        timeout_seconds: int = 45,
    ) -> dict[str, object]:
        """Answer with optional live web research and structured source metadata."""

        tool: dict[str, object] = {
            "type": "web_search",
            "search_context_size": search_context_size,
        }
        if allowed_domains:
            tool["filters"] = {"allowed_domains": list(allowed_domains)}
        request: dict[str, Any] = {
            "model": self.default_model,
            "instructions": instructions,
            "input": input_messages,
            "tools": [tool],
            "tool_choice": "required" if force_search else "auto",
            "timeout": timeout_seconds,
        }
        try:
            self.logger.info("Sending general research request to OpenAI.")
            response = self.client.responses.create(**request)
            self._record_usage(response, self.default_model)
            sources = self._response_sources(response, maximum_sources)
            return {
                "status": "success",
                "message": response.output_text,
                "sources": sources,
                "researched": bool(sources),
            }
        except Exception as exc:
            self.logger.error(f"OpenAI research request failed: {exc}")
            return {
                "status": "unavailable",
                "message": "Live research is temporarily unavailable. Please try again.",
                "sources": (),
                "researched": False,
            }

    @staticmethod
    def _response_sources(response, maximum_sources: int) -> tuple[dict[str, str], ...]:
        """Extract unique URL citations without depending on SDK model classes."""

        found: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in getattr(response, "output", ()) or ():
            for content in getattr(item, "content", ()) or ():
                for annotation in getattr(content, "annotations", ()) or ():
                    if getattr(annotation, "type", None) != "url_citation":
                        continue
                    url = str(getattr(annotation, "url", "")).strip()
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    title = str(getattr(annotation, "title", "")).strip() or url
                    found.append({"title": title, "url": url})
                    if len(found) >= maximum_sources:
                        return tuple(found)
        return tuple(found)

    def _record_usage(self, response, model):
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        input_price, output_price = self.PRICES_PER_MILLION.get(
            model, (5.0, 30.0)
        )
        cost = (
            input_tokens * input_price + output_tokens * output_price
        ) / 1_000_000
        if self.usage_ledger is not None:
            self.usage_ledger.record(
                "openai", model, input_tokens, output_tokens, cost
            )
        return cost
