import csv
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from prepare_m39_voice_dataset import clean_transcript, normalize_clip  # noqa: E402
from review_m39_voice_dataset import (  # noqa: E402
    load_rows,
    save_rows,
    write_accepted_metadata,
)
from package_m39_voice_dataset import package  # noqa: E402


class M39VoiceDatasetTests(unittest.TestCase):
    def test_transcript_and_audio_normalization_are_bounded(self):
        import numpy as np

        self.assertEqual(clean_transcript("  Systems   ready. "), "Systems ready.")
        samples = np.array([-0.9, 0.0, 0.9], dtype=np.float32)
        normalized = normalize_clip(samples)
        self.assertLessEqual(float(abs(normalized).max()), 1.0)
        self.assertEqual(normalized.dtype, np.float32)

    def test_review_round_trip_and_accepted_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review = root / "review.csv"
            rows = [
                {"file": "one.wav", "text": "One.", "review_status": "accepted"},
                {"file": "two.wav", "text": "Two.", "review_status": "rejected"},
            ]
            save_rows(review, rows)
            self.assertEqual(load_rows(review), rows)
            accepted = root / "metadata.accepted.csv"
            self.assertEqual(write_accepted_metadata(accepted, rows), 1)
            with accepted.open(encoding="utf-8", newline="") as handle:
                self.assertEqual(list(csv.reader(handle, delimiter="|")), [["one.wav", "One."]])

    def test_private_outputs_are_ignored(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/training/m39_dataset/", ignore)
        self.assertIn("/training/m39_models/", ignore)

    def test_colab_notebook_contains_reproducible_runtime_fixes(self):
        import json

        notebook = json.loads(
            (ROOT / "training" / "m39" / "M39_Piper_Training.ipynb").read_text(
                encoding="utf-8"
            )
        )
        code = "\n".join(
            "".join(cell.get("source", []))
            for cell in notebook["cells"] if cell.get("cell_type") == "code"
        )
        self.assertIn("scikit-build", code)
        self.assertIn("onnxscript", code)
        self.assertIn("setup.py', 'build_ext', '--inplace", code)
        self.assertIn("checkpoint['epoch'] = 0", code)
        self.assertIn("'--data.espeak_voice', 'en'", code)
        self.assertIn("'--weights_only', 'true'", code)
        self.assertIn("environment['PYTHONUNBUFFERED'] = '1'", code)
        self.assertIn("dynamo=False", code)

    def test_package_contains_only_accepted_clips(self):
        import json
        import zipfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "wav").mkdir()
            (root / "wav" / "one.wav").write_bytes(b"accepted")
            (root / "wav" / "two.wav").write_bytes(b"rejected")
            save_rows(root / "review.csv", [
                {"file": "one.wav", "text": "One.", "duration": "2.0", "review_status": "accepted"},
                {"file": "two.wav", "text": "Two.", "duration": "3.0", "review_status": "rejected"},
            ])
            destination = root / "dataset.zip"
            card = package(root, destination)
            self.assertEqual(card["clip_count"], 1)
            with zipfile.ZipFile(destination) as archive:
                self.assertIn("wav/one.wav", archive.namelist())
                self.assertNotIn("wav/two.wav", archive.namelist())
                stored = json.loads(archive.read("DATASET_CARD.json"))
                self.assertTrue(stored["manual_review_complete"])


if __name__ == "__main__":
    unittest.main()
