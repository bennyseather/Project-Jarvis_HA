"""
Home Assistant client for Project Jarvis.
"""

import json

import websockets


class HomeAssistantClient:
    """
    Handles communication with Home Assistant.
    """

    def __init__(self, url: str, token: str, logger):
        self.url = url
        self.token = token
        self.logger = logger

        self.websocket = None

    async def connect(self):
        """
        Connect to Home Assistant.
        """

        ws_url = self.url.replace("http://", "ws://")
        ws_url = ws_url.replace("https://", "wss://")
        ws_url += "/api/websocket"

        self.logger.info(f"Connecting to {ws_url}")

        self.websocket = await websockets.connect(ws_url)

        self.logger.info("Connected successfully")

    async def authenticate(self):
        """
        Authenticate with Home Assistant.
        """

        pass

    async def disconnect(self):
        """
        Close the connection.
        """

        if self.websocket:
            await self.websocket.close()