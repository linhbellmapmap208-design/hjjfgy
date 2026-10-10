import os
import threading
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI()

REPO_ID = "legraphista/glm-4-9b-chat-IMat-GGUF"
FILENAME = "glm-4-9b-chat.IQ4_XS.gguf"

SYSTEM_PROMPT = (
    "Bạn là một trợ lý AI hữu ích, thân thiện. "
    "Luôn trả lời bằng tiếng Việt một cách tự nhiên, rõ ràng."
)

llm = None
model_status = "loading"
status_message = "Starting..."


def load_model():
    global llm, model_status, status_message
    try:
        from huggingface_hub import hf_hub_download
        from llama_cpp import Llama

        status_message = "Downloading model (~5.25GB, first run only)..."
        model_path = hf_hub_download(repo_id=REPO_ID, filename=FILENAME)

        status_message = "Loading model into memory..."
        llm = Llama(
            model_path=model_path,
            n_ctx=2048,
            n_gpu_layers=0,
            n_threads=4,
            verbose=False,
        )

        model_status = "ready"
        status_message = "Model ready"
    except Exception as e:
        model_status = "error"
        status_message = str(e)


@app.on_event("startup")
async def startup_event():
    # Khởi động model loading trong background
    thread = threading.Thread(target=load_model, daemon=True)
    thread.start()
    # Khởi động Discord bot trong background
    from discord_bot import start_bot
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()


@app.get("/health")
async def health():
    return {"status": model_status, "message": status_message}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


@app.post("/chat")
async def chat(request: ChatRequest):
    if model_status != "ready" or llm is None:
        return JSONResponse(
            {"error": "Model is not ready", "status": model_status, "message": status_message},
            status_code=503,
        )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in request.history:
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": request.message})

    response = llm.create_chat_completion(
        messages=messages,
        max_tokens=128,
    )

    return {"response": response["choices"][0]["message"]["content"]}


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path) as f:
        return f.read()
