import telebot
import os
import requests
import time
import pymongo
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
from yt_dlp import YoutubeDL

# --- Configuration ---
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
MONETAG = os.environ.get('MONETAG_LINK')
CH_ID = os.environ.get('TELEGRAM_CHANNEL_ID')
MONGO_URI = os.environ.get('MONGO_URI') 
ADMIN_ID = int(os.environ.get('ADMIN_ID', '6311806060'))

# লিঙ্ক সংরক্ষণের জন্য (Callback Data Limit এড়াতে)
pending_links = {}

client = pymongo.MongoClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client['mediago_db']
users_col = db['users']

bot = telebot.TeleBot(API_TOKEN)
app = Flask('')

@app.route('/')
def home(): return "Mediago Bot is Active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run).start()

# --- Helpers ---
def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CH_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

# --- Handlers ---
@bot.message_handler(func=lambda message: "http" in message.text)
def handle_link(message):
    if not is_subscribed(message.chat.id):
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("📢 Join Channel", url="https://t.me/mediago9"))
        bot.send_message(message.chat.id, "❌ আগে জয়েন করুন!", reply_markup=markup)
        return

    # ইউনিক আইডি দিয়ে লিঙ্ক সেভ করা (যাতে বাটন ক্লিক করলে পাওয়া যায়)
    link_id = str(int(time.time()))
    pending_links[link_id] = message.text

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎬 Watch Ad (1 Min)", url=MONETAG))
    markup.add(InlineKeyboardButton("🔓 Unlock Video", callback_data=f"unl_{link_id}"))
    
    bot.send_message(message.chat.id, "⚠️ লিঙ্ক লক করা! ১ মিনিট পর আনলক করুন।", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('unl_'))
def process_unlock(call):
    link_id = call.data.split('_')[1]
    
    if int(time.time()) - int(link_id) < 60:
        bot.answer_callback_query(call.id, "❌ ১ মিনিট পূর্ণ হয়নি!", show_alert=True)
        return

    original_url = pending_links.get(link_id)
    bot.answer_callback_query(call.id, "✅ আনলক হয়েছে!")
    status_msg = bot.send_message(call.message.chat.id, "⏳ প্রসেস হচ্ছে...")

    try:
        file_path = f"vid_{call.message.chat.id}.mp4"
        
        # ইউটিউব ও টিকটকের জন্য শক্তিশালী সেটিংস
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': file_path,
            'quiet': True,
            'no_warnings': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/110.0.0.0 Safari/537.36',
            'referer': 'https://www.tiktok.com/', # টিকটকের জন্য রেফারার জরুরি
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([original_url])
        
        with open(file_path, 'rb') as video:
            bot.send_video(call.message.chat.id, video, caption="✅ ডাউনলোড সফল!")
        
        os.remove(file_path)
    except Exception as e:
        bot.send_message(call.message.chat.id, "❌ ফেইলড! লিঙ্কটি হয়তো প্রাইভেট বা সার্ভার ব্লক করেছে।")
    finally:
        bot.delete_message(call.message.chat.id, status_msg.message_id)

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
        
