# Base44 Dev Environment

## Project Overview
A Python app that runs the GLM-4-9B-chat LLM locally via `llama-cpp-python` (CPU mode).
The original `run_glm4.py` is a CLI script; `app.py` wraps it in a FastAPI web server with a chat UI (`index.html`) for the preview.

## Setup
- Docker compose: `docker compose -f docker-compose.base44.yml up -d --build`
- The app runs on port 3000 (uvicorn with --reload for live code changes).
- The model (~5.25GB) is downloaded from Hugging Face on first run and cached in the `hf-cache` Docker volume.
- No external credentials needed — the HF model is public.

## Architecture
- `app.py` — FastAPI server; loads the model in a background thread on startup.
- `index.html` — Chat UI served at `/`; polls `/health` until the model is ready.
- `Dockerfile.base44` — Python 3.12 + build tools; installs deps from `requirements.txt`.
- `docker-compose.base44.yml` — Bind-mounts source, persists HF cache in a volume.

## Notes
- First startup takes several minutes (model download + load into RAM).
- CPU inference is slow (~2-5 tokens/sec); responses may take 30-60+ seconds.
- The model uses ~5.25GB RAM; the sandbox has 7.8GB total.
- If `requirements.txt` changes, rebuild: `docker compose -f docker-compose.base44.yml up -d --build`.
