"""
Bot Discord cho Gemma 3 4B (dùng chung model với web qua llm.py).

Cách hoạt động:
    - Mention @bot kèm câu hỏi để bot trả lời.
    - Gửi kèm ảnh (đính kèm) để bot mô tả ảnh — giống chế độ trên web.
    - Bot nhớ ngữ cảnh hội thoại riêng cho từng kênh.

Cấu hình (biến môi trường, xem docker-compose.base44.yml):
    DISCORD_BOT_TOKEN  bắt buộc — token của bot
    DISCORD_GUILD_ID   tuỳ chọn — nếu đặt, bot chỉ trả lời trong server này
"""

import asyncio
import base64
import os

import discord

import llm

TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "").strip()

MAX_HISTORY = int(os.environ.get("DISCORD_MAX_HISTORY", "10"))
MAX_LEN = 2000  # giới hạn tin nhắn của Discord

intents = discord.Intents.default()
intents.message_content = True  # cần bật "Message Content Intent" trong Discord Developer Portal

client = discord.Client(intents=intents)
history = {}  # channel_id -> [{role, content}]


def stripped_question(message):
    """Bỏ phần mention @bot, giữ lại câu hỏi."""
    text = message.content
    for mention in message.mentions:
        text = text.replace(f"<@{mention.id}>", " ").replace(f"<@!{mention.id}>", " ")
    return text.strip()


async def attached_image(message):
    """Ảnh đính kèm đầu tiên, dạng base64."""
    for attachment in message.attachments:
        if (attachment.content_type or "").startswith("image/"):
            data = await attachment.read()
            return base64.b64encode(data).decode()
    return None


def chunks(text, size=MAX_LEN):
    parts = [text[i : i + size] for i in range(0, len(text), size)]
    return parts or [""]


@client.event
async def on_ready():
    print(f"Đã đăng nhập: {client.user} (server: {GUILD_ID or 'tất cả'})", flush=True)
    try:
        print("Đang kiểm tra model...", flush=True)
        await asyncio.to_thread(llm.ensure_model)
        print("Model sẵn sàng.", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"Không tải được model: {e}", flush=True)


@client.event
async def on_message(message):
    if message.author.bot or client.user not in message.mentions:
        return
    if GUILD_ID and str(getattr(message.guild, "id", "")) != GUILD_ID:
        return

    question = stripped_question(message)
    image = await attached_image(message)
    if not question and image is None:
        await message.reply("Bạn hãy nhập câu hỏi hoặc gửi kèm một ảnh nhé.")
        return

    async with message.channel.typing():
        try:
            answer = await asyncio.to_thread(
                llm.reply, question, list(history.get(message.channel.id, [])), image
            )
        except Exception as e:  # noqa: BLE001
            await message.reply(f"Lỗi khi gọi model: {e}")
            return

    convo = history.setdefault(message.channel.id, [])
    convo.append({"role": "user", "content": question or llm.DEFAULT_IMAGE_PROMPT})
    convo.append({"role": "assistant", "content": answer})
    del convo[:-MAX_HISTORY]

    for part in chunks(answer):
        await message.reply(part)


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
