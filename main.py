import telebot
import os
import requests
import time
import pymongo
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
from yt_dlp import YoutubeDL
from bson.objectid import ObjectId

# --- Configuration ---
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
MONETAG = os.environ.get('MONETAG_LINK')
CH_ID = os.environ.get('TELEGRAM_CHANNEL_ID', '@mediago9') 
MONGO_URI = os.environ.get('MONGO_URI') 
ADMIN_ID = 6311806060 # আপনার আইডি

# --- Database Setup ---
client = pymongo.MongoClient(
    MONGO_URI, 
    tls=True, 
    tlsAllowInvalidCertificates=True
)
db = client['mediago_db']
users_col = db['users']
links_col = db['links'] 

bot = telebot.TeleBot(API_TOKEN)
app = Flask('')

@app.route('/')
def home(): return "Mediago Bot: YouTube Fix & 100MB Enabled!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Functions ---
def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CH_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

def log_user(user_id):
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({"user_id": user_id, "join_date": time.time()})

# --- Handlers ---
@bot.message_handler(commands=['start'])
def welcome(message):
    log_user(message.chat.id)
    bot.send_message(message.chat.id, "👋 **স্বাগতম!**\nযেকোনো ভিডিও লিঙ্ক পাঠান এবং ডাউনলোড করুন।")

@bot.message_handler(func=lambda message: "http" in message.text)
def handle_link(message):
    log_user(message.chat.id)
    
    if not is_subscribed(message.chat.id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📢 Join Our Channel", url="https://t.me/mediago9"))
        bot.send_message(message.chat.id, "❌ **আগে চ্যানেলে জয়েন করুন!**", reply_markup=markup)
        return

    # লিঙ্কটি ডাটাবেজে সেভ করা (যাতে BUTTON_DATA_INVALID এরর না আসে)
    link_data = {"url": message.text, "time": int(time.time())}
    link_obj = links_col.insert_one(link_data)
    link_id = str(link_obj.inserted_id)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎬 Watch Ad to Unlock (1 Min)", url=MONETAG))
    markup.add(InlineKeyboardButton("🔓 Unlock Now", callback_data=f"unl_{link_id}"))
    
    bot.send_message(
        message.chat.id, 
        "⚠️ **লিঙ্কটি লক করা আছে!**\n\n১ মিনিট অ্যাড দেখে 'Unlock Now' এ ক্লিক করুন।", 
        reply_markup=markup, 
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('unl_'))
def process_unlock(call):
    link_id = call.data.split('_')[1]
    link_info = links_col.find_one({"_id": ObjectId(link_id)})
    
    if not link_info:
        bot.answer_callback_query(call.id, "❌ লিঙ্কটি খুঁজে পাওয়া যায়নি।", show_alert=True)
        return

    original_url = link_info['url']
    sent_time = link_info['time']
    
    if int(time.time()) - sent_time < 60:
        bot.answer_callback_query(call.id, "❌ আপনি এখনো ১ মিনিট অ্যাড দেখেননি!", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "✅ আনলক সফল!")
        status_msg = bot.send_message(call.message.chat.id, "⏳ প্রসেস হচ্ছে, দয়া করে অপেক্ষা করুন...")
        
        file_path = f"vid_{call.message.chat.id}.mp4"
        try:
            # ইউটিউবের ব্লক এড়ানোর জন্য নতুন সেটিংস
            ydl_opts = {
                'format': 'best[ext=mp4]/best', 
                'outtmpl': file_path,
                'quiet': True,
                'no_warnings': True,
                'max_filesize': 100 * 1024 * 1024, # ১০০ এমবি লিমিট
                'nocheckcertificate': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'add_header': ['Accept-Language: en-US,en;q=0.9']
            }

            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([original_url])
            
            with open(file_path, 'rb') as video:
                bot.send_video(call.message.chat.id, video, caption="✅ ডাউনলোড সফল!")
            
            if os.path.exists(file_path):
                os.remove(file_path)
            bot.delete_message(call.message.chat.id, status_msg.message_id)
            links_col.delete_one({"_id": ObjectId(link_id)})
            
        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            print(f"Error: {e}")
            bot.send_message(call.message.chat.id, "❌ ডাউনলোড ব্যর্থ! ইউটিউব আপনার সার্ভারকে ব্লক করেছে বা ফাইলটি অনেক বড়।")

if __name__ == "__main__":
    keep_alive()
    # কনফ্লিক্ট সমস্যা এড়াতে নতুন পোলিং মেথড
    try:
        bot.remove_webhook()
        bot.polling(none_stop=True, timeout=60)
    except Exception as e:
        print(f"Polling error: {e}")
        time.sleep(5)
