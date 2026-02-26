import os
import asyncio
import threading
from flask import Flask
import firebase_admin
from firebase_admin import credentials, db
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from datetime import datetime

app = Flask(__name__)

# --- ১. ওয়েব সার্ভার সেটিংস (মিনি অ্যাপের জন্য) ---
@app.route('/')
def home():
    try:
        # এটি সরাসরি আপনার index.html ফাইলটি পড়বে এবং মিনি অ্যাপে দেখাবে
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Error: index.html ফাইলটি পাওয়া যায়নি! নিশ্চিত করুন এটি main.py এর পাশেই আছে।"

def run_flask():
    # রেলওয়ে সাধারণত ৮MD৮ বা নির্দিষ্ট পোর্ট ব্যবহার করে
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- ২. কনফিগারেশন ---
BOT_TOKEN = "8595737059:AAHOuAZV6eCH632Ypvpp5wmfoEgiQ3erdUA" 
ADMIN_ID = 6311806060 
CHANNEL_USERNAME = "@viralmoviehubbd"
FIREBASE_DB_URL = "https://viralmoviehubbd-default-rtdb.firebaseio.com/"

# রেলওয়ে ডোমেইন (যেখানে index.html আছে)
RAILWAY_APP_URL = "https://viral-link-production.up.railway.app" 
# গিটহাব অ্যাড লিঙ্ক
ADS_URL = "https://viralhub420.github.io/Viral-Link/ads.html"

TASK_LINKS = {
    "task1": "https://singingfiles.com/show.php?l=0&u=2499908&id=54747", 
    "task2": "https://singingfiles.com/show.php?l=0&u=2499908&id=36521",
    "task3": "https://singingfiles.com/show.php?l=0&u=2499908&id=54746"
}

# ফায়ারবেস ইনিশিয়াল করা
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
    except Exception as e:
        print(f"Firebase Error: {e}")

user_ref = db.reference('users')

# --- ৩. সাহায্যকারী ফাংশন ---
async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

def get_progress_bar(count, total=5):
    filled = "█" * count
    empty = "░" * (total - count)
    return f"[{filled}{empty}] {int((count/total)*100)}%"

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not await is_subscribed(context.bot, user_id):
        kb = [[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
              [InlineKeyboardButton("✅ Joined (Check)", callback_data="check_join")]]
        msg = "❌ <b>অ্যাক্সেস ডিনাইড!</b>\nচ্যানেলে জয়েন করে চেক বাটনে ক্লিক করুন।"
    else:
        msg = "🎬 <b>Viral Movie Hub</b>\n\nনিচের অপশনগুলো ব্যবহার করুন:"
        kb = [
            [InlineKeyboardButton("🚀 Open Movie App", callback_data="open_app")],
            [InlineKeyboardButton("🎁 My Offers (Earn)", callback_data="open_tasks")],
            [InlineKeyboardButton("🚀 Referral Reward", callback_data="open_referral")],
            [InlineKeyboardButton("📅 Daily Bonus & Rewards", callback_data="claim_bonus")],
            [InlineKeyboardButton("💰 Wallet & Withdraw", callback_data="open_wallet")]
        ]
    target = update.callback_query.message if update.callback_query else update.message
    await target.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

# --- ৪. বাটন হ্যান্ডলার ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)
    u_info = user_ref.child(user_id).get() or {'referrals': 0, 'coins': 0, 'completed_tasks': []}
    
    if query.data == "open_app":
        referrals = u_info.get('referrals', 0)
        if referrals < 5:
            bot_info = await context.bot.get_me()
            ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
            msg = f"🔒 <b>লক!</b> মুভি দেখতে ৫ জন বন্ধুকে ইনভাইট করুন।\n\n📊 {get_progress_bar(min(referrals, 5))}\n🔗 <code>{ref_link}</code>"
            kb = [[InlineKeyboardButton("🚀 Invite Friends", switch_inline_query=f"\nমুভি দেখো!\n{ref_link}")],
                  [InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
        else:
            msg = "✅ অ্যাডটি দেখে 'Open App' এ ক্লিক করুন।"
            # ADS_URL এ যাবে বিজ্ঞাপনের জন্য, RAILWAY_APP_URL এ যাবে মিনি অ্যাপ ডিজাইনের জন্য
            kb = [[InlineKeyboardButton("📺 Watch Ad to Unlock", url=ADS_URL)],
                  [InlineKeyboardButton("🎬 Open Movie App", web_app={"url": RAILWAY_APP_URL})]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif query.data == "open_tasks":
        completed = u_info.get('completed_tasks', [])
        kb = []
        for i in range(1, 4):
            tid = f"task{i}"
            if tid not in completed:
                kb.append([InlineKeyboardButton(f"💎 Offer {i}", url=TASK_LINKS[tid])])
                kb.append([InlineKeyboardButton(f"🔘 Done {i}", callback_data=f"done_{tid}")])
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])
        await query.edit_message_text("🎯 <b>My Offers:</b> অফার পূরণ করে 'Done' ক্লিক করুন।", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif query.data.startswith("done_"):
        tid = query.data.replace("done_", "")
        completed = u_info.get('completed_tasks', [])
        if tid not in completed:
            completed.append(tid)
            user_ref.child(user_id).update({'coins': u_info.get('coins', 0) + 200, 'completed_tasks': completed})
            await query.answer("🎉 ২০০ কয়েন যোগ হয়েছে!", show_alert=True)
            await show_main_menu(update, context)

    elif query.data == "claim_bonus":
        msg = "🎁 <b>Viral Reward Center</b>\n\nকাজগুলো করে পয়েন্ট নিন:"
        kb = [
            [InlineKeyboardButton("📺 Watch Ad (10 🪙)", url=ADS_URL)],
            [InlineKeyboardButton("✅ Claim Ad Reward", callback_data="verify_bonus")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_main")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif query.data == "verify_bonus":
        user_ref.child(user_id).update({'coins': u_info.get('coins', 0) + 10})
        await query.answer("📺 অভিনন্দন! ১০ কয়েন যোগ হয়েছে।", show_alert=True)

    elif query.data == "open_referral":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        msg = f"🚀 <b>Invite & Earn</b>\n\nপ্রতিটি রেফারে ১০০ কয়েন।\n\n🔗 <code>{ref_link}</code>"
        kb = [[InlineKeyboardButton("📢 Share Link", switch_inline_query=f"\nমুভি দেখো!\n{ref_link}")],
              [InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif query.data == "open_wallet":
        coins = u_info.get('coins', 0)
        msg = f"💰 <b>Your Wallet</b>\n\n🪙 Coins: {coins}\n💵 Cash: {coins*0.05:.2f} TK"
        kb = [[InlineKeyboardButton("💳 Withdraw Now", callback_data="req_withdraw")],
              [InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif query.data == "req_withdraw":
        coins = u_info.get('coins', 0)
        if coins < 2000:
            msg = f"❌ আপনার পর্যাপ্ত কয়েন নেই। উইথড্র করতে ২০০০ কয়েন লাগবে।"
            kb = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
        else:
            context.user_data['awaiting_num'] = True
            await query.edit_message_text("📩 পেমেন্ট নিতে আপনার <b>বিকাশ/নগদ নম্বর</b> লিখে পাঠান।")

    elif query.data in ["back_main", "check_join"]:
        await show_main_menu(update, context)

# --- ৫. মেসেজ ও স্টার্ট ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if context.user_data.get('awaiting_num'):
        number = update.message.text
        u_info = user_ref.child(user_id).get()
        admin_text = f"💳 <b>Withdraw!</b>\n👤 ID: {user_id}\n💰 Coins: {u_info['coins']}\n📱 No: {number}"
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text)
        user_ref.child(user_id).update({'coins': 0})
        context.user_data['awaiting_num'] = False
        await update.message.reply_text("✅ রিকোয়েস্ট পাঠানো হয়েছে।")
        
        # --- মুভি পোস্ট করার নতুন ফাংশন ---
async def post_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # এডমিন চেক
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ আপনি এই বটের এডমিন নন!")
        return

    try:
        # মেসেজ ফরম্যাট করা
        text = update.message.text.replace("/post", "").strip()
        parts = text.split("|")
        
        if len(parts) != 3:
            await update.message.reply_text("⚠️ সঠিক ফরম্যাট: /post নাম | ছবির লিঙ্ক | ভিডিও লিঙ্ক")
            return
            
        title, img, url = parts[0].strip(), parts[1].strip(), parts[2].strip()
        
        # ফায়ারবেসে ডাটা সেভ
        movie_ref = db.reference('movies')
        movie_ref.push({
            'title': title,
            'image_url': img,
            'video_url': url,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        await update.message.reply_text(f"✅ সফলভাবে মিনি অ্যাপে যোগ হয়েছে!\n🎬 মুভি: {title}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ সমস্যা হয়েছে: {str(e)}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    is_new = not user_ref.child(user_id).get()
    if is_new:
        args = context.args
        ref_by = args[0] if args and args[0] != user_id else None
        user_ref.child(user_id).set({'referrals': 0, 'coins': 0, 'completed_tasks': [], 'last_bonus': "", 'ref_by': ref_by})
        if ref_by:
            r_data = user_ref.child(ref_by).get() or {'referrals': 0, 'coins': 0}
            user_ref.child(ref_by).update({'referrals': r_data.get('referrals', 0) + 1, 'coins': r_data.get('coins', 0) + 100})
    await show_main_menu(update, context)

if __name__ == "__main__":
    # ওয়েব সার্ভার আলাদা থ্রেডে চালানো
    threading.Thread(target=run_flask, daemon=True).start()
    
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("post", post_movie))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot and Mini App Server is ready!")
    app_bot.run_polling()
