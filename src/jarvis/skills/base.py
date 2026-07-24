from abc import ABC, abstractmethod


class Skill(ABC):
    """
    Base class for all Jarvis skills.
    """

    @abstractmethod
    def can_handle(self, message: str) -> bool:
        pass

    @abstractmethod
    def execute(self, message: str) -> str:
        pass