import telebot
import os
import requests
import time
import pymongo
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
from yt_dlp import YoutubeDL

# --- Configuration (Render Environment Variables থেকে আসবে) ---
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
MONETAG = os.environ.get('MONETAG_LINK')
CH_ID = os.environ.get('TELEGRAM_CHANNEL_ID', '@mediago9') # ডিফল্ট আপনার নতুন চ্যানেল
MONGO_URI = os.environ.get('MONGO_URI') 

# অ্যাডমিন আইডি (আপনার আইডিটি এখানে ফিক্সড করে দেওয়া হয়েছে)
ADMIN_ID = 6311806060

# --- Database Setup (MongoDB) ---
# SSL হ্যান্ডশেক এরর এড়াতে tls=True এবং tlsAllowInvalidCertificates যোগ করা হয়েছে
client = pymongo.MongoClient(
    MONGO_URI, 
    tls=True, 
    tlsAllowInvalidCertificates=True
)
db = client['mediago_db']
users_col = db['users']

bot = telebot.TeleBot(API_TOKEN)
app = Flask('')

@app.route('/')
def home(): return "Mediago Bot is Online & Database Connected!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Functions ---
def is_subscribed(user_id):
    """ইউজার চ্যানেলে জয়েন আছে কি না চেক করে"""
    try:
        member = bot.get_chat_member(CH_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

def log_user(user_id):
    """নতুন ইউজার হলে ডাটাবেজে সেভ করে"""
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({"user_id": user_id, "join_date": time.time()})

# --- Handlers ---
@bot.message_handler(commands=['start'])
def welcome(message):
    log_user(message.chat.id)
    bot.send_message(message.chat.id, "👋 **স্বাগতম!**\nযেকোনো ভিডিও লিঙ্ক পাঠান এবং আনলক করে ডাউনলোড করুন।")

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    """অ্যাডমিন প্যানেল: মোট ইউজার সংখ্যা দেখাবে"""
    if message.from_user.id == ADMIN_ID:
        total = users_col.count_documents({})
        bot.send_message(message.chat.id, f"📊 **অ্যাডমিন প্যানেল**\n\n👥 মোট ইউজার: {total} জন")
    else:
        bot.send_message(message.chat.id, f"❌ আপনি এই বটের অ্যাডমিন নন।\nআপনার আইডি: {message.from_user.id}")

@bot.message_handler(func=lambda message: "http" in message.text)
def handle_link(message):
    log_user(message.chat.id)
    
    # ফোর্স জয়েন চেক
    if not is_subscribed(message.chat.id):
        markup = InlineKeyboardMarkup()
        # এখানে আপনার নতুন চ্যানেল লিঙ্ক দেওয়া হয়েছে
        markup.add(InlineKeyboardButton("📢 Join Our Channel", url="https://t.me/mediago9"))
        bot.send_message(message.chat.id, "❌ **আপনাকে আগে আমাদের চ্যানেলে জয়েন করতে হবে!**\nজয়েন করার পর আবার লিঙ্কটি পাঠান।", reply_markup=markup)
        return

    # লিঙ্ক লক সিস্টেম
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎬 Watch Ad to Unlock (1 Min)", url=MONETAG))
    markup.add(InlineKeyboardButton("🔓 Unlock Now", callback_data=f"unl_{int(time.time())}_{message.text}"))
    
    bot.send_message(
        message.chat.id, 
        "⚠️ **লিঙ্কটি লক করা আছে!**\n\nভিডিওটি আনলক করতে অন্তত ১ মিনিট অ্যাডটি দেখুন। তারপর নিচের আনলক বাটনে ক্লিক করুন।", 
        reply_markup=markup, 
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('unl_'))
def process_unlock(call):
    data = call.data.split('_')
    sent_time = int(data[1])
    original_url = data[2]
    
    # ১ মিনিট সময় পার হয়েছে কি না চেক
    if int(time.time()) - sent_time < 60:
        bot.answer_callback_query(call.id, "❌ আপনি এখনো ১ মিনিট অ্যাড দেখেননি! অপেক্ষা করুন।", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "✅ আনলক সফল! ভিডিও প্রসেস হচ্ছে...")
        status_msg = bot.send_message(call.message.chat.id, "⏳ ভিডিওটি প্রসেস হচ্ছে, দয়া করে ১-২ মিনিট অপেক্ষা করুন...")
        
        file_path = f"vid_{call.message.chat.id}.mp4"
        try:
            # প্রো-লেভেল ইউটিউব ও অন্যান্য ভিডিও ডাউনলোড সেটিংস
            ydl_opts = {
                'format': 'best[ext=mp4]/best', # অডিওসহ ভিডিও নিশ্চিত করবে (FFmpeg ছাড়া)
                'outtmpl': file_path,
                'quiet': True,
                'no_warnings': True,
                'max_filesize': 50 * 1024 * 1024 # রেন্ডার সার্ভার সেফটির জন্য ৫০ এমবি লিমিট
            }

            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([original_url])
            
            # ভিডিও পাঠানো
            with open(file_path, 'rb') as video:
                bot.send_video(call.message.chat.id, video, caption="✅ আপনার ভিডিও প্রস্তুত!")
            
            # মেমোরি খালি করা
            if os.path.exists(file_path):
                os.remove(file_path)
            bot.delete_message(call.message.chat.id, status_msg.message_id)
            
        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            print(f"Error: {e}")
            bot.send_message(call.message.chat.id, f"❌ ডাউনলোড করতে সমস্যা হয়েছে। লিঙ্কটি কাজ করছে না অথবা ভিডিওটি অনেক বড় (৫০ এমবি+)।")

if __name__ == "__main__":
    keep_alive()
    print("Bot is starting...")
    bot.polling(none_stop=True)
    
