"""
Web chat cho Gemma 3 4B qua Ollama.

Đây là lớp giao diện web mỏng bọc quanh setup_gemma3.py: cùng model,
cùng prompt hệ thống, cùng hai chức năng (chat và mô tả ảnh).

Cách dùng (xem docker-compose.base44.yml):
    docker compose -f docker-compose.base44.yml up -d
"""

import os
import threading

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

MODEL = "gemma3:4b"

SYSTEM_PROMPT = (
    "Bạn là một trợ lý AI hữu ích, thân thiện. "
    "Luôn trả lời bằng tiếng Việt một cách tự nhiên, rõ ràng."
)

DEFAULT_IMAGE_PROMPT = "Mô tả ảnh này bằng tiếng Việt."

app = FastAPI()

model_status = "loading"
status_message = "Đang kiểm tra Ollama..."


def load_model():
    """Tải model trong nền để UI hiển thị được tiến trình (giống script gốc)."""
    global model_status, status_message
    try:
        import ollama

        status_message = "Đang kiểm tra model..."
        installed = {m.get("model", "") for m in ollama.list().get("models", [])}
        if not any(name == MODEL or name.startswith(f"{MODEL}:") for name in installed):
            status_message = "Đang tải gemma3:4b (khoảng 3.3 GB, chỉ tải một lần)..."
            for chunk in ollama.pull(MODEL, stream=True):
                total = chunk.get("total")
                completed = chunk.get("completed")
                if total and completed:
                    status_message = f"Đang tải gemma3:4b... {completed * 100 // total}%"

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

    import ollama

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in request.history:
        messages.append({"role": h.role, "content": h.content})

    content = request.message.strip() or (DEFAULT_IMAGE_PROMPT if request.image else "")
    user_message = {"role": "user", "content": content}
    if request.image:
        user_message["images"] = [request.image]
    messages.append(user_message)

    try:
        resp = ollama.chat(model=MODEL, messages=messages, options={"num_predict": 256})
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)}, status_code=502)

    return {"response": resp["message"]["content"]}


@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(os.path.dirname(__file__), "index.html"), encoding="utf-8") as f:
        return f.read()
