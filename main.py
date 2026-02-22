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

if not TOKEN or ADMIN_ID == 0:
    print("❌ خطأ: يرجى ضبط BOT_TOKEN و ADMIN_ID في متغيرات البيئة!")

bot = telebot.TeleBot(TOKEN)

# ================= قاعدة البيانات ================= #
def db_op(query, params=(), fetch=False):
    try:
        conn = sqlite3.connect('islamic_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(query, params)
        res = cursor.fetchall() if fetch else None
        conn.commit()
        conn.close()
        return res
    except Exception as e:
        print(f"Database Error: {e}")
        return []

def init_db():
    db_op('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, is_running INTEGER, interval INTEGER)')
    db_op('CREATE TABLE IF NOT EXISTS chats (chat_id INTEGER PRIMARY KEY, title TEXT)')
    if not db_op("SELECT * FROM settings", fetch=True):
        db_op("INSERT INTO settings VALUES (1, 1, 60)")

# ================= جلب المحتوى (APIs فقط) ================= #

def fetch_tadabor_api():
    """جلب فيديو أو صورة من تدبر"""
    try:
        res = requests.get("https://mp3quran.net/api/v3/tadabor", timeout=15).json()
        items = []
        if 'tadabor' in res:
            for sora in res['tadabor']:
                items.extend(res['tadabor'][sora])
        return random.choice(items) if items else None
    except: return None

def fetch_full_tafsir():
    """آية + تفسير + صوت"""
    try:
        ayah_num = random.randint(1, 6236)
        res_t = requests.get(f"https://api.alquran.cloud/v1/ayah/{ayah_num}/ar.jalalayn", timeout=10).json()
        res_a = requests.get(f"https://api.alquran.cloud/v1/ayah/{ayah_num}/ar.alafasy", timeout=10).json()
        d = res_t['data']
        msg = f"📖 *قَالَ تَعَالَى:* `{d['text']}`\n\n📗 *التفسير:* {d['text']}\n\n📝 {d['surah']['name']} | {d['numberInSurah']}"
        return "audio", res_a['data']['audio'], msg
    except: return "text", None, "📿 سبحان الله وبحمده"

def fetch_hadith_api():
    """حديث نبوي"""
    try:
        res = requests.get("https://hadeethenc.com/api/v1/hadeeths/list/?language=ar&category_id=1&per_page=50", timeout=10).json()
        h_id = random.choice(res['data'])['id']
        h = requests.get(f"https://hadeethenc.com/api/v1/hadeeths/one/?language=ar&id={h_id}", timeout=10).json()
        return f"📜 *حديث شريف:*\n\n{h['hadeeth']}\n\n📖 {h['attribution']}"
    except: return "📜 قال ﷺ: «مَنْ صَلَّى عَلَيَّ صَلَاةً صَلَّى الله عَلَيْهِ بِهَا عَشْرًا»"

def fetch_azkar_api():
    """أذكار منوعة"""
    try:
        res = requests.get("https://raw.githubusercontent.com/nawafalbagmi/azkar-api/master/azkar.json", timeout=10).json()
        cat = random.choice(list(res.keys()))
        item = random.choice(res[cat])
        return f"📿 *ذكر ({cat}):*\n\n{item['content']}"
    except: return "📿 لا إله إلا الله وحده لا شريك له"

# ================= محرك اختيار المحتوى ================= #

def get_content(mode=None):
    if not mode:
        mode = random.choice(["video", "image", "hadith", "full_tafsir", "azkar"])
    
    if mode == "full_tafsir":
        return fetch_full_tafsir()
    
    if mode in ["video", "image"]:
        it = fetch_tadabor_api()
        if it:
            cap = f"🎥 *تدبر* | سورة {it.get('sora_name','')}\n🎙 القارئ: {it.get('reciter_name','')}\n\n✨ {it.get('title','')}"
            if mode == "video" and it.get('video_url'): return "video", it['video_url'], cap
            if mode == "image" and it.get('image_url'): return "photo", it['image_url'], cap
    
    if mode == "azkar": return "text", None, fetch_azkar_api()
    return "text", None, fetch_hadith_api()

def publish_all(ctype, media, msg):
    chats = db_op("SELECT chat_id FROM chats", fetch=True)
    success = 0
    for c in chats:
        try:
            if ctype == "video": bot.send_video(c[0], media, caption=msg, parse_mode="Markdown")
            elif ctype == "photo": bot.send_photo(c[0], media, caption=msg, parse_mode="Markdown")
            elif ctype == "audio": bot.send_audio(c[0], media, caption=msg, parse_mode="Markdown")
            else: bot.send_message(c[0], msg, parse_mode="Markdown")
            success += 1
        except: pass
    return success

# ================= لوحة التحكم ================= #

def main_markup():
    m = InlineKeyboardMarkup(row_width=2)
    conf = db_op("SELECT is_running, interval FROM settings", fetch=True)[0]
    m.add(InlineKeyboardButton("✅ تشغيل" if conf[0]==1 else "🛑 إيقاف", callback_data="toggle"))
    m.add(InlineKeyboardButton(f"⏱ كل {conf[1]} دقيقة", callback_data="m_time"))
    m.add(InlineKeyboardButton("📊 القنوات", callback_data="m_list"), InlineKeyboardButton("🚀 نشر فوري", callback_data="m_instant"))
    return m

@bot.message_handler(commands=['start', 'admin'])
def admin_cmd(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, "🕋 **لوحة إدارة البوت:**", reply_markup=main_markup(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def calls(call):
    if call.from_user.id != ADMIN_ID: return
    
    if call.data == "toggle":
        db_op("UPDATE settings SET is_running = 1 - is_running")
    elif call.data == "m_list":
        chats = db_op("SELECT chat_id, title FROM chats", fetch=True)
        txt = "📊 **القنوات:**\n\n" + ("❌ لا يوجد" if not chats else "\n".join([f"• `{c[0]}` | {c[1]}" for c in chats]))
        return bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ عودة", callback_data="back")), parse_mode="Markdown")
    elif call.data == "m_instant":
        m = InlineKeyboardMarkup(row_width=2)
        m.add(InlineKeyboardButton("🎥 فيديو", callback_data="i_video"), InlineKeyboardButton("🔊 آية+صوت", callback_data="i_full_tafsir"),
              InlineKeyboardButton("📜 حديث", callback_data="i_hadith"), InlineKeyboardButton("📿 ذكر", callback_data="i_azkar"),
              InlineKeyboardButton("⬅️ عودة", callback_data="back"))
        return bot.edit_message_text("🚀 اختر نوع النشر الفوري:", call.message.chat.id, call.message.message_id, reply_markup=m)
    elif call.data.startswith("i_"):
        bot.answer_callback_query(call.id, "جاري النشر...")
        ctype, med, msg = get_content(call.data.split("_")[1])
        publish_all(ctype, med, msg)
        return
    elif call.data == "m_time":
        m = InlineKeyboardMarkup()
        for t in [30, 60, 120, 360]: m.add(InlineKeyboardButton(f"{t} دقيقة", callback_data=f"set_{t}"))
        return bot.edit_message_text("⏱ اختر وقت النشر:", call.message.chat.id, call.message.message_id, reply_markup=m)
    elif call.data.startswith("set_"):
        db_op("UPDATE settings SET interval = ?", (int(call.data.split("_")[1]),))

    bot.edit_message_text("🕋 **لوحة إدارة البوت:**", call.message.chat.id, call.message.message_id, reply_markup=main_markup(), parse_mode="Markdown")

# ================= النظام الآلي ================= #

def loop_thread():
    while True:
        try:
            conf = db_op("SELECT is_running, interval FROM settings", fetch=True)[0]
            if conf[0] == 1:
                ctype, med, msg = get_content()
                publish_all(ctype, med, msg)
            time.sleep(conf[1] * 60)
        except: time.sleep(60)

@bot.my_chat_member_handler()
def track_chats(m):
    if m.new_chat_member.status in ["administrator", "member"]:
        title = m.chat.title if m.chat.title else "قناة/مجموعة"
        db_op("INSERT OR IGNORE INTO chats VALUES (?, ?)", (m.chat.id, title))
    else:
        db_op("DELETE FROM chats WHERE chat_id = ?", (m.chat.id,))

if __name__ == "__main__":
    init_db()
    threading.Thread(target=loop_thread, daemon=True).start()
    print("Bot is Live...")
    bot.infinity_polling()
