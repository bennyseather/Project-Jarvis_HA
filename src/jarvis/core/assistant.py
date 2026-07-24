"""
Jarvis Assistant.

Central intelligence of Project Jarvis.
"""

from jarvis.core.context_builder import ContextBuilder
from jarvis.core.conversation import Conversation
from jarvis.providers.openai_provider import OpenAIProvider


class Assistant:
    """
    Coordinates conversations with Jarvis.
    """

    def __init__(
        self,
        openai: OpenAIProvider,
        context_builder: ContextBuilder,
    ):
        self.openai = openai
        self.context_builder = context_builder
        self.conversation = Conversation()

    def respond(self, message: str) -> str:
        """
        Process a user message and return Jarvis's response.
        """

        self._store_user_message(message)

        response = self._generate_response()

        self._store_assistant_message(response)

        return response

    def ask(self, message: str) -> str:
        """
        Backwards compatibility.

        This method will be removed later.
        """

        return self.respond(message)

    def _store_user_message(self, message: str) -> None:
        self.conversation.add_user_message(message)

    def _generate_response(self) -> str:
        """
        Build the current context and send it to OpenAI.
        """

        context = self.context_builder.build(
            self.conversation
        )

        return self.openai.ask(context)

    def _store_assistant_message(self, message: str) -> None:
        self.conversation.add_assistant_message(message)