"""Unit tests for request classification."""

import unittest

from jarvis.classification.request_classifier import KeywordRequestClassifier
from jarvis.models.request import Request, RequestType


class KeywordRequestClassifierTests(unittest.TestCase):
    """Verify the deterministic default classification rules."""

    def setUp(self) -> None:
        self.classifier = KeywordRequestClassifier()

    def test_classifies_supported_request_types(self) -> None:
        cases = (
            ("Remember that the guest room is upstairs.", RequestType.MEMORY),
            ("Schedule the porch light for every day at sunset.", RequestType.AUTOMATION),
            ("Help me plan the weekend cleaning.", RequestType.PLANNING),
            ("Turn on the kitchen lights.", RequestType.COMMAND),
            ("What is the temperature in the kitchen?", RequestType.QUERY),
            ("Tell me about the house energy use.", RequestType.INFORMATION),
            ("Hello, Jarvis.", RequestType.CONVERSATION),
        )

        for content, expected_type in cases:
            with self.subTest(content=content):
                classification = self.classifier.classify(Request(content))

                self.assertEqual(classification.request_type, expected_type)

    def test_returns_unknown_for_ambiguous_or_unsupported_requests(self) -> None:
        classification = self.classifier.classify(Request("Purple elephants ponder quietly."))

        self.assertEqual(classification.request_type, RequestType.UNKNOWN)

    def test_preserves_the_original_request(self) -> None:
        request = Request("Turn off the hallway lights.")

        classification = self.classifier.classify(request)

        self.assertIs(classification.request, request)

    def test_matches_phrases_without_regard_to_case(self) -> None:
        classification = self.classifier.classify(Request("TURN ON the kitchen lights."))

        self.assertEqual(classification.request_type, RequestType.COMMAND)
