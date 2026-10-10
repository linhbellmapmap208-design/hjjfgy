"""
Tạo ảnh từ mô tả qua API công khai của Pollinations (miễn phí, không cần key).

Dịch vụ miễn phí này giới hạn số request của khách vãng lai nên hay trả
402/429; `generate()` tự thử lại vài lần trước khi bỏ cuộc.
"""

import os
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://image.pollinations.ai/prompt/"
SIZE = int(os.environ.get("IMAGE_SIZE", "768"))
UA = "teto-bot/1.1"
ATTEMPTS = int(os.environ.get("IMAGE_ATTEMPTS", "5"))
RETRY_DELAY = float(os.environ.get("IMAGE_RETRY_DELAY", "2.5"))


TOKEN = os.environ.get("POLLINATIONS_TOKEN", "").strip()


def _is_image(data):
    return data[:2] == b"\xff\xd8" or data[:8] == b"\x89PNG\r\n\x1a\n"


def generate(prompt, size=SIZE):
    """Trả về nội dung ảnh (bytes) cho câu mô tả `prompt`."""
    query = urllib.parse.urlencode({"width": size, "height": size, "nologo": "true"})
    url = f"{API}{urllib.parse.quote(prompt)}?{query}"

    headers = {"User-Agent": UA}
    if TOKEN:
        # Token miễn phí của Pollinations giúp hạn mức cao hơn nhiều.
        headers["Authorization"] = f"Bearer {TOKEN}"

    error = "không rõ"
    for attempt in range(ATTEMPTS):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=180) as response:
                data = response.read()
            if _is_image(data):
                return data
            error = "dịch vụ trả về dữ liệu không phải ảnh"
        except urllib.error.HTTPError as e:
            error = f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            error = str(e)

        if attempt < ATTEMPTS - 1:
            time.sleep(RETRY_DELAY)

    raise RuntimeError(f"Dịch vụ tạo ảnh miễn phí đang quá tải ({error}). Bạn thử lại sau vài giây nhé.")


def content_type(data):
    """Đoán kiểu ảnh từ magic bytes."""
    return "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
