"""Keep the bridge alive while Home Assistant is still starting."""
import asyncio


async def connect_when_ready(connect, logger, *, sleep=asyncio.sleep):
    delay = 2
    while True:
        try:
            await connect()
            return
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning(
                f"Home Assistant startup connection unavailable ({type(error).__name__}); "
                f"retrying in {delay}s. If persistent, check HA availability and bridge credentials."
            )
            await sleep(delay)
            delay = min(30, delay * 2)
