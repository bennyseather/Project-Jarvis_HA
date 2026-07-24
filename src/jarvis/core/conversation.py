"""
Conversation management for Project Jarvis.
"""

from jarvis.models.chat_message import ChatMessage


class Conversation:
    """
    Stores the current conversation between the user and Jarvis.
    """

    def __init__(self):
        self.messages: list[ChatMessage] = []

    def add_user_message(self, message: str) -> None:
        """
        Add a message from the user.
        """
        self.messages.append(
            ChatMessage(
                role="user",
                content=message,
            )
        )

    def add_assistant_message(self, message: str) -> None:
        """
        Add a message from Jarvis.
        """
        self.messages.append(
            ChatMessage(
                role="assistant",
                content=message,
            )
        )

    def history(self) -> list[ChatMessage]:
        """
        Return a copy of the conversation history.
        """
        return self.messages.copy()

    def clear(self) -> None:
        """
        Clear the conversation history.
        """
        self.messages.clear()

    def to_openai_input(self) -> list[dict[str, str]]:
        """
        Return the conversation in a format suitable for OpenAI.
        """
        return [
            message.to_openai()
            for message in self.messages
        ]

    def last_message(self) -> ChatMessage | None:
        """
        Return the most recent message in the conversation.
        """
        if not self.messages:
            return None

        return self.messages[-1]

    def message_count(self) -> int:
        """
        Return the number of messages in the conversation.
        """
        return len(self.messages)