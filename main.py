import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import threading
import time
import random
import sqlite3
import os

# ================= الإعدادات ================= #
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

bot = telebot.TeleBot(TOKEN)

# ================= قاعدة البيانات ================= #
def db_op(query, params=(), fetch=False):
    conn = sqlite3.connect('islamic_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(query, params)
    res = cursor.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return res

def init_db():
    db_op('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, is_running INTEGER, interval INTEGER)')
    db_op('CREATE TABLE IF NOT EXISTS chats (chat_id INTEGER PRIMARY KEY, title TEXT)')
    db_op('CREATE TABLE IF NOT EXISTS blacklist (chat_id INTEGER PRIMARY KEY)')
    if not db_op("SELECT * FROM settings", fetch=True):
        db_op("INSERT INTO settings VALUES (1, 1, 60)")

# ================= دوال جلب المحتوى ================= #

def fetch_hadith():
    try:
        res = requests.get("https://hadeethenc.com/api/v1/hadeeths/list/?language=ar&category_id=1&per_page=40", timeout=10).json()
        h_id = random.choice(res['data'])['id']
        h_details = requests.get(f"https://hadeethenc.com/api/v1/hadeeths/one/?language=ar&id={h_id}", timeout=10).json()
        return f"📜 *حديث نبوي شريف:*\n\n{h_details['hadeeth']}\n\n📖 *المصدر:* {h_details['attribution']}"
    except: return "📜 قال ﷺ: «مَنْ صَلَّى عَلَيَّ صَلَاةً صَلَّى الله عَلَيْهِ بِهَا عَشْرًا»"

def fetch_tadabor():
    try:
        res = requests.get("https://mp3quran.net/api/v3/tadabor", timeout=10).json()
        item = random.choice(res['tadabor'])
        return item['video_url'], f"🎥 *تأملات قرآنية*\n\n📖 سورة: {item['surah_name']}\n🎙 القارئ: {item['reciter_name']}"
    except: return None, None

def fetch_quran_audio():
    try:
        res = requests.get("https://api.alquran.cloud/v1/ayah/random/ar.alafasy", timeout=10).json()
        d = res['data']
        return d['audio'], f"📖 *{d['surah']['name']}*\n\n{d['text']}"
    except: return None, None

# ================= لوحات التحكم ================= #

def main_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    conf = db_op("SELECT is_running, interval FROM settings", fetch=True)[0]
    status = "🛑 إيقاف النشر" if conf[0] == 1 else "✅ تشغيل النشر"
    markup.add(InlineKeyboardButton(status, callback_data="toggle_run"))
    markup.add(InlineKeyboardButton("⏱ ضبط الوقت", callback_data="menu_time"),
               InlineKeyboardButton("📊 القنوات", callback_data="menu_chats"))
    markup.add(InlineKeyboardButton("🚫 القائمة السوداء", callback_data="menu_black"),
               InlineKeyboardButton("📢 إذاعة", callback_data="menu_broadcast"))
    markup.add(InlineKeyboardButton("🚀 نشر فوري (تجربة)", callback_data="menu_instant"))
    return markup

# ================= معالجة الأوامر ================= #

@bot.message_handler(commands=['start', 'admin'])
def start_cmd(message):
    if message.from_user.id != ADMIN_ID: return
    bot.send_message(message.chat.id, "🛠 **لوحة التحكم الكاملة للأدمن:**", reply_markup=main_markup(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.from_user.id != ADMIN_ID: return
    
    data = call.data
    if data == "toggle_run":
        db_op("UPDATE settings SET is_running = 1 - is_running")
    
    elif data == "menu_time":
        markup = InlineKeyboardMarkup()
        for t in [15, 30, 60, 120, 360, 720]:
            markup.add(InlineKeyboardButton(f"كل {t} دقيقة", callback_data=f"settime_{t}"))
        markup.add(InlineKeyboardButton("⬅️ عودة", callback_data="main"))
        return bot.edit_message_text("⏱ اختر الفاصل الزمني للنشر:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif data.startswith("settime_"):
        t = int(data.split("_")[1])
        db_op("UPDATE settings SET interval = ?", (t,))
        bot.answer_callback_query(call.id, f"تم ضبط الوقت: {t} دقيقة")

    elif data == "menu_chats":
        chats = db_op("SELECT chat_id, title FROM chats", fetch=True)
        text = "📊 **القنوات المتصلة:**\n\n" + "\n".join([f"🔹 `{c[0]}` - {c[1]}" for c in chats])
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ عودة", callback_data="main"))
        return bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "menu_instant":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🎥 فيديو تدبر", callback_data="inst_tadabor"),
                   InlineKeyboardButton("📜 حديث", callback_data="inst_hadith"))
        markup.add(InlineKeyboardButton("🎙 قرآن صوتي", callback_data="inst_quran"),
                   InlineKeyboardButton("📿 ذكر", callback_data="inst_azkar"))
        markup.add(InlineKeyboardButton("⬅️ عودة", callback_data="main"))
        return bot.edit_message_text("🚀 اختر الخدمة للنشر الفوري الآن:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif data.startswith("inst_"):
        bot.answer_callback_query(call.id, "جاري النشر...")
        mode = data.split("_")[1]
        publish_content(manual_mode=mode)

    elif data == "main":
        return bot.edit_message_text("🛠 **لوحة التحكم الكاملة للأدمن:**", call.message.chat.id, call.message.message_id, reply_markup=main_markup(), parse_mode="Markdown")

    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=main_markup())

# ================= النشر والمهام الخلفية ================= #

def publish_content(manual_mode=None):
    chats = db_op("SELECT chat_id FROM chats", fetch=True)
    black = [b[0] for b in db_op("SELECT chat_id FROM blacklist", fetch=True)]
    
    choice = manual_mode if manual_mode else random.choice(["tadabor", "hadith", "quran", "azkar"])
    
    content = None
    if choice == "tadabor":
        v, c = fetch_tadabor()
        content = ("video", v, c)
    elif choice == "hadith":
        content = ("text", None, fetch_hadith())
    elif choice == "quran":
        a, c = fetch_quran_audio()
        content = ("audio", a, c)
    else:
        content = ("text", None, f"📿 {random.choice(['سبحان الله', 'الحمد لله', 'الله أكبر'])}")

    for c_id in chats:
        if c_id[0] in black: continue
        try:
            if content[0] == "video": bot.send_video(c_id[0], content[1], caption=content[2], parse_mode="Markdown")
            elif content[0] == "audio": bot.send_audio(c_id[0], content[1], caption=content[2], parse_mode="Markdown")
            else: bot.send_message(c_id[0], content[2], parse_mode="Markdown")
        except: pass

def auto_loop():
    while True:
        conf = db_op("SELECT is_running, interval FROM settings", fetch=True)[0]
        if conf[0] == 1: publish_content()
        time.sleep(conf[1] * 60)

@bot.my_chat_member_handler()
def track_chats(message):
    status = message.new_chat_member.status
    if status in ["administrator", "member"]:
        db_op("INSERT OR IGNORE INTO chats VALUES (?, ?)", (message.chat.id, message.chat.title))
    else:
        db_op("DELETE FROM chats WHERE chat_id = ?", (message.chat.id,))

# ================= التشغيل ================= #
if __name__ == "__main__":
    init_db()
    threading.Thread(target=auto_loop, daemon=True).start()
    print("Admin Bot is Ready!")
    bot.infinity_polling()
