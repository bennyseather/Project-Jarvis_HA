"""
Home Assistant client for Project Jarvis.
"""

import asyncio
import json
from urllib.parse import quote
from urllib.request import Request, urlopen

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
        self._background_tasks = set()

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

        await self._connect_socket()
        return await self._get_states_once()

    async def _connect_socket(self):
        """Open and authenticate a fresh Home Assistant websocket."""
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
        if self.url.rstrip("/") == "http://supervisor/core":
            ws_url = "ws://supervisor/core/websocket"
        else:
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
            return

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

        try:
            return await self._get_states_once()
        except Exception as error:
            self.logger.warning(
                f"Home Assistant state read failed; reconnecting once: {error}"
            )
            await self._connect_socket()
            return await self._get_states_once()

    async def _get_states_once(self) -> list:
        """Retrieve entity states once on the current authenticated socket."""
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

    async def get_services(self) -> list:
        """Retrieve Home Assistant's available service descriptions read-only."""
        request = {"id": self.get_next_message_id(), "type": "get_services"}
        await self.send_json(request)
        response = await self.receive_json()
        if response["type"] != "result":
            raise RuntimeError(f"Unexpected response while retrieving services: {response}")
        return response["result"]

    async def get_registry(self, command: str):
        request = {"id": self.get_next_message_id(), "type": command}
        await self.send_json(request)
        response = await self.receive_json()
        if response["type"] != "result":
            raise RuntimeError(f"Unexpected response while retrieving {command}: {response}")
        return response["result"]

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

    async def call_service_response(
        self,
        domain: str,
        service: str,
        service_data: dict,
    ) -> dict:
        """Call a read-style Home Assistant service and return its response."""
        request = {
            "id": self.get_next_message_id(),
            "type": "call_service",
            "domain": domain,
            "service": service,
            "service_data": service_data,
            "return_response": True,
        }
        await self.send_json(request)
        response = await self.receive_json()
        if response.get("type") != "result" or not response.get("success", False):
            raise RuntimeError(
                f"Home Assistant reported a failed service call: {response}"
            )
        result = response.get("result") or {}
        return result.get("response") or {}

    async def dispatch_service(
        self,
        domain: str,
        service: str,
        service_data: dict,
    ):
        """Send a service call on an isolated socket and return its result task."""

        dispatcher = HomeAssistantClient(self.url, self.token, self.logger)
        await dispatcher._connect_socket()
        request = {
            "id": dispatcher.get_next_message_id(),
            "type": "call_service",
            "domain": domain,
            "service": service,
            "service_data": service_data,
        }
        await dispatcher.send_json(request)
        task = asyncio.create_task(
            dispatcher._receive_dispatched_service_result()
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def dispatch_event(self, event_type: str, event_data: dict) -> bool:
        """Fire a bounded HA event through its local authenticated REST API."""
        return await asyncio.to_thread(self._dispatch_event, event_type, event_data)

    def _dispatch_event(self, event_type: str, event_data: dict) -> bool:
        request = Request(
            f"{self.url.rstrip('/')}/api/events/{quote(event_type, safe='')}",
            data=json.dumps(event_data).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(
                    f"Home Assistant rejected event dispatch with HTTP {response.status}"
                )
        return True

    async def _receive_dispatched_service_result(self):
        try:
            response = await self.receive_json()
            if response.get("type") != "result" or not response.get(
                "success", False
            ):
                raise RuntimeError(
                    f"Home Assistant reported a failed service call: {response}"
                )
            return True
        finally:
            await self.disconnect()

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
        tasks = tuple(self._background_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
