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
    capture = None
    capture_timer = None

    def capture_call(method, *args):
        nonlocal capture
        if capture is None:
            return
        try:
            getattr(capture, method)(*args)
        except Exception:
            failed, capture = capture, None
            try:
                failed.abort()
            except Exception:
                pass

    def pipeline_event(event):
        # The normal event and audio paths never await optional recognition.
        connection.send_event(msg["id"], event)
        capture_call("on_event", event)

    # Only an explicit private-operator pairing enables this optional tap.
    # Browser conversation/device IDs or a shared HA user do not authorise it.
    # The factory is memory-only; no network/model work belongs on this path.
    try:
        factory = getattr(hass, "data", {}).get("jarvis_conversation", {}).get("speaker_capture_factory")
    except Exception:
        factory = None
    if factory is not None:
        try:
            capture = factory(connection, msg["conversation_id"], msg["start_stage"])
            if capture is not None:
                capture_timer = asyncio.get_running_loop().call_later(35, capture_call, "abort")
        except Exception:
            capture_call("abort")
            capture = None
    def audio_received(_hass, _connection, data):
        if queue.full():
            if task is not None:
                task.cancel()
            return
        queue.put_nowait(data)
    handler, unregister = connection.async_register_binary_handler(audio_received)
    async def stream():
        while chunk := await queue.get():
            capture_call("feed", chunk)
            yield chunk
    try:
        pipeline = async_get_pipeline(hass, msg.get("pipeline"))
        run = PipelineRun(
            hass, context=connection.context(msg), pipeline=pipeline,
            start_stage=PipelineStage(msg["start_stage"]), end_stage=PipelineStage.TTS,
            event_callback=pipeline_event,
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
        if capture_timer is not None:
            capture_timer.cancel()
        capture_call("abort")
        unregister()
        connection.subscriptions.pop(msg["id"], None)
        if task is not None and not task.done():
            task.cancel()
