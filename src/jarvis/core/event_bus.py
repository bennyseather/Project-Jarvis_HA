"""
Event bus for Project Jarvis.
"""


class EventBus:
    """
    Publishes events throughout the application.
    """

    def publish(self, event_name: str):
        print(f"[EVENT] {event_name}")