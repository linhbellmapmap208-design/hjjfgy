from huggingface_hub import hf_hub_download
from llama_cpp import Llama

REPO_ID = "legraphista/glm-4-9b-chat-IMat-GGUF"
FILENAME = "glm-4-9b-chat.IQ4_XS.gguf"

# Lần đầu sẽ tải khoảng 5.25GB, các lần sau dùng cache
model_path = hf_hub_download(repo_id=REPO_ID, filename=FILENAME)

llm = Llama(
    model_path=model_path,
    n_ctx=4096,
    n_gpu_layers=0,  # đổi thành -1 nếu build llama-cpp-python có GPU
    verbose=False,
)

out = llm.create_chat_completion(
    messages=[{"role": "user", "content": "Xin chào, bạn là ai?"}],
    max_tokens=256,
)
print(out["choices"][0]["message"]["content"])
