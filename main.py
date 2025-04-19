# === 📁 main.py ===
# Вставь этот файл в корень твоего GitHub репозитория
# Он автоматически запускается Render'ом при деплое

import os
import json
import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, BotCommand
from aiogram.utils.executor import start_webhook
import aiohttp
from gtts import gTTS
from tempfile import NamedTemporaryFile

API_TOKEN = os.getenv("TG_API")
OPENROUTER_API_KEY = os.getenv("OPENROUTER")
ELEVENLABS_KEY = os.getenv("ELEVEN_KEY")
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")
WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"https://{WEBHOOK_HOST}{WEBHOOK_PATH}"

WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.getenv("PORT", 5000))

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

user_prefs_file = "user_prefs.json"
user_prefs = {}
user_context = {}

voices = {
    "Sargazy": "EXAVITQu4vr4xnSDxMaL",
    "Kanykey": "21m00Tcm4TlvDq8ikWAM",
    "Almambet": "AZnzlk1XvdvUeBnXmlld"
}

def load_prefs():
    global user_prefs
    if os.path.exists(user_prefs_file):
        with open(user_prefs_file, "r") as f:
            user_prefs = json.load(f)

def save_prefs():
    with open(user_prefs_file, "w") as f:
        json.dump(user_prefs, f)

load_prefs()

def init_user(uid):
    if uid not in user_prefs:
        user_prefs[uid] = {"language": "en", "mode": "wise", "voice": "Sargazy", "voice_mode": False}

async def get_ai_response(prompt: str, user_id: int) -> str:
    prefs = user_prefs.get(str(user_id), {})
    lang = prefs.get("language", "en")
    mode = prefs.get("mode", "wise")
    history = user_context.get(user_id, [])[-5:]
    messages = [{"role": "system", "content": f"You are a {mode} character who replies in {lang}"}] + history + [{"role": "user", "content": prompt}]

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "openchat/openchat-3.5-0106", "messages": messages}

    async with aiohttp.ClientSession() as session:
        async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                answer = data["choices"][0]["message"]["content"]
                user_context.setdefault(user_id, []).append({"role": "user", "content": prompt})
                user_context[user_id].append({"role": "assistant", "content": answer})
                return answer
            return "AI is temporarily unavailable."

async def speak(text: str, user_id: int) -> str:
    prefs = user_prefs.get(str(user_id), {})
    voice = prefs.get("voice", "Sargazy")
    lang = prefs.get("language", "en")
    headers = {"xi-api-key": ELEVENLABS_KEY, "Content-Type": "application/json"}
    if len(text) > 900:
        text = text[:900]

    json_data = {"text": text, "voice_settings": {"stability": 0.3, "similarity_boost": 0.8}, "model_id": "eleven_multilingual_v2"}
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voices.get(voice)}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=json_data) as resp:
                if resp.status == 429:
                    return "📛 ElevenLabs limit reached."
                if resp.status != 200:
                    raise Exception("Eleven failed")
                data = await resp.read()
                with NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                    f.write(data)
                    return f.name
    except:
        tts = gTTS(text=text, lang=lang)
        fallback = NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(fallback.name)
        return fallback.name

@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    uid = str(msg.from_user.id)
    init_user(uid)
    await msg.answer("👋 Welcome to BEKNMD — digital nomad is online. Type /help")

@dp.message_handler(commands=["ask"])
async def ask_cmd(msg: types.Message):
    uid = str(msg.from_user.id)
    init_user(uid)
    prompt = msg.get_args()
    if not prompt:
        await msg.answer("❓ Use like this: /ask What is the meaning of life?")
        return
    reply = await get_ai_response(prompt, uid)
    await msg.answer(reply)
    if user_prefs[uid].get("voice_mode"):
        audio = await speak(reply, uid)
        await msg.answer_voice(types.InputFile(audio))

@dp.message_handler()
async def fallback(msg: types.Message):
    await msg.answer("⚠️ Unknown command. Type /ask to chat or /help")

async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(dp):
    await bot.delete_webhook()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.create_task(start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT
    ))
    loop.run_forever()
