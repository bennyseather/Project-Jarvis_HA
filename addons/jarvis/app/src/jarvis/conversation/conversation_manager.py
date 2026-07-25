"""
Conversation Manager

Coordinates conversations between the user, memory,
Home Assistant context, OpenAI and the orchestration layer.
"""

from __future__ import annotations


class ConversationManager:
    """
    The ConversationManager is responsible for handling an
    entire user conversation.

    It does not execute Home Assistant services directly.

    It does not know how individual capabilities work.

    Its responsibility is to gather context, build the AI
    request and return a structured result that another
    component can execute.
    """

    def __init__(self) -> None:
        """
        Create a ConversationManager.
        """

        pass

    async def process(self, user_message: str):
        """
        Process one user message.

        Planned workflow:

            User Message
                  │
                  ▼
            Load conversation history
                  │
                  ▼
            Load long-term memory
                  │
                  ▼
            Load Home Assistant context
                  │
                  ▼
            Build AI prompt
                  │
                  ▼
            Ask OpenAI
                  │
                  ▼
            Return structured response

        Returns
        -------
        Structured response from the AI.
        """

        raise NotImplementedError