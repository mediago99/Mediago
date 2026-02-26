import telebot
import os
import requests
import time
import pymongo
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
from yt_dlp import YoutubeDL
from bson.objectid import ObjectId # এটি নতুন যোগ করা হয়েছে ID হ্যান্ডেল করার জন্য

# --- Configuration ---
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
MONETAG = os.environ.get('MONETAG_LINK')
CH_ID = os.environ.get('TELEGRAM_CHANNEL_ID', '@mediago9') 
MONGO_URI = os.environ.get('MONGO_URI') 
ADMIN_ID = 6311806060 

# --- Database Setup ---
client = pymongo.MongoClient(
    MONGO_URI, 
    tls=True, 
    tlsAllowInvalidCertificates=True
)
db = client['mediago_db']
users_col = db['users']
links_col = db['links'] # লিঙ্ক জমা রাখার জন্য নতুন কালেকশন

bot = telebot.TeleBot(API_TOKEN)
app = Flask('')

@app.route('/')
def home(): return "Mediago Bot is Online & Error Fixed!"

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
    bot.send_message(message.chat.id, "👋 **স্বাগতম!**\nযেকোনো ভিডিও লিঙ্ক পাঠান এবং আনলক করে ডাউনলোড করুন।")

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id == ADMIN_ID:
        total = users_col.count_documents({})
        bot.send_message(message.chat.id, f"📊 **অ্যাডমিন প্যানেল**\n\n👥 মোট ইউজার: {total} জন")
    else:
        bot.send_message(message.chat.id, f"❌ আপনি এই বটের অ্যাডমিন নন।")

@bot.message_handler(func=lambda message: "http" in message.text)
def handle_link(message):
    log_user(message.chat.id)
    
    if not is_subscribed(message.chat.id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📢 Join Our Channel", url="https://t.me/mediago9"))
        bot.send_message(message.chat.id, "❌ **আপনাকে আগে আমাদের চ্যানেলে জয়েন করতে হবে!**", reply_markup=markup)
        return

    # প্রো-সিস্টেম: লিঙ্ক ডাটাবেজে সেভ করা (BUTTON_DATA_INVALID এরর ঠেকাতে)
    link_data = {
        "url": message.text,
        "time": int(time.time())
    }
    link_obj = links_col.insert_one(link_data)
    link_id = str(link_obj.inserted_id)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎬 Watch Ad to Unlock (1 Min)", url=MONETAG))
    markup.add(InlineKeyboardButton("🔓 Unlock Now", callback_data=f"unl_{link_id}"))
    
    bot.send_message(
        message.chat.id, 
        "⚠️ **লিঙ্কটি লক করা আছে!**\n\nভিডিওটি আনলক করতে অন্তত ১ মিনিট অ্যাডটি দেখুন। তারপর নিচের আনলক বাটনে ক্লিক করুন।", 
        reply_markup=markup, 
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('unl_'))
def process_unlock(call):
    link_id = call.data.split('_')[1]
    
    # ডাটাবেজ থেকে লিঙ্ক উদ্ধার করা
    link_info = links_col.find_one({"_id": ObjectId(link_id)})
    
    if not link_info:
        bot.answer_callback_query(call.id, "❌ লিঙ্কটি পুরনো হয়ে গেছে বা পাওয়া যায়নি।", show_alert=True)
        return

    sent_time = link_info['time']
    original_url = link_info['url']
    
    if int(time.time()) - sent_time < 60:
        bot.answer_callback_query(call.id, "❌ আপনি এখনো ১ মিনিট অ্যাড দেখেননি! অপেক্ষা করুন।", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "✅ আনলক সফল! ভিডিও প্রসেস হচ্ছে...")
        status_msg = bot.send_message(call.message.chat.id, "⏳ ভিডিওটি প্রসেস হচ্ছে, দয়া করে অপেক্ষা করুন...")
        
        file_path = f"vid_{call.message.chat.id}.mp4"
        try:
                        ydl_opts = {
                # এটি ইউটিউব থেকে সরাসরি অডিওসহ ভিডিও (Single File) নিয়ে আসবে
                'format': 'best[ext=mp4]/best', 
                'outtmpl': file_path,
                'quiet': True,
                'no_warnings': True,
                # বড় ভিডিওর কারণে সার্ভার ক্রাশ হওয়া ঠেকাতে লিমিট
                'max_filesize': 50 * 1024 * 1024 
            }
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([original_url])
                
            with open(file_path, 'rb') as video:
                bot.send_video(call.message.chat.id, video, caption="✅ আপনার ভিডিও প্রস্তুত!")
            
            if os.path.exists(file_path):
                os.remove(file_path)
            bot.delete_message(call.message.chat.id, status_msg.message_id)
            # ডাউনলোড শেষ হলে ডাটাবেজ থেকে লিঙ্ক মুছে ফেলা (অপশনাল)
            links_col.delete_one({"_id": ObjectId(link_id)})
            
        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            bot.send_message(call.message.chat.id, f"❌ ডাউনলোড ব্যর্থ! ইউটিউব ব্লক করেছে অথবা ফাইল সাইজ অনেক বড়।")

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
