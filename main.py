import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import threading
import time
import random
import sqlite3
import os

# ================= جلب الإعدادات من متغيرات البيئة ================= #
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else 0

bot = telebot.TeleBot(TOKEN)

# ================= إدارة التخزين (SQLite) ================= #
def init_db():
    conn = sqlite3.connect('islamic_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, is_running INTEGER, interval INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS chats (chat_id INTEGER PRIMARY KEY)')
    if cursor.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0:
        cursor.execute("INSERT INTO settings VALUES (1, 1, 60)")
    conn.commit()
    conn.close()

def db_op(query, params=(), fetch=False):
    conn = sqlite3.connect('islamic_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(query, params)
    res = cursor.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return res

# ================= دوال جلب المحتوى ================= #

def fetch_hadith():
    try:
        res = requests.get("https://hadeethenc.com/api/v1/hadeeths/list/?language=ar&category_id=1&per_page=40", timeout=10).json()
        h_id = random.choice(res['data'])['id']
        h_details = requests.get(f"https://hadeethenc.com/api/v1/hadeeths/one/?language=ar&id={h_id}", timeout=10).json()
        return f"📜 *حديث نبوي شريف:*\n\n{h_details['hadeeth']}\n\n📖 *المصدر:* {h_details['attribution']}"
    except:
        return "📜 قال ﷺ: «مَنْ صَلَّى عَلَيَّ صَلَاةً صَلَّى الله عَلَيْهِ بِهَا عَشْرًا»"

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

# ================= نظام النشر التلقائي ================= #

def get_any_content():
    choice = random.choice(["hadith", "tadabor", "quran", "azkar"])
    if choice == "hadith":
        return "text", fetch_hadith(), None
    elif choice == "tadabor":
        v, c = fetch_tadabor()
        return ("video", c, v) if v else ("text", fetch_hadith(), None)
    elif choice == "quran":
        a, c = fetch_quran_audio()
        return ("audio", c, a) if a else ("text", fetch_hadith(), None)
    else:
        azkar = ["سبحان الله وبحمده", "لا إله إلا الله", "أستغفر الله", "لا حول ولا قوة إلا بالله"]
        return "text", f"📿 {random.choice(azkar)}", None

def auto_publisher():
    while True:
        conf = db_op("SELECT is_running, interval FROM settings WHERE id=1", fetch=True)[0]
        if conf[0] == 1:
            chats = db_op("SELECT chat_id FROM chats", fetch=True)
            if chats:
                ctype, msg, media = get_any_content()
                for chat in chats:
                    try:
                        if ctype == "video": bot.send_video(chat[0], media, caption=msg, parse_mode="Markdown")
                        elif ctype == "audio": bot.send_audio(chat[0], media, caption=msg, parse_mode="Markdown")
                        else: bot.send_message(chat[0], msg, parse_mode="Markdown")
                    except: pass
        time.sleep(conf[1] * 60)

# ================= الأوامر والتحكم ================= #

@bot.my_chat_member_handler()
def track_chats(message):
    status = message.new_chat_member.status
    if status in ["administrator", "member"]:
        db_op("INSERT OR IGNORE INTO chats (chat_id) VALUES (?)", (message.chat.id,))
    else:
        db_op("DELETE FROM chats WHERE chat_id = ?", (message.chat.id,))

@bot.message_handler(commands=['start', 'admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "مرحباً بك! أضف البوت لقناتك وارفعني مشرفاً ليبدأ النشر تلقائياً.")
        return
    
    conf = db_op("SELECT is_running, interval FROM settings WHERE id=1", fetch=True)[0]
    chats_count = db_op("SELECT COUNT(*) FROM chats", fetch=True)[0][0]
    
    markup = InlineKeyboardMarkup()
    btn_status = "🛑 إيقاف" if conf[0] == 1 else "✅ تشغيل"
    markup.add(InlineKeyboardButton(btn_status, callback_data="toggle"))
    markup.add(InlineKeyboardButton(f"⏱ كل {conf[1]} دقيقة", callback_data="time"))
    markup.add(InlineKeyboardButton(f"📊 القنوات: {chats_count}", callback_data="info"))
    
    bot.send_message(message.chat.id, "🛠 **لوحة تحكم البوت:**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    if call.data == "toggle":
        db_op("UPDATE settings SET is_running = 1 - is_running WHERE id=1")
    elif call.data == "time":
        times = [30, 60, 120, 360]
        curr = db_op("SELECT interval FROM settings WHERE id=1", fetch=True)[0][0]
        new_t = times[(times.index(curr)+1)%len(times)] if curr in times else 60
        db_op("UPDATE settings SET interval = ? WHERE id=1", (new_t,))
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    admin_panel(call)

# ================= التشغيل النهائي ================= #
if __name__ == "__main__":
    init_db()
    threading.Thread(target=auto_publisher, daemon=True).start()
    print("Bot is Live...")
    bot.infinity_polling()
