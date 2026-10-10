"""
Lớp dùng chung cho Gemma 3 4B qua Ollama — dùng cho cả web (app.py) và bot Discord.

Cùng model, cùng prompt hệ thống và cùng hai chế độ: chat và mô tả ảnh.
"""

import os

MODEL = "gemma3:4b"

SYSTEM_PROMPT = (
    "Bạn là một trợ lý AI hữu ích, thân thiện. "
    "Luôn trả lời bằng tiếng Việt một cách tự nhiên, rõ ràng."
)

DEFAULT_IMAGE_PROMPT = "Mô tả ảnh này bằng tiếng Việt."

# Cho model dùng hết số core của máy để trả lời nhanh hơn.
NUM_THREAD = int(os.environ.get("LLM_NUM_THREADS", "4"))
MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "256"))


def model_installed():
    """Model đã có trong Ollama chưa (đã tải về máy)."""
    import ollama

    installed = {m.get("model", "") for m in ollama.list().get("models", [])}
    return any(name == MODEL or name.startswith(f"{MODEL}:") for name in installed)


def ensure_model(on_progress=None):
    """Tải model nếu chưa có. on_progress(percent) để báo tiến trình."""
    import ollama

    if model_installed():
        return
    for chunk in ollama.pull(MODEL, stream=True):
        total = chunk.get("total")
        completed = chunk.get("completed")
        if on_progress and total and completed:
            on_progress(completed * 100 // total)


def reply(message, history=None, image=None):
    """Gọi model. `image` là chuỗi base64 (không kèm tiền tố data:)."""
    import ollama

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history or []:
        messages.append({"role": h["role"], "content": h["content"]})

    content = (message or "").strip() or (DEFAULT_IMAGE_PROMPT if image else "")
    user_message = {"role": "user", "content": content}
    if image:
        user_message["images"] = [image]
    messages.append(user_message)

    resp = ollama.chat(
        model=MODEL,
        messages=messages,
        options={"num_thread": NUM_THREAD, "num_predict": MAX_TOKENS},
    )
    return resp["message"]["content"]
