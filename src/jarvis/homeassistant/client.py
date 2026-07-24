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
        self.next_message_id = 1

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

    def get_next_message_id(self) -> int:
        """
        Return the next available Home Assistant message ID.
        """

        message_id = self.next_message_id
        self.next_message_id += 1

        return message_id

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

            return await self.get_states()

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
            "id": self.get_next_message_id(),
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

    async def call_service(
        self,
        domain: str,
        service: str,
        service_data: dict,
    ) -> bool:
        """
        Call a Home Assistant service.
        """

        self.logger.info(f"Calling service {domain}.{service}")

        request = {
            "id": self.get_next_message_id(),
            "type": "call_service",
            "domain": domain,
            "service": service,
            "service_data": service_data,
        }

        await self.send_json(request)

        response = await self.receive_json()

        if response["type"] != "result":
            raise RuntimeError(
                f"Unexpected response while calling service: {response}"
            )

        if not response.get("success", False):
            raise RuntimeError(
                f"Home Assistant reported a failed service call: {response}"
            )

        self.logger.info("Service call completed successfully.")

        return True

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