"""
Context builder for Project Jarvis.
"""

from jarvis.core.conversation import Conversation


class ContextBuilder:
    """
    Builds the context that is sent to the reasoning engine.
    """

    def build(
        self,
        conversation: Conversation,
    ) -> list[dict[str, str]]:
        """
        Build the current conversation context.
        """

        return conversation.to_openai_input()