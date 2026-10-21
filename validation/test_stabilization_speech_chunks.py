import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import types
import sys

spec = importlib.util.spec_from_file_location('speech_chunks', Path(__file__).resolve().parents[1] / 'deployment/cosyvoice_worker/speech_chunks.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SpeechChunkTests(unittest.TestCase):
    def test_long_answer_is_complete_and_ordered(self):
        text = ' '.join(f'Segment {i} arrives at its destination.' for i in range(40))
        chunks = module.speech_chunks(text)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(text, ' '.join(chunks))
        self.assertTrue(all(len(chunk) <= 320 for chunk in chunks))

    def test_short_answer_unchanged(self):
        self.assertEqual(['Request received.'], module.speech_chunks('Request received.'))

    def test_no_punctuation_keeps_all_words(self):
        text = ' '.join(['word'] * 400)
        self.assertEqual(text, ' '.join(module.speech_chunks(text)))

    def test_excess_rejected_not_silently_shortened(self):
        with self.assertRaises(ValueError):
            module.speech_chunks('word ' * 3000)

    def test_long_token_rejected(self):
        with self.assertRaises(ValueError):
            module.speech_chunks('x' * 400)

    def test_long_sentence_is_not_split_at_an_arbitrary_space(self):
        text=' '.join(['natural']*65)+'.'
        self.assertEqual(module.speech_chunks(text),[text])
        text=' '.join(['natural']*45)+', '+' '.join(['more']*70)+'.'
        chunks=module.speech_chunks(text)
        self.assertEqual(' '.join(chunks),text)
        self.assertTrue(all(chunk.endswith((',', '.', ';', ':', '!', '?')) for chunk in chunks))

    def test_overlong_unpunctuated_clause_rejected_not_split_mid_sentence(self):
        with self.assertRaisesRegex(ValueError,'complete-section'):
            module.speech_chunks('word '*500)


class WorkerContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_complete_audio_envelope_preserves_all_text(self):
        sent, spoken = [], []
        class Event:
            def __init__(self, header, data, payload=b''):
                self.type, self.data, self.payload = header['type'], data, payload
        async def write_event(writer, event):
            sent.append(event)
        class Engine:
            async def synthesize_stream(self, text):
                spoken.append(text)
                yield b'\0\0', 24000, 0.01
                self.assert_no_partial = not sent if len(spoken) == 1 else True
                if not self.assert_no_partial:
                    raise AssertionError('First chunk leaked before generation finished')
                yield b'\0\0', 24000, 0.02
        engine_module = types.ModuleType('cosyvoice_engine')
        engine_module.CosyVoiceConfig = object
        engine_module.CosyVoiceEngine = Engine
        protocol = types.ModuleType('protocol')
        protocol.Event, protocol.write_event, protocol.read_event = Event, write_event, None
        spec = importlib.util.spec_from_file_location('stabilization_worker', Path(__file__).resolve().parents[1] / 'deployment/cosyvoice_worker/server.py')
        worker_module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'cosyvoice_engine': engine_module, 'protocol': protocol, 'speech_chunks': module}):
            spec.loader.exec_module(worker_module)
        text = ' '.join(f'Flight {i} arrives safely.' for i in range(40))
        await worker_module.Worker(Engine()).synthesize(Event({'type': 'synthesize'}, {'text': text}), object())
        self.assertEqual(text, ' '.join(spoken))
        self.assertEqual(1, sum(event.type == 'audio-start' for event in sent))
        self.assertEqual(1, sum(event.type == 'audio-stop' for event in sent))
        self.assertEqual('audio-stop', sent[-1].type)

        class EmptyEngine:
            async def synthesize_stream(self, text):
                if False:
                    yield b'', 24000, 0
        sent.clear()
        with self.assertRaises(RuntimeError):
            await worker_module.Worker(EmptyEngine()).synthesize(Event({'type': 'synthesize'}, {'text': 'Hello.'}), object())
        self.assertFalse(any(event.type == 'audio-stop' for event in sent))

        class BrokenEngine:
            async def synthesize_stream(self, text):
                yield b'\0\0', 24000, .01
                raise RuntimeError('generation failed before chunk completed')
        sent.clear()
        with self.assertRaises(RuntimeError):
            await worker_module.Worker(BrokenEngine()).synthesize(Event({'type': 'synthesize'}, {'text': 'Hello.'}), object())
        self.assertEqual(sent, [])
