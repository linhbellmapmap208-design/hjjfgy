"""
Web chat cho Gemma 3 4B qua Ollama.

Các chế độ: chat, đọc ảnh, đọc tệp (pdf/docx/text) và tạo tệp.
Tạo ảnh đi qua `imagegen.py` vì Gemma 3 không tự vẽ được ảnh.

Lớp model dùng chung với bot Discord nằm trong llm.py.

Cách dùng (xem docker-compose.base44.yml):
    docker compose -f docker-compose.base44.yml up -d
"""

import base64
import os
import threading

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

import files
import imagegen
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


class Attachment(BaseModel):
    name: str
    data: str  # base64


class ChatRequest(BaseModel):
    message: str = ""
    history: list[ChatMessage] = []
    image: str | None = None  # ảnh dạng base64 (không kèm tiền tố data:)
    files: list[Attachment] = []


class ImageRequest(BaseModel):
    prompt: str


@app.post("/api/chat")
async def chat(request: ChatRequest):
    if model_status != "ready":
        return JSONResponse(
            {"error": "Model chưa sẵn sàng", "status": model_status, "message": status_message},
            status_code=503,
        )

    context = []
    for attachment in request.files:
        try:
            text = files.extract_text(attachment.name, base64.b64decode(attachment.data))
            context.append(f"[Nội dung tệp {attachment.name}]\n{text}")
        except Exception as e:  # noqa: BLE001
            context.append(f"[Không đọc được tệp {attachment.name}: {e}]")

    message = "\n\n".join(context + [request.message]) if context else request.message
    history = [{"role": h.role, "content": h.content} for h in request.history]
    try:
        answer = llm.reply(message, history, request.image)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)}, status_code=502)

    answer, created = files.extract_files(answer)
    return {"response": answer, "files": created}


@app.post("/api/image")
async def create_image(request: ImageRequest):
    if not request.prompt.strip():
        return JSONResponse({"error": "Thiếu mô tả ảnh"}, status_code=400)
    try:
        data = imagegen.generate(request.prompt.strip())
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)}, status_code=502)
    return Response(content=data, media_type=imagegen.content_type(data))


@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(os.path.dirname(__file__), "index.html"), encoding="utf-8") as f:
        return f.read()
