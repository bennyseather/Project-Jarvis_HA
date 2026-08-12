import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "home_assistant" / "jarvis_ui" / "www" / "jarvis" / "jarvis-ui.js"


class M31VoiceActivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = UI.read_text(encoding="utf-8")

    def test_visual_voice_satellite_is_registered(self):
        self.assertIn("class JarvisVoiceSatelliteCard", self.script)
        self.assertIn('"jarvis-voice-satellite-card"', self.script)
        self.assertIn("static getConfigForm()", self.script)

    def test_satellite_uses_authenticated_assist_pipeline(self):
        self.assertIn('type: "assist_pipeline/run"', self.script)
        self.assertIn("this._hass.connection.subscribeMessage", self.script)
        self.assertIn("this._hass.connection.socket.send(packet)", self.script)
        self.assertNotIn("long_lived_access_token", self.script)
        self.assertNotIn("volume_multiplier:", self.script)

    def test_privacy_and_output_controls_are_present(self):
        self.assertIn("getUserMedia", self.script)
        self.assertIn("track.stop()", self.script)
        self.assertIn("Push to talk", self.script)
        self.assertIn("Enable wake word", self.script)
        self.assertIn('window.fetch.call(window, target, { credentials: "same-origin" })', self.script)
        self.assertIn("decodeAudioData", self.script)
        self.assertIn("source.onended", self.script)

    def test_command_audio_bypasses_gate_after_wake_detection(self):
        self.assertIn("this._wakeDetected = true", self.script)
        self.assertIn('this._mode !== "wake" || this._wakeDetected', self.script)

    def test_tts_event_formats_and_rearm_are_safe(self):
        self.assertIn("data.url || data.tts_output?.url", self.script)
        self.assertIn("Promise.resolve(this._ttsPromise).finally", self.script)

    def test_release_is_versioned(self):
        self.assertIn('const JARVIS_UI_VERSION = "0.36.2"', self.script)
        manifest = (ROOT / "home_assistant" / "custom_components" / "jarvis_conversation" / "manifest.json").read_text(encoding="utf-8")
        self.assertIn('"version": "0.30.0"', manifest)


if __name__ == "__main__":
    unittest.main()
