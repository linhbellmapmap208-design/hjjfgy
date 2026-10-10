"""
Bot Discord cho Gemma 3 4B (dùng chung model với web qua llm.py).

Cách hoạt động:
    - Mention @bot kèm câu hỏi để bot trả lời.
    - Lần đầu một người mention, bot gửi lời chào thân thiện kèm mẫu tạo ảnh mèo.
    - "vẽ ..." (hoặc trả lời mẫu ở trên) -> bot tạo ảnh và gửi thẳng vào kênh.
    - Gửi kèm ảnh -> bot mô tả ảnh; gửi kèm tệp (pdf/docx/txt...) -> bot đọc nội dung.
    - Yêu cầu tạo tệp -> bot gửi tệp đính kèm.

Cấu hình (biến môi trường, xem docker-compose.base44.yml):
    DISCORD_BOT_TOKEN  bắt buộc — token của bot
    DISCORD_GUILD_ID   tuỳ chọn — nếu đặt, bot chỉ trả lời trong server này
"""

import asyncio
import base64
import io
import os

import discord

import files
import imagegen
import llm

TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "").strip()

MAX_HISTORY = int(os.environ.get("DISCORD_MAX_HISTORY", "10"))
MAX_LEN = 2000  # giới hạn tin nhắn của Discord

GREETING = (
    "Chào bạn, mình là trợ lý AI của server 😊\n"
    "Mình có thể trò chuyện, đọc ảnh/tệp bạn gửi, tạo ảnh và tạo tệp cho bạn.\n\n"
    "Thử tạo ảnh mèo nhé — bạn cho mình vài thông tin:\n"
    "• Loại mèo: (Mèo Ba Tư, mèo Anh lông dài, mèo Xiêm, mèo hoang...)\n"
    "• Màu lông: (Trắng, đen, xám, vằn đen, tam thể...)\n"
    "• Biểu cảm: (Vui vẻ, ngộ nghĩnh, buồn bã...)\n"
    "• Hành động: (Ngủ, chơi, ăn...)\n\n"
    "Nếu bạn không có yêu cầu cụ thể, mình sẽ tạo một con mèo dễ thương nhé! 😊"
)

IMAGE_KEYWORDS = ("vẽ", "tạo ảnh", "tạo hình", "sinh ảnh", "generate image", "draw ")
GREETING_WORDS = {"hi", "hello", "hey", "alo", "chào", "chào bạn", "xin chào", "hú", "test"}

intents = discord.Intents.default()
intents.message_content = True  # cần bật "Message Content Intent" trong Discord Developer Portal

client = discord.Client(intents=intents)
history = {}  # channel_id -> [{role, content}]
greeted = set()  # user_id đã nhận lời chào
awaiting_image = set()  # user_id đang chờ mô tả ảnh (sau lời chào)


def stripped_question(message):
    """Bỏ phần mention @bot, giữ lại câu hỏi."""
    text = message.content
    for mention in message.mentions:
        text = text.replace(f"<@{mention.id}>", " ").replace(f"<@!{mention.id}>", " ")
    return text.strip()


async def attachments_of(message):
    """Trả về (ảnh base64 đầu tiên, [(tên tệp, base64)] cho các tệp còn lại)."""
    image = None
    documents = []
    for attachment in message.attachments:
        content_type = attachment.content_type or ""
        if content_type.startswith("image/") and image is None:
            image = base64.b64encode(await attachment.read()).decode()
        elif not content_type.startswith("image/"):
            documents.append((attachment.filename, base64.b64encode(await attachment.read()).decode()))
    return image, documents


def chunks(text, size=MAX_LEN):
    parts = [text[i : i + size] for i in range(0, len(text), size)]
    return parts or [""]


def read_documents(documents):
    """Đọc nội dung các tệp đính kèm thành phần ngữ cảnh."""
    context = []
    for name, data in documents:
        try:
            text = files.extract_text(name, base64.b64decode(data))
            context.append(f"[Nội dung tệp {name}]\n{text}")
        except Exception as e:  # noqa: BLE001
            context.append(f"[Không đọc được tệp {name}: {e}]")
    return context


@client.event
async def on_ready():
    print(f"Đã đăng nhập: {client.user} (server: {GUILD_ID or 'tất cả'})", flush=True)
    try:
        print("Đang kiểm tra model...", flush=True)
        await asyncio.to_thread(llm.ensure_model)
        print("Model sẵn sàng.", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"Không tải được model: {e}", flush=True)


async def send_created_files(message, created):
    for item in created:
        await message.reply(
            f"Tệp **{item['name']}** của bạn đây 👇",
            file=discord.File(io.BytesIO(item["content"].encode()), filename=item["name"]),
        )


async def send_image(message, prompt):
    """Tạo ảnh và gửi vào kênh."""
    placeholder = await message.reply(f"Đang tạo ảnh: **{prompt}** ... 🎨")
    try:
        data = await asyncio.to_thread(imagegen.generate, prompt)
    except Exception as e:  # noqa: BLE001
        await placeholder.edit(content=f"Không tạo được ảnh: {e}")
        return
    await placeholder.edit(
        content=(
            f"Ảnh **{prompt}** của bạn đây ✨\n"
            "Bạn thấy thế nào? Muốn chỉnh gì thêm (góc chụp, thêm chi tiết...) cứ nói mình nhé 😊"
        ),
        attachments=[discord.File(io.BytesIO(data), filename="anh.jpg")],
    )


@client.event
async def on_message(message):
    if message.author.bot or client.user not in message.mentions:
        return
    if GUILD_ID and str(getattr(message.guild, "id", "")) != GUILD_ID:
        return

    question = stripped_question(message)
    image, documents = await attachments_of(message)

    if message.author.id not in greeted:
        greeted.add(message.author.id)
        await message.reply(GREETING)
        if not question or question.lower().strip(" !.,") in GREETING_WORDS:
            awaiting_image.add(message.author.id)
            return

    wants_image = message.author.id in awaiting_image and image is None and not documents
    wants_image = wants_image or any(k in question.lower() for k in IMAGE_KEYWORDS)
    if wants_image:
        awaiting_image.discard(message.author.id)
        await send_image(message, question or "một con mèo dễ thương")
        return

    if not question and image is None and not documents:
        await message.reply("Bạn hãy nhập câu hỏi, hoặc gửi kèm ảnh/tệp nhé.")
        return

    context = read_documents(documents)
    prompt = "\n\n".join(context + [question]) if context else question

    async with message.channel.typing():
        try:
            answer = await asyncio.to_thread(
                llm.reply, prompt, list(history.get(message.channel.id, [])), image
            )
        except Exception as e:  # noqa: BLE001
            await message.reply(f"Lỗi khi gọi model: {e}")
            return

    answer, created = files.extract_files(answer)
    convo = history.setdefault(message.channel.id, [])
    convo.append({"role": "user", "content": prompt or llm.DEFAULT_IMAGE_PROMPT})
    convo.append({"role": "assistant", "content": answer})
    del convo[:-MAX_HISTORY]

    if answer:
        for part in chunks(answer):
            await message.reply(part)
    await send_created_files(message, created)


def main():
    if not TOKEN:
        print(
            "Thiếu DISCORD_BOT_TOKEN — hãy đặt token của bot (Discord Developer Portal → Bot) rồi chạy lại.",
            flush=True,
        )
        return
    try:
        client.run(TOKEN)
    except discord.PrivilegedIntentsRequired:
        print(
            "Cần bật 'Message Content Intent' trong Discord Developer Portal → Bot → Privileged Gateway Intents.",
            flush=True,
        )
    except discord.LoginFailure:
        print("DISCORD_BOT_TOKEN không hợp lệ hoặc đã bị thu hồi.", flush=True)


if __name__ == "__main__":
    main()
