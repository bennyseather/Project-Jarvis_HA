"""
Project Jarvis

Application entry point.
"""

import asyncio

from jarvis.core.application import JarvisApplication


async def main():
    """
    Start Project Jarvis.
    """

    app = JarvisApplication()

    try:
        await app.run()

    finally:
        app.say_goodbye("Goodbye from Project Jarvis!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass