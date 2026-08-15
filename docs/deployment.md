# Deployment readiness

The static frontend is Vercel-compatible and degrades gracefully when the backend is offline. Set `window.MEDIRAG_API_BASE_URL` before loading `research-app.js` for production.

The backend is not deployed by this task. Future deployment requires Python 3.11+, `backend/requirements.txt`, `uvicorn main:app --app-dir backend --host 0.0.0.0 --port $PORT`, `/health`, explicit CORS, and server-side credentials. Copy `.env.example` locally and never commit `.env`.

SiliconFlow uses OpenAI-compatible variables. Local embedding, rerank, and vector-store providers remain default. Qdrant is optional/future-ready. Browser JavaScript never contains server keys.
