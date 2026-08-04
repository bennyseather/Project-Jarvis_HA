"""Local-only browser review for M39 clips and Whisper transcripts."""

from __future__ import annotations

import argparse
import csv
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def save_rows(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def write_accepted_metadata(path: Path, rows: list[dict[str, str]]) -> int:
    accepted = [row for row in rows if row["review_status"] == "accepted"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="|")
        for row in accepted:
            writer.writerow((row["file"], row["text"].strip()))
    return len(accepted)


def page(row: dict[str, str], index: int, total: int, counts: dict[str, int]) -> bytes:
    status = row["review_status"]
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>M39 dataset review</title>
<style>
body{{font:16px system-ui;background:#06141d;color:#d7f7ff;max-width:900px;margin:30px auto}}
main{{border:1px solid #00bde7;padding:24px;background:#071c28}}
textarea{{width:100%;min-height:120px;background:#031018;color:white;border:1px solid #168ba5;padding:12px}}
button,a{{background:#0dbbe8;color:#001018;border:0;padding:10px 16px;margin:8px 4px;text-decoration:none}}
.reject{{background:#8d4960;color:white}} code{{color:#5eeaff}}
</style></head><body><main>
<h1>M39 voice dataset review</h1>
<p>Clip {index + 1} of {total} — accepted {counts.get('accepted', 0)}, rejected {counts.get('rejected', 0)}, pending {counts.get('needs_review', 0)}</p>
<p><code>{escape(row['source'])} @ {escape(row['start'])}s — {escape(row['file'])}</code></p>
<audio controls autoplay src="/audio/{escape(row['file'])}"></audio>
<form method="post" action="/review/{index}">
<textarea name="text">{escape(row['text'])}</textarea><br>
<button name="status" value="accepted">Accept corrected clip</button>
<button class="reject" name="status" value="rejected">Reject clip</button>
</form>
<p><a href="/review/{max(0, index-1)}">Previous</a><a href="/review/{min(total-1, index+1)}">Next</a></p>
<p>Current status: <strong>{escape(status)}</strong>. Reject music, applause, another speaker, effects, bad cuts, or unclear words.</p>
</main></body></html>"""
    return html.encode("utf-8")


def handler_factory(dataset: Path):
    review_path = dataset / "review.csv"
    audio_dir = dataset / "wav"

    class ReviewHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path.startswith("/audio/"):
                name = Path(parsed.path.removeprefix("/audio/")).name
                audio = audio_dir / name
                if not audio.is_file():
                    self.send_error(404)
                    return
                payload = audio.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            rows = load_rows(review_path)
            if not rows:
                self.send_error(404, "No review rows")
                return
            try:
                index = int(parsed.path.rsplit("/", 1)[-1]) if parsed.path.startswith("/review/") else 0
            except ValueError:
                index = 0
            index = max(0, min(len(rows) - 1, index))
            counts: dict[str, int] = {}
            for row in rows:
                counts[row["review_status"]] = counts.get(row["review_status"], 0) + 1
            payload = page(rows[index], index, len(rows), counts)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            if not self.path.startswith("/review/"):
                self.send_error(404)
                return
            rows = load_rows(review_path)
            index = max(0, min(len(rows) - 1, int(self.path.rsplit("/", 1)[-1])))
            length = int(self.headers.get("Content-Length", "0"))
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            status = form.get("status", ["needs_review"])[0]
            if status not in {"accepted", "rejected"}:
                self.send_error(400, "Invalid review status")
                return
            rows[index]["text"] = form.get("text", [rows[index]["text"]])[0].strip()
            rows[index]["review_status"] = status
            save_rows(review_path, rows)
            accepted = write_accepted_metadata(dataset / "metadata.accepted.csv", rows)
            (dataset / "review-summary.json").write_text(json.dumps({
                "accepted": accepted,
                "rejected": sum(row["review_status"] == "rejected" for row in rows),
                "pending": sum(row["review_status"] == "needs_review" for row in rows),
            }, indent=2), encoding="utf-8")
            next_index = min(len(rows) - 1, index + 1)
            self.send_response(303)
            self.send_header("Location", f"/review/{next_index}")
            self.end_headers()

        def log_message(self, _format, *_arguments):
            return

    return ReviewHandler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()
    server = ThreadingHTTPServer(
        ("127.0.0.1", arguments.port), handler_factory(arguments.dataset)
    )
    print(f"Review M39 locally at http://127.0.0.1:{arguments.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
