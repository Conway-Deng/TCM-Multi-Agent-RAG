from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException

from .store import FormalJobStore
from .worker_service import FormalReplayWorker, resident_memory_mb


store = FormalJobStore()
worker = FormalReplayWorker(store)
_wake = threading.Event()
_stop = threading.Event()
_thread: threading.Thread | None = None


def _worker_loop() -> None:
    retention_days = max(1, int(os.getenv("FORMAL_REPLAY_RETENTION_DAYS", "30")))
    store.cleanup_old_replays(retention_days)
    while not _stop.is_set():
        _wake.wait(timeout=60)
        _wake.clear()
        if _stop.is_set():
            break
        worker.run_until_idle()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _thread
    store.initialize()
    _stop.clear()
    _wake.set()  # Reclaim queued/expired jobs immediately after a cold start.
    _thread = threading.Thread(target=_worker_loop, name="experiment-worker-loop", daemon=True)
    _thread.start()
    yield
    _stop.set()
    _wake.set()
    if _thread is not None:
        _thread.join(timeout=5)
    try:
        from providers.openai_compatible import OpenAICompatibleLLMProvider
        await OpenAICompatibleLLMProvider.close_shared_http_client()
    finally:
        store.close()


app = FastAPI(title="TCM Experiment Worker", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, object]:
    queue = store.queue_summary()
    return {
        "status": "ok",
        "service": "TCM Experiment Worker",
        "single_concurrency": True,
        "active_run_id": worker.active_run_id,
        "queued_jobs": queue["queued"],
        "running_jobs": queue["running"],
        "rss_mb": resident_memory_mb(),
        "peak_rss_mb": worker.peak_rss_mb,
        "persistence": "FORMAL_DATABASE_URL",
    }


@app.post("/wake", status_code=202)
async def wake(x_worker_wake_token: str | None = Header(default=None)) -> dict[str, object]:
    expected = os.getenv("FORMAL_WORKER_WAKE_TOKEN", "").strip()
    if expected and x_worker_wake_token != expected:
        raise HTTPException(status_code=401, detail="Invalid worker wake token")
    _wake.set()
    return {"status": "accepted", "active_run_id": worker.active_run_id}


def main() -> None:
    import uvicorn

    uvicorn.run(
        "formal_experiments.worker_web:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "10000")),
        workers=1,
    )


if __name__ == "__main__":
    main()
