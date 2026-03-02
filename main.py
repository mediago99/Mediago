import os
import telebot
import yt_dlp
import time
from flask import Flask
from threading import Thread
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===============================
# CONFIG
# ===============================

TOKEN = os.environ.get("BOT_TOKEN")
MONETAG_LINK = os.environ.get("MONETAG_LINK")

bot = telebot.TeleBot(TOKEN)
BOT_USERNAME = bot.get_me().username

users = set()
pending_links = {}

# ===============================
# FLASK (Render keep alive)
# ===============================

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run).start()

# ===============================
# START
# ===============================

@bot.message_handler(commands=['start'])
def start(message):
    users.add(message.from_user.id)

    bot.reply_to(
        message,
        f"""👋 Welcome!

📥 Send video link or mention me

👥 Total Users: {len(users)}
"""
    )

# ===============================
# HANDLE LINK
# ===============================

@bot.message_handler(func=lambda message: True)
def handle_message(message):

    text = message.text.strip()

    if message.chat.type in ["group", "supergroup"]:
        if f"@{BOT_USERNAME}" not in text:
            return
        text = text.replace(f"@{BOT_USERNAME}", "").strip()

    if not text.startswith("http"):
        return

    link_id = str(int(time.time()))
    pending_links[link_id] = text

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📢 Watch Ad", url=MONETAG_LINK))
    markup.add(InlineKeyboardButton("🔓 Unlock Video", callback_data=f"unlock_{link_id}"))

    bot.send_message(
        message.chat.id,
        "🔒 Video Locked!\n\nWatch ad and unlock after 60 seconds.",
        reply_markup=markup
    )

# ===============================
# UNLOCK
# ===============================

@bot.callback_query_handler(func=lambda call: call.data.startswith("unlock_"))
def unlock(call):

    link_id = call.data.split("_")[1]

    if int(time.time()) - int(link_id) < 60:
        bot.answer_callback_query(call.id, "❌ Wait 60 seconds!", show_alert=True)
        return

    url = pending_links.get(link_id)

    bot.answer_callback_query(call.id, "✅ Unlocked!")

    try:
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': 'video.%(ext)s',
            'quiet': True,
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        with open(filename, 'rb') as video:
            bot.send_video(call.message.chat.id, video)

        os.remove(filename)

    except:
        bot.send_message(call.message.chat.id, "❌ Download failed!")

# ===============================
# RUN
# ===============================

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
