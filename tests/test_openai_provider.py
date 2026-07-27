import json
import unittest
from unittest.mock import patch

from jarvis.providers.openai_provider import OpenAIProvider


class Logger:
    def info(self, message):
        pass

    def error(self, message):
        pass


class OpenAIProviderTests(unittest.TestCase):
    @patch("jarvis.providers.openai_provider.OpenAI")
    def test_serializes_structured_context_as_responses_text_input(self, openai_class):
        response = type("Response", (), {"output_text": "{}"})()
        openai_class.return_value.responses.create.return_value = response

        provider = OpenAIProvider("test-key", Logger())
        result = provider.ask({"request": "What is the state?"})

        self.assertEqual(result, "{}")
        request = openai_class.return_value.responses.create.call_args.kwargs
        self.assertEqual(request["model"], "gpt-5.5")
        self.assertEqual(json.loads(request["input"]), {"request": "What is the state?"})

    @patch("jarvis.providers.openai_provider.OpenAI")
    def test_preserves_instruction_and_conversation_items(self, openai_class):
        response = type("Response", (), {"output_text": "{}"})()
        openai_class.return_value.responses.create.return_value = response
        provider = OpenAIProvider("test-key", Logger())
        messages = [
            {"role": "user", "content": "What is the state of the interior lights?"},
            {"role": "assistant", "content": "Six devices: five on, one off."},
            {"role": "user", "content": "Are all of them on?"},
        ]

        provider.ask({"instructions": "Return JSON only.", "input": messages})

        request = openai_class.return_value.responses.create.call_args.kwargs
        self.assertEqual(request["instructions"], "Return JSON only.")
        self.assertEqual(request["input"], messages)
