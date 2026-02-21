import telebot
import os
import requests
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
from yt_dlp import YoutubeDL

# --- Uptime System (Railway Fix) ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Alive and Running on Railway!"

def run():
    # Railway-তে পোর্ট অটোমেটিক সেট হয়, তাই os.getenv('PORT') ব্যবহার করা হয়েছে
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Configuration ---
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CH_ID = os.environ.get('TELEGRAM_CHANNEL_ID')
MONETAG = os.environ.get('MONETAG_LINK')
ADMIN_ID = 6311806060 

bot = telebot.TeleBot(API_TOKEN)

# --- ইউজার ট্র্যাকিং (Railway-তে ফাইল রাইটিং পারমিশন ফিক্স) ---
def log_user(user_id):
    try:
        if not os.path.exists("users.txt"):
            with open("users.txt", "w") as f: f.write("")
        with open("users.txt", "r") as f:
            users = f.read().splitlines()
        if str(user_id) not in users:
            with open("users.txt", "a") as f: f.write(f"{user_id}\n")
    except Exception as e:
        print(f"Logging error: {e}")

# --- টিকটক ডাউনলোডার (Dual API) ---
def get_tiktok_video(url):
    try:
        res = requests.get(f"https://api.tiklydown.eu.org/api/download?url={url}", timeout=10).json()
        return res.get('video', {}).get('noWatermark')
    except:
        try:
            res = requests.get(f"https://www.tikwm.com/api/?url={url}", timeout=10).json()
            return res.get('data', {}).get('play')
        except: return None

@bot.message_handler(commands=['start'])
def welcome(message):
    log_user(message.chat.id)
    bot.send_message(message.chat.id, "👋 **স্বাগতম!**\nলিঙ্ক পাঠান এবং আনলক করে ডাউনলোড করুন।")

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.from_user.id == ADMIN_ID:
        msg_text = message.text.replace('/broadcast ', '')
        if msg_text == '/broadcast' or not msg_text:
            bot.send_message(message.chat.id, "⚠️ ব্যবহার: `/broadcast আপনার মেসেজ`")
            return
        
        if os.path.exists("users.txt"):
            with open("users.txt", "r") as f:
                users = f.read().splitlines()
            count = 0
            for user in users:
                try:
                    bot.send_message(user, msg_text)
                    count += 1
                except: continue
            bot.send_message(message.chat.id, f"✅ {count} জন ইউজারের কাছে পাঠানো হয়েছে।")
    else:
        bot.send_message(message.chat.id, "❌ আপনি অ্যাডমিন নন।")

@bot.message_handler(func=lambda message: "http" in message.text)
def handle_link(message):
    log_user(message.chat.id)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎬 Watch Ad to Unlock (1 Min)", url=MONETAG))
    markup.add(InlineKeyboardButton("🔓 Unlock Now", callback_data=f"unl_{int(time.time())}_{message.text}"))
    bot.send_message(message.chat.id, "⚠️ **লিঙ্কটি লক করা আছে!**\nভিডিওটি আনলক করতে অন্তত ১ মিনিট অ্যাডটি দেখুন।", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('unl_'))
def process_unlock(call):
    bot.answer_callback_query(call.id)
    data = call.data.split('_')
    sent_time, original_url = int(data[1]), data[2]
    
    if int(time.time()) - sent_time < 60:
        remaining = 60 - (int(time.time()) - sent_time)
        bot.send_message(call.message.chat.id, f"❌ আপনি এখনো ১ মিনিট দেখেননি! আর {remaining} সেকেন্ড অপেক্ষা করুন।")
    else:
        status_msg = bot.send_message(call.message.chat.id, "⏳ প্রসেসিং হচ্ছে...")
        try:
            if "tiktok.com" in original_url:
                video_link = get_tiktok_video(original_url)
                if video_link:
                    bot.send_video(call.message.chat.id, video_link, caption="✅ TikTok প্রস্তুত!")
                else:
                    bot.send_message(call.message.chat.id, "❌ টিকটক ভিডিও পাওয়া যায়নি।")
            else:
                file_path = f"vid_{call.message.chat.id}.mp4"
                # Railway ক্রেডিট বাঁচাতে quiet=True এবং মেমোরি ম্যানেজমেন্ট যোগ করা হয়েছে
                ydl_opts = {'format': 'best', 'outtmpl': file_path, 'quiet': True, 'no_warnings': True}
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([original_url])
                with open(file_path, 'rb') as video:
                    bot.send_video(call.message.chat.id, video, caption="✅ ভিডিও প্রস্তুত!")
                if os.path.exists(file_path): os.remove(file_path)
            bot.delete_message(call.message.chat.id, status_msg.message_id)
        except Exception as e:
            bot.send_message(call.message.chat.id, "❌ ডাউনলোড এরর! লিঙ্কটি আবার চেক করুন।")

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
