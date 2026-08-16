"""Client for the private Jarvis node telemetry service."""

from aiohttp import ClientError, ClientSession, ClientTimeout


class JarvisNodeApi:
    def __init__(self, session: ClientSession, url: str, token: str) -> None:
        self.session = session
        self.url = url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}

    async def status(self) -> dict:
        try:
            async with self.session.get(
                f"{self.url}/v1/status", headers=self.headers, timeout=ClientTimeout(total=10)
            ) as response:
                response.raise_for_status()
                return await response.json()
        except ClientError as err:
            raise ConnectionError(str(err)) from err
