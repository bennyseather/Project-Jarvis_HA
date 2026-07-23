"""
Event bus for Project Jarvis.
"""


class EventBus:
    """
    Publishes events throughout the application.
    """

    def __init__(self):
        self.listeners = []

    def subscribe(self, callback):
        self.listeners.append(callback)

    def publish(self, event_name: str):
        print(f"[EVENT] {event_name}")

        for callback in self.listeners:
            callback(event_name)