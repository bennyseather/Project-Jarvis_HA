"""
Home Assistant client for Project Jarvis.
"""


class HomeAssistantClient:
    """
    Handles communication with Home Assistant.
    """

    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token

    def connect(self):
        """
        Connect to Home Assistant.
        """

        print(f"Connecting to Home Assistant at {self.url}")