from jarvis.skills.base import Skill


class HomeAssistantSkill(Skill):

    def __init__(self, home_assistant):
        self.home_assistant = home_assistant

    def can_handle(self, message: str) -> bool:

        text = message.lower()

        return (
            "turn on" in text
            or "turn off" in text
        )

    def execute(self, message: str) -> str:

        return "Home Assistant command received."