"""
Cài và thử Gemma 3 4B qua Ollama.

Cách dùng:
    python setup_gemma3.py                  # tải model và chat thử
    python setup_gemma3.py anh.jpg          # tải model và mô tả ảnh anh.jpg
"""

import shutil
import subprocess
import sys

MODEL = "gemma3:4b"


def check_ollama():
    if shutil.which("ollama") is None:
        print("Chưa tìm thấy Ollama.")
        print("Tải và cài tại: https://ollama.com/download")
        print("Sau khi cài xong, mở lại terminal rồi chạy script này lần nữa.")
        sys.exit(1)


def pull_model():
    print(f"Đang tải {MODEL} (khoảng 3.3 GB, chỉ tải một lần)...")
    subprocess.run(["ollama", "pull", MODEL], check=True)
    print("Tải xong.")


def quick_test():
    print("\nThử chat với model:")
    subprocess.run(
        ["ollama", "run", MODEL, "Xin chào, bạn là ai? Trả lời ngắn gọn."],
        check=True,
    )


def describe_image(path):
    try:
        import ollama
    except ImportError:
        print("Cần cài thư viện trước: pip install ollama")
        sys.exit(1)

    resp = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": "Mô tả ảnh này bằng tiếng Việt.", "images": [path]}],
    )
    print(resp["message"]["content"])


def main():
    check_ollama()
    pull_model()
    if len(sys.argv) > 1:
        describe_image(sys.argv[1])
    else:
        quick_test()


if __name__ == "__main__":
    main()
