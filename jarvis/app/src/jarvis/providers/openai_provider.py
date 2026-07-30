"""OpenAI provider for Project Jarvis."""

from typing import Any
import json

from openai import OpenAI


class OpenAIProvider:
    """
    Handles communication with OpenAI.
    """

    def __init__(self, api_key: str, logger):
        self.logger = logger
        self.client = OpenAI(api_key=api_key)

    def ask(self, input_data: Any) -> str:
        """
        Send input to OpenAI.
        """

        try:
            self.logger.info("Sending request to OpenAI.")
            request: dict[str, Any] = {"model": "gpt-5.5"}
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

            return response.output_text

        except Exception as exc:
            self.logger.error(f"OpenAI request failed: {exc}")
            return "I'm sorry, I couldn't contact OpenAI."

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
            "model": "gpt-5.5",
            "instructions": instructions,
            "input": input_messages,
            "tools": [tool],
            "tool_choice": "required" if force_search else "auto",
            "timeout": timeout_seconds,
        }
        try:
            self.logger.info("Sending general research request to OpenAI.")
            response = self.client.responses.create(**request)
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
