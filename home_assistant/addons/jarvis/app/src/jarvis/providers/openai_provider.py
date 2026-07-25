"""
OpenAI provider for Project Jarvis.
"""

from typing import Any

from openai import OpenAI

from pprint import pprint


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
            self.logger.info("Sending context to OpenAI:")

            pprint(input_data)
            response = self.client.responses.create(
                model="gpt-5.5",
                input=input_data,
            )

            return response.output_text

        except Exception as exc:
            self.logger.error(f"OpenAI request failed: {exc}")
            return "I'm sorry, I couldn't contact OpenAI."