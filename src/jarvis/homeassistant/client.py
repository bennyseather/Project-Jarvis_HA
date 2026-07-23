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

    async def send_json(self, data: dict):
        """
        Send a JSON message to Home Assistant.
        """
        await self.websocket.send(json.dumps(data))

    async def receive_json(self) -> dict:
        """
        Receive a JSON message from Home Assistant.
        """

        message = await self.websocket.recv()
        data = json.loads(message)

        message_type = data.get("type", "unknown")
        self.logger.info(f"Received message of type '{message_type}'")

        return data

    async def connect(self):
        """
        Connect and authenticate with Home Assistant.
        """

        ws_url = self.url.replace("http://", "ws://")
        ws_url = ws_url.replace("https://", "wss://")
        ws_url += "/api/websocket"

        self.logger.info(f"Connecting to {ws_url}")

        self.websocket = await websockets.connect(ws_url)

        self.logger.info("Connected successfully")

        # Receive the initial handshake
        response = await self.receive_json()

        if response["type"] != "auth_required":
            raise RuntimeError(
                f"Unexpected response from Home Assistant: {response}"
            )

        # Send authentication
        auth_message = {
            "type": "auth",
            "access_token": self.token,
        }

        await self.send_json(auth_message)

        self.logger.info("Authentication request sent")

        # Receive authentication result
        auth_response = await self.receive_json()

        if auth_response["type"] == "auth_ok":
            self.logger.info("Successfully authenticated with Home Assistant")

            states = await self.get_states()

            self.logger.info(
                f"Discovered {len(states)} Home Assistant entities."
            )

        elif auth_response["type"] == "auth_invalid":
            raise RuntimeError(
                f"Authentication failed: {auth_response['message']}"
            )

        else:
            raise RuntimeError(
                f"Unexpected authentication response: {auth_response}"
            )

    async def get_states(self) -> list:
        """
        Retrieve all entity states from Home Assistant.
        """

        self.logger.info("Requesting entity states...")

        request = {
            "id": 1,
            "type": "get_states",
        }

        await self.send_json(request)

        response = await self.receive_json()

        if response["type"] != "result":
            raise RuntimeError(
                f"Unexpected response while retrieving states: {response}"
            )

        entities = response["result"]

        self.logger.info(f"Retrieved {len(entities)} entities.")

        return entities

    async def authenticate(self):
        """
        Reserved for future authentication refactoring.
        """
        pass

    async def disconnect(self):
        """
        Close the connection.
        """
        if self.websocket:
            await self.websocket.close()