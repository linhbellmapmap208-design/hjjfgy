# AGENTS.md

## What this project is
A local **Gemma 3 4B assistant** built on **Ollama** (Vietnamese UI/logs), used from a web page and a Discord bot.
- `setup_gemma3.py` — the original CLI entry point: pulls `gemma3:4b` and chats, or describes an image file.
- `llm.py` — shared model layer (model name, system prompt, model download, `reply()`). Used by both surfaces.
- `imagegen.py` — **image generation** via a public free API (Pollinations, no API key). Gemma 3 is vision-input only and cannot draw.
- `files.py` — reads uploaded files (txt/csv/md/json/code, PDF, DOCX) and splits AI-created files out of a reply.
- `app.py` + `index.html` — web chat: text, image (vision), file upload, image generation, AI-created file downloads.
- `discord_bot.py` — Discord bot: mention `@bot` to chat; first mention gets a friendly greeting with a cat-image template; "vẽ ..." generates an image; attachments are read (image or document); the AI can hand back files.

## Running it (sandbox / docker compose)
```bash
docker compose -f docker-compose.base44.yml up -d --build
```
- `web` (FastAPI + the static chat page) is published on **host port 3000**; it binds `0.0.0.0:8000` inside the container.
- `bot` runs `discord_bot.py` (long-running Discord gateway client).
- `ollama` is the model server (plain infra image), reachable by the other services at `OLLAMA_HOST=http://ollama:11434`.
- Dependencies are installed from `requirements.txt` on container start (pinned by the file, not baked into an image), then the dev command runs (`--reload` for the web app). **After changing `requirements.txt`, restart the app containers** — the install only runs at container start (`docker compose -f docker-compose.base44.yml restart web bot`).

## How the AI "creates files"
There is no tool-calling: `llm.py`'s system prompt asks the model to emit the file body in a fenced block headed
```` ```file:name.txt ````. `files.extract_files()` strips those blocks out of the reply and both surfaces deliver them
(download link on the web, `discord.File` attachment in Discord). If the model ignores the convention, no file is produced —
check the reply text before assuming delivery works.

## Non-obvious gotchas
- **First boot needs network and time.** `gemma3:4b` is ~3.3 GB and is downloaded on first run into the `ollama-models` docker volume (persists across restarts — do **not** delete it to "refresh" anything).
- The web app pulls the model in a **background thread** (`load_model` in `app.py`); `/health` reports `loading` / `ready` / `error` and the UI shows download progress. `discord_bot.py` also calls `llm.ensure_model()` on login, so whichever starts first downloads it once (they share the same volume).
- **Memory is the binding constraint.** The loaded LLM alone holds ~4.4 GB of the 7.8 GB VM, and there is **no swap**. Do not add a resident local diffusion model — image generation is delegated to the external API partly for this reason.
- The model needs roughly 4 GB RAM for inference; CPU-only inference is slow, so replies take a while (~5-15 s, longer for images).
- **CPU speed settings:** `OLLAMA_NUM_PARALLEL=1` (a single request gets all 4 cores instead of splitting threads across parallel slots), `OLLAMA_KEEP_ALIVE=-1` (keeps the model loaded so later replies skip the load), and `LLM_NUM_THREADS=4` → passed as Ollama's `num_thread` option in `llm.py`. Do not add a CPU quota to the `ollama` service or it can no longer use all 4 cores.
- Discord's edge blocks requests that use Python's default `urllib` user agent (`403 error code: 1010`). Both the `bot` healthcheck and `imagegen.py` therefore send a `User-Agent` header. The Pollinations image API requires it too.
- Image generation goes through a **third-party free service** (Pollinations) because the VM has no GPU. Its **anonymous tier is aggressively rate-limited** — `402 Payment Required` on most requests; `imagegen.generate()` retries 5× (`IMAGE_ATTEMPTS` / `IMAGE_RETRY_DELAY`) but a burst of failures is normal without a token. Setting `POLLINATIONS_TOKEN` (free, from pollinations.ai — sent as `Authorization: Bearer`) restores reliable generation. Report failures to the user instead of silently swallowing them.
- **Discord needs "Message Content Intent" turned ON** (Developer Portal → your app → Bot → Privileged Gateway Intents). Without it Discord refuses the gateway connection — the bot logs the exact hint and exits instead of crash-looping.
- The `bot` service reads its credentials from the platform-managed env file `/run/base44/app.env` (last `env_file` entry; no secrets are ever written into the repo or compose `environment:`).

## Verifying it works
```bash
curl -s localhost:3000/health                 # wait until {"status":"ready"}
curl -s -X POST localhost:3000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Xin chào, bạn là ai?"}'
curl -s -X POST localhost:3000/api/image \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"a cute white persian cat"}' -o /tmp/a.jpg && ls -l /tmp/a.jpg
docker compose -f docker-compose.base44.yml logs bot --tail 20   # login + model ready
```
Presence of a secret (never print its value):
```bash
docker compose -f docker-compose.base44.yml exec -T bot sh -c 'printenv DISCORD_BOT_TOKEN >/dev/null && echo present || echo missing'
```

## Secrets
- `DISCORD_BOT_TOKEN` — the bot's token (required for the bot; the web app runs without it).
- `DISCORD_GUILD_ID` — optional; when set the bot only answers in that server.
- `POLLINATIONS_TOKEN` — optional; free token that lifts the image API's anonymous rate limit (without it image creation is best-effort and often 402s).
All are delivered by the platform to `/run/base44/app.env` (wired into both `web` and `bot`). Ollama and the model need no credentials.

## Sandbox notes
- `BASE44_PREVIEW_MODE` is passed through to the `web` service but the app does not need it: it is a plain same-origin FastAPI app (no CORS/host allowlist config), and uvicorn binds `0.0.0.0`.
