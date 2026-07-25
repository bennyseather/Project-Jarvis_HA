"""
Chat message model.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ChatMessage:
    """
    Represents one message in a conversation.
    """

    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_openai(self) -> dict[str, str]:
        return {
            "role": self.role,
            "content": self.content,
        }
