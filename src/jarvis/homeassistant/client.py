"""
Home Assistant client.
"""


class HomeAssistantClient:
    """
    Handles communication with Home Assistant.
    """

    def __init__(self):
        self.connected = False

    def connect(self):
        """
        Connect to Home Assistant.
        """

        self.connected = True

    def is_connected(self):
        return self.connected