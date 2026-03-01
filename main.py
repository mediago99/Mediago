import telebot
import os
import time
import pymongo
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
from yt_dlp import YoutubeDL

# ================= CONFIG =================
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
MONETAG = os.environ.get('MONETAG_LINK')
CH_ID = os.environ.get('TELEGRAM_CHANNEL_ID')
MONGO_URI = os.environ.get('MONGO_URI')
ADMIN_ID = int(os.environ.get('ADMIN_ID'))

# ================= DB =================
client = pymongo.MongoClient(MONGO_URI)
db = client['mediago_db']
users_col = db['users']

# ================= BOT =================
bot = telebot.TeleBot(API_TOKEN)
app = Flask('')

# ============== WEB SERVER (Render) ==============
@app.route('/')
def home():
    return "Bot Running Successfully"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run).start()

# ============== HELPERS ==============
def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CH_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def add_user(user_id):
    if not users_col.find_one({"_id": user_id}):
        users_col.insert_one({"_id": user_id})

# ============== START ==============
@bot.message_handler(commands=['start'])
def start(message):
    add_user(message.from_user.id)
    total = users_col.count_documents({})
    bot.send_message(
        message.chat.id,
        f"👋 Welcome!\n\n👥 Total Users: {total}\n\nSend YouTube / TikTok / Facebook link."
    )

# ============== ADMIN STATS ==============
@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id == ADMIN_ID:
        total = users_col.count_documents({})
        bot.send_message(message.chat.id, f"👥 Total Users: {total}")

# ============== LINK HANDLER ==============
@bot.message_handler(func=lambda m: m.text and "http" in m.text)
def download_video(message):

    if not is_subscribed(message.from_user.id):
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CH_ID.replace('@','')}")
        )
        bot.send_message(message.chat.id, "❌ Please join channel first!", reply_markup=markup)
        return

    url = message.text.strip()
    status = bot.send_message(message.chat.id, "⏳ Downloading... Please wait")

    file_path = f"video_{message.chat.id}.mp4"

    try:
        ydl_opts = {
            'format': 'bv*[height<=720]+ba/best[height<=720]',
            'outtmpl': file_path,
            'quiet': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android']
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0'
            }
        }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if os.path.exists(file_path):
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video, caption="✅ Download Complete")
            os.remove(file_path)
        else:
            bot.send_message(message.chat.id, "❌ File not found.")

    except Exception as e:
        bot.send_message(message.chat.id, "❌ Failed! Server blocked or invalid link.")

    finally:
        bot.delete_message(message.chat.id, status.message_id)

# ============== MAIN ==============
if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
