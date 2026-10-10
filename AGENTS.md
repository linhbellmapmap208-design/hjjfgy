# AGENTS.md

## What this project is
A local **Gemma 3 4B chat assistant** built on **Ollama** (Vietnamese UI/logs).
- `setup_gemma3.py` — the original CLI entry point: pulls `gemma3:4b` and chats, or describes an image file.
- `app.py` + `index.html` — a thin web wrapper around the same model/prompt so the app can be used in the sandbox preview (same two capabilities: chat and image description).

## Running it (sandbox / docker compose)
```bash
docker compose -f docker-compose.base44.yml up -d --build
```
- `web` (FastAPI + the static chat page) is published on **host port 3000**; it binds `0.0.0.0:8000` inside the container.
- `ollama` is the model server (plain infra image), reachable by `web` at `OLLAMA_HOST=http://ollama:11434`.
- Dependencies are installed from `requirements.txt` on container start (pinned by the file, not baked into an image), then uvicorn runs with `--reload`.

## Non-obvious gotchas
- **First boot needs network and time.** `gemma3:4b` is ~3.3 GB and is downloaded on first run into the `ollama-models` docker volume (persists across restarts — do **not** delete it to "refresh" anything).
- The model pull happens in a **background thread** inside `app.py` (`load_model`); `/health` reports `loading` / `ready` / `error` and the UI shows download progress. The web service is therefore "up" before the model is usable.
- The model needs roughly 4 GB RAM for inference; CPU-only inference is slow, so replies can take a while.

## Verifying it works
```bash
curl -s localhost:3000/health                 # wait until {"status":"ready"}
curl -s -X POST localhost:3000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Xin chào, bạn là ai?"}'
```

## Secrets
None required — Ollama and the model run locally inside compose.

## Sandbox notes
- `BASE44_PREVIEW_MODE` is passed through to the `web` service but the app does not need it: it is a plain same-origin FastAPI app (no CORS/host allowlist config), and uvicorn binds `0.0.0.0`.
