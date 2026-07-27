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
