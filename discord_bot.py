import os
import json
import asyncio
import threading
import discord
from discord import app_commands

DATA_FILE = os.path.join(os.path.dirname(__file__), "chat_history.json")

SYSTEM_PROMPT = (
    "Bạn là một trợ lý AI hữu ích, thân thiện. "
    "Luôn trả lời bằng tiếng Việt một cách tự nhiên, rõ ràng. "
    "Nhớ ngữ cảnh cuộc trò chuyện để trả lời连贯."
)

# Lịch sử chat: { user_id: [ {role, content}, ... ] }
histories: dict[str, list] = {}


def load_histories():
    global histories
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            histories = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        histories = {}


def save_histories():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(histories, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_history(user_id: str) -> list:
    return histories.get(user_id, [])


def add_message(user_id: str, role: str, content: str):
    if user_id not in histories:
        histories[user_id] = []
    histories[user_id].append({"role": role, "content": content})
    # Giữ tối đa 20 tin nhắn (10 vòng对话)
    if len(histories[user_id]) > 20:
        histories[user_id] = histories[user_id][-20:]
    save_histories()


def generate_response(user_id: str, message: str) -> str:
    """Gọi model để tạo câu trả lời với lịch sử user."""
    from app import llm, model_status

    if model_status != "ready" or llm is None:
        return "⚠️ Model đang tải, vui lòng thử lại sau."

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in get_history(user_id):
        messages.append(h)
    messages.append({"role": "user", "content": message})

    response = llm.create_chat_completion(
        messages=messages,
        max_tokens=256,
    )
    return response["choices"][0]["message"]["content"].strip()


intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@tree.command(name="chat", description="Trò chuyện với AI")
async def chat_command(interaction: discord.Interaction, message: str):
    user_id = str(interaction.user.id)

    # Phản hồi tạm để user biết bot đang xử lý
    await interaction.response.send_thinking()

    # Chạy inference trong thread pool để không block event loop
    loop = asyncio.get_event_loop()
    try:
        reply = await loop.run_in_executor(None, generate_response, user_id, message)
    except Exception as e:
        reply = f"❌ Lỗi: {e}"

    # Lưu lịch sử
    add_message(user_id, "user", message)
    add_message(user_id, "assistant", reply)

    await interaction.followup.send(reply)


@tree.command(name="clear", description="Xóa lịch sử trò chuyện của bạn")
async def clear_command(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id in histories:
        del histories[user_id]
        save_histories()
    await interaction.response.send_message("🗑️ Đã xóa lịch sử trò chuyện!")


@client.event
async def on_ready():
    print(f"Discord bot đã đăng nhập: {client.user}")
    try:
        synced = await tree.sync()
        print(f"Đã sync {len(synced)} slash commands")
    except Exception as e:
        print(f"Lỗi sync commands: {e}")


def start_bot():
    """Khởi động Discord bot trong thread riêng."""
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("⚠️ DISCORD_BOT_TOKEN chưa được cấu hình — bot không khởi động.")
        return
    load_histories()
    try:
        client.run(token)
    except Exception as e:
        print(f"❌ Lỗi Discord bot: {e}")
