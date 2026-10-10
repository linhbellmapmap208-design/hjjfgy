"""Đọc tệp người dùng gửi lên và tách tệp do model tạo ra."""

import io
import os
import re

MAX_CHARS = 20000

# Khối do model xuất ra để tạo tệp:  ```file:tên.txt\n nội dung \n```
FILE_BLOCK = re.compile(r"```file:([^\n`]+)\n(.*?)```", re.S)


def extract_text(filename, data):
    """Chuyển nội dung tệp thành text (txt/csv/md/json/code, PDF, DOCX)."""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif ext == ".docx":
        import docx

        text = "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)
    else:
        text = data.decode("utf-8", errors="replace")
    return text.strip()[:MAX_CHARS]


def extract_files(text):
    """Tách các khối ```file:tên ...``` khỏi câu trả lời.

    Trả về (câu trả lời đã bỏ khối, danh sách tệp [{name, content}]).
    """
    created = []

    def take(match):
        created.append({"name": match.group(1).strip(), "content": match.group(2).rstrip()})
        return ""

    return FILE_BLOCK.sub(take, text).strip(), created
