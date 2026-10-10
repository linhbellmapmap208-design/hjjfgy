"""
Web chat cho Gemma 3 4B qua Ollama.

Lớp model dùng chung (với bot Discord) nằm trong llm.py: cùng model,
cùng prompt hệ thống, cùng hai chức năng (chat và mô tả ảnh).

Cách dùng (xem docker-compose.base44.yml):
    docker compose -f docker-compose.base44.yml up -d
"""

import os
import threading

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

import llm

app = FastAPI()

model_status = "loading"
status_message = "Đang kiểm tra Ollama..."


def load_model():
    """Tải model trong nền để UI hiển thị được tiến trình (giống script gốc)."""
    global model_status, status_message

    def on_progress(percent):
        global status_message
        status_message = f"Đang tải gemma3:4b... {percent}%"

    try:
        status_message = "Đang kiểm tra model..."
        if not llm.model_installed():
            status_message = "Đang tải gemma3:4b (khoảng 3.3 GB, chỉ tải một lần)..."
        llm.ensure_model(on_progress=on_progress)
        model_status = "ready"
        status_message = "Model sẵn sàng"
    except Exception as e:  # noqa: BLE001
        model_status = "error"
        status_message = str(e)


@app.on_event("startup")
async def startup_event():
    threading.Thread(target=load_model, daemon=True).start()


@app.get("/health")
async def health():
    return {"status": model_status, "message": status_message}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = ""
    history: list[ChatMessage] = []
    image: str | None = None  # ảnh dạng base64 (không kèm tiền tố data:)


@app.post("/api/chat")
async def chat(request: ChatRequest):
    if model_status != "ready":
        return JSONResponse(
            {"error": "Model chưa sẵn sàng", "status": model_status, "message": status_message},
            status_code=503,
        )

    history = [{"role": h.role, "content": h.content} for h in request.history]
    try:
        answer = llm.reply(request.message, history, request.image)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)}, status_code=502)

    return {"response": answer}


@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(os.path.dirname(__file__), "index.html"), encoding="utf-8") as f:
        return f.read()
