"""Read-only localhost dashboard for persisted RQ4 runtime state."""
from __future__ import annotations

import html
import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from rq4_platform import RUNTIME_PATH, StateMachine, status


def dashboard_payload() -> dict:
    return status()


def render(payload: dict) -> str:
    runtime = payload.get("runtime", {})
    cards = "".join(f"<div class='card'><b>{html.escape(str(key))}</b><pre>{html.escape(json.dumps(value, ensure_ascii=False, indent=2))}</pre></div>" for key, value in runtime.items())
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta http-equiv='refresh' content='5'><title>RQ4 status</title><style>body{{font:15px system-ui;background:#f5f2e9;color:#18211b;max-width:1100px;margin:2rem auto}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}}.card{{background:white;padding:14px;border-radius:10px;box-shadow:0 1px 4px #bbb}}pre{{white-space:pre-wrap}}</style></head><body><h1>RQ4 STATUS</h1><p><b>Phase:</b> {html.escape(payload['state'])}</p><p>Read-only. The runner does not depend on this page.</p><div class='grid'>{cards or '<div class="card">No formal runtime has started.</div>'}</div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/state":
            body = json.dumps(dashboard_payload()).encode(); content_type = "application/json"
        else:
            body = render(dashboard_payload()).encode(); content_type = "text/html; charset=utf-8"
        self.send_response(200); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def log_message(self, *_):
        return


def available_port(start: int = 5600, attempts: int = 20) -> int:
    for port in range(start, start + attempts):
        with socket.socket() as probe:
            try: probe.bind(("127.0.0.1", port))
            except OSError: continue
            return port
    raise RuntimeError("NO_LOCAL_RQ4_DASHBOARD_PORT_AVAILABLE")


def serve() -> None:
    StateMachine().read()
    port = available_port()
    print(f"RQ4 read-only dashboard: http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    serve()
