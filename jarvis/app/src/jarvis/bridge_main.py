"""Run Jarvis as a Home Assistant add-on bridge."""
import asyncio
import os
from jarvis.core.application import JarvisApplication
from jarvis.homeassistant.bridge_server import ConversationBridgeServer
from jarvis.homeassistant.conversation_bridge import JarvisConversationBridge


async def main():
    app = JarvisApplication(); app.load_configuration(); app.initialize_services(); await app.connect_services(); await app.startup_checks()
    key = os.environ.get("JARVIS_BRIDGE_API_KEY")
    if not key: raise RuntimeError("JARVIS_BRIDGE_API_KEY is required")
    server = ConversationBridgeServer(JarvisConversationBridge(app), key, asyncio.get_running_loop())
    server.start()
    try: await asyncio.Event().wait()
    finally:
        server.stop()
        if app.container.timeline_task is not None:
            app.container.timeline_task.cancel()
        if app.container.proactive_task is not None:
            app.container.proactive_task.cancel()
        if app.container.timeline_client is not None:
            await app.container.timeline_client.disconnect()
        if app.container.proactive_client is not None:
            await app.container.proactive_client.disconnect()
        await app.container.home_assistant.disconnect()
        app.container.memory_store.close()
        app.container.knowledge_store.close()
        app.container.conversation_store.close()
        app.container.reflection_store.close()
        app.container.proactive_store.close()


if __name__ == "__main__": asyncio.run(main())
