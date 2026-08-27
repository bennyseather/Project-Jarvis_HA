"""Per-run Assist adapter; keeps HA in charge of VAD, STT and actions."""
import asyncio
import logging
import voluptuous as vol
from homeassistant.components import stt, websocket_api
from homeassistant.components.assist_pipeline.pipeline import (
    AudioSettings, PipelineInput, PipelineRun, PipelineStage, WakeWordSettings,
    async_get_pipeline,
)
from homeassistant.helpers import chat_session

LOGGER = logging.getLogger(__name__)


@websocket_api.websocket_command({
    vol.Required("type"): "jarvis_conversation/listen",
    vol.Required("start_stage"): vol.In(["stt", "wake_word"]),
    vol.Required("end_stage"): "tts",
    vol.Required("input"): {vol.Required("sample_rate"): 16000},
    vol.Required("conversation_id"): str,
    vol.Optional("pipeline"): str,
    vol.Optional("device_id"): str,
    vol.Optional("timeout", default=300): vol.All(int, vol.Range(min=10, max=300)),
})
@websocket_api.async_response
async def listen(hass, connection, msg):
    if not msg["conversation_id"].startswith("jarvis-voice-v3:development_computer:"):
        connection.send_error(msg["id"], "invalid_target", "Development satellite only")
        return
    queue = asyncio.Queue(maxsize=600)
    task = None
    acknowledged = False
    def audio_received(_hass, _connection, data):
        if queue.full():
            if task is not None:
                task.cancel()
            return
        queue.put_nowait(data)
    handler, unregister = connection.async_register_binary_handler(audio_received)
    async def stream():
        while chunk := await queue.get():
            yield chunk
    try:
        pipeline = async_get_pipeline(hass, msg.get("pipeline"))
        run = PipelineRun(
            hass, context=connection.context(msg), pipeline=pipeline,
            start_stage=PipelineStage(msg["start_stage"]), end_stage=PipelineStage.TTS,
            event_callback=lambda event: connection.send_event(msg["id"], event),
            runner_data={"stt_binary_handler_id": handler, "timeout": msg["timeout"]},
            wake_word_settings=WakeWordSettings(timeout=15) if msg["start_stage"] == "wake_word" else None,
            audio_settings=AudioSettings(silence_seconds=1.8),
        )
        metadata = stt.SpeechMetadata(
            language=pipeline.stt_language or pipeline.language,
            format=stt.AudioFormats.WAV, codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        )
        with chat_session.async_get_chat_session(hass, msg["conversation_id"]) as session:
            pipeline_input = PipelineInput(run=run, session=session,
                device_id=msg.get("device_id"), stt_metadata=metadata, stt_stream=stream())
            await pipeline_input.validate()
            connection.send_result(msg["id"])
            acknowledged = True
            task = hass.async_create_task(pipeline_input.execute())
            connection.subscriptions[msg["id"]] = task.cancel
            async with asyncio.timeout(msg["timeout"]):
                await task
    except asyncio.CancelledError:
        raise
    except Exception:
        LOGGER.exception("Jarvis development listening pipeline failed")
        if acknowledged:
            connection.send_event(msg["id"], {"type": "error", "data": {
                "code": "listening_failed", "message": "Check the HA pipeline and microphone connection"}})
        else:
            connection.send_error(msg["id"], "listening_failed", "Check the HA pipeline configuration")
    finally:
        unregister()
        connection.subscriptions.pop(msg["id"], None)
        if task is not None and not task.done():
            task.cancel()
