from __future__ import annotations

import json
import csv
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = ROOT / "benchmark_v1.jsonl"
DECISIONS_PATH = ROOT / "human_review.json"
HOST = "127.0.0.1"
PORT = 8765


def load_benchmark() -> list[dict]:
    questions = [json.loads(line) for line in BENCHMARK_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    review_rows = list(csv.DictReader((ROOT / "review_sheet.csv").open(encoding="utf-8-sig")))
    sources: dict[tuple[str, str], str] = {(row["question_id"], row["gold_fact"]): row["source"] for row in review_rows}
    for question in questions:
        for fact in question.get("gold_facts", []):
            fact["source"] = sources.get((question["question_id"], fact["fact"]), "Corpus v1")
    return questions


def load_decisions() -> dict:
    if not DECISIONS_PATH.exists():
        return {"version": 1, "decisions": {}}
    return json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/benchmark":
            self._json({"questions": load_benchmark()})
            return
        if path == "/api/review":
            self._json(load_decisions())
            return
        if path in {"/", "/index.html"}:
            self._serve(ROOT / "reviewer" / "index.html")
            return
        if path == "/reviewer.js":
            self._serve(ROOT / "reviewer" / "reviewer.js", "text/javascript; charset=utf-8")
            return
        if path == "/reviewer.css":
            self._serve(ROOT / "reviewer" / "reviewer.css", "text/css; charset=utf-8")
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/review":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            question_id = payload["question_id"]
            valid_ids = {item["question_id"] for item in load_benchmark()}
            if question_id not in valid_ids:
                self._json({"error": "unknown question_id"}, 400)
                return
            status = payload.get("review_status", "UNREVIEWED")
            if status not in {"UNREVIEWED", "APPROVED", "REVISE", "REMOVE"}:
                self._json({"error": "invalid review_status"}, 400)
                return
            decisions = load_decisions()
            decisions.setdefault("version", 1)
            decisions.setdefault("decisions", {})
            decisions["decisions"][question_id] = {
                "question_id": question_id,
                "review_status": status,
                "fact_statuses": payload.get("fact_statuses", {}),
                "review_notes": str(payload.get("review_notes", "")),
                "review_timestamp": payload.get("review_timestamp"),
            }
            DECISIONS_PATH.write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._json({"ok": True, "decision": decisions["decisions"][question_id]})
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, 400)

    def _serve(self, path: Path, content_type: str = "text/html; charset=utf-8") -> None:
        if not path.exists():
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


if __name__ == "__main__":
    print(f"TCM Gold Benchmark reviewer: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
