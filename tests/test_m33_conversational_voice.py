import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "home_assistant" / "jarvis_ui" / "www" / "jarvis" / "jarvis-ui.js").read_text(encoding="utf-8")


class M33ConversationalVoiceTests(unittest.TestCase):
    def test_editor_exposes_bounded_dialogue_controls(self):
        self.assertIn('{ name: "conversational_mode", selector: { boolean: {} } }', SCRIPT)
        self.assertIn('follow_up_timeout", selector: { number: { min: 3, max: 20', SCRIPT)
        self.assertIn('max_dialogue_turns", selector: { number: { min: 1, max: 5', SCRIPT)

    def test_followups_reuse_pipeline_and_conversation(self):
        self.assertIn('if (this._conversationId) message.conversation_id', SCRIPT)
        self.assertIn('this._runPipeline(continueDialogue)', SCRIPT)
        self.assertIn('const startStage = followUp ? "stt"', SCRIPT)

    def test_dialogue_is_bounded_and_returns_to_wake_word(self):
        self.assertIn('this._dialogueTurns < maximum', SCRIPT)
        self.assertIn('Number(this._config.follow_up_timeout || 7) * 1000', SCRIPT)
        self.assertIn('Follow-up timed out // rearming wake word', SCRIPT)
        self.assertIn('this._pipelineGeneration += 1', SCRIPT)

    def test_exit_phrases_and_playback_order_are_explicit(self):
        self.assertIn('"stop listening"', SCRIPT)
        self.assertIn('"thats all"', SCRIPT)
        self.assertIn('Promise.resolve(this._ttsPromise).finally', SCRIPT)
        self.assertIn('this._followUpMode', SCRIPT)

    def test_wake_word_starts_a_fresh_dialogue(self):
        wake_word_branch = SCRIPT.split('type === "wake_word-end"', 1)[1].split("else if", 1)[0]
        self.assertIn("this._dialogueTurns = 0", wake_word_branch)
        self.assertIn("this._endDialogue = false", wake_word_branch)


if __name__ == "__main__":
    unittest.main()
