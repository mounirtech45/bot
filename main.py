import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import threading
import time
import random
import sqlite3
import os

# ================= الإعدادات الأساسية ================= #
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
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
    except: return []

def init_db():
    # الإعدادات: التشغيل، التوقيت، كود القارئ المختار
    db_op('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, is_running INTEGER, interval INTEGER, reciter_code TEXT DEFAULT "afs")')
    # القنوات والمجموعات
    db_op('CREATE TABLE IF NOT EXISTS chats (chat_id INTEGER PRIMARY KEY, title TEXT)')
    # حالة الخدمات (تشغيل/إيقاف)
    db_op('CREATE TABLE IF NOT EXISTS services (name TEXT PRIMARY KEY, status INTEGER DEFAULT 1)')
    # السور المختارة صوتياً
    db_op('CREATE TABLE IF NOT EXISTS selected_surahs (surah_no INTEGER PRIMARY KEY)')

    if not db_op("SELECT * FROM settings", fetch=True):
        db_op("INSERT INTO settings (id, is_running, interval, reciter_code) VALUES (1, 1, 60, 'afs')")
    
    for srv in ['audio_surahs', 'tadabor_video', 'azkar']:
        db_op("INSERT OR IGNORE INTO services VALUES (?, 1)", (srv,))

# ================= قائمة القراء والسور ================= #
RECITERS = {
    "afs": "مشاري العفاسي",
    "minsh": "المنشاوي (مُجود)",
    "abd": "عبد الباسط (مُجود)",
    "yasser": "ياسر الدوسري",
    "shur": "سعود الشريم",
    "husr": "محمود خليل الحصري",
    "qtm": "ناصر القطامي",
    "maher": "ماهر المعيقلي"
}

ALL_SURAHS = ["الفاتحة", "البقرة", "آل عمران", "النساء", "المائدة", "الأنعام", "الأعراف", "الأنفال", "التوبة", "يونس", "هود", "يوسف", "الرعد", "إبراهيم", "الحجر", "النحل", "الإسراء", "الكهف", "مريم", "طه", "الأنبياء", "الحج", "المؤمنون", "النور", "الفرقان", "الشعراء", "النمل", "القصص", "العنكبوت", "الروم", "لقمان", "السجدة", "الأحزاب", "سبأ", "فاطر", "يس", "الصافات", "ص", "الزمر", "غافر", "فصلت", "الشورى", "الزخرف", "الدخان", "الجاثية", "الأحقاف", "محمد", "الفتح", "الحجرات", "ق", "الذاريات", "الطور", "النجم", "القمر", "الرحمن", "الواقعة", "الحديد", "المجادلة", "الحشر", "الممتحنة", "الصف", "الجمعة", "المنافقون", "التغابن", "الطلاق", "التحريم", "الملك", "القلم", "الحاقة", "المعارج", "نوح", "الجن", "المزمل", "المدثر", "القيامة", "الإنسان", "المرسلات", "النبأ", "النازعات", "عبس", "التكوير", "الانفطار", "المطففين", "الانشقاق", "البروج", "الطارق", "الأعلى", "الغاشية", "الفجر", "البلد", "الشمس", "الليل", "الضحى", "الشرح", "التين", "العلق", "القدر", "البينة", "الزلزلة", "العاديات", "القارعة", "التكاثر", "العصر", "الهمزة", "الفيل", "قريش", "الماعون", "الكوثر", "الكافرون", "النصر", "المسد", "الإخلاص", "الفلق", "الناس"]

# ================= محركات جلب المحتوى ================= #

def get_audio_surah():
    selected = db_op("SELECT surah_no FROM selected_surahs", fetch=True)
    reciter = db_op("SELECT reciter_code FROM settings", fetch=True)[0][0]
    if not selected: return None
    s_no = random.choice(selected)[0]
    formatted_no = str(s_no).zfill(3)
    # روابط صوتية من سيرفرات mp3quran
    audio_url = f"https://server8.mp3quran.net/{reciter}/{formatted_no}.mp3"
    msg = f"🔊 *تلاوة مباركة*\n📖 سورة: {ALL_SURAHS[s_no-1]}\n🎙 بصوت: {RECITERS.get(reciter)}"
    return "audio", audio_url, msg

def get_tadabor():
    try:
        res = requests.get("https://mp3quran.net/api/v3/tadabor").json()
        items = []
        for sora in res['tadabor']: items.extend(res['tadabor'][sora])
        it = random.choice(items)
        return "video", it['video_url'], f"🎥 *تدبر آية*\n✨ {it['title']}"
    except: return None

# ================= لوحات التحكم (الواجهة) ================= #

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id == ADMIN_ID:
        show_main_menu(message.chat.id)

def show_main_menu(chat_id, message_id=None):
    m = InlineKeyboardMarkup(row_width=1)
    # 1. إدارة الخدمات
    srvs = db_op("SELECT name, status FROM services", fetch=True)
    names_map = {"audio_surahs": "الصوتيات", "tadabor_video": "فيديوهات تدبر", "azkar": "الأذكار"}
    for name, stat in srvs:
        icon = "🟢" if stat == 1 else "🔴"
        m.add(InlineKeyboardButton(f"{icon} خدمة {names_map[name]}", callback_data=f"tg_{name}"))
    
    # 2. خيارات التخصيص
    m.row(InlineKeyboardButton("🎙 اختيار القارئ", callback_data="list_recs"),
          InlineKeyboardButton("🎼 اختيار السور", callback_data="pg_0"))
    m.add(InlineKeyboardButton("⏱ ضبط وقت النشر", callback_data="m_time"))

    txt = "🕋 **لوحة تحكم البوت الشاملة**\nتحكم في الخدمات، القراء، والسور من هنا:"
    if message_id: bot.edit_message_text(txt, chat_id, message_id, reply_markup=m, parse_mode="Markdown")
    else: bot.send_message(chat_id, txt, reply_markup=m, parse_mode="Markdown")

def get_surahs_markup(page=0):
    m = InlineKeyboardMarkup(row_width=2)
    per_page = 10
    start, end = page*per_page, (page+1)*per_page
    selected = [s[0] for s in db_op("SELECT surah_no FROM selected_surahs", fetch=True)]
    
    for i, name in enumerate(ALL_SURAHS[start:end]):
        s_num = start + i + 1
        m.add(InlineKeyboardButton(f"{'✅' if s_num in selected else '▫️'} {name}", callback_data=f"as_{s_num}_{page}"))
    
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"pg_{page-1}"))
    if end < 114: nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"pg_{page+1}"))
    if nav: m.row(*nav)
    m.add(InlineKeyboardButton("🏠 العودة للرئيسية", callback_data="back_main"))
    return m

# ================= معالجة الطلبات (Callbacks) ================= #

@bot.callback_query_handler(func=lambda call: True)
def handle_queries(call):
    if call.from_user.id != ADMIN_ID: return

    # تبديل حالة الخدمة
    if call.data.startswith("tg_"):
        srv = call.data.split("_")[1]
        db_op("UPDATE services SET status = 1 - status WHERE name = ?", (srv,))
        show_main_menu(call.message.chat.id, call.message.message_id)

    # قائمة القراء
    elif call.data == "list_recs":
        m = InlineKeyboardMarkup(row_width=2)
        curr = db_op("SELECT reciter_code FROM settings", fetch=True)[0][0]
        for code, name in RECITERS.items():
            m.add(InlineKeyboardButton(f"{'🔹 ' if code==curr else ''}{name}", callback_data=f"setr_{code}"))
        m.add(InlineKeyboardButton("🏠 عودة", callback_data="back_main"))
        bot.edit_message_text("🎙 **اختر القارئ المفضل لنشر السور:**", call.message.chat.id, call.message.message_id, reply_markup=m)

    elif call.data.startswith("setr_"):
        code = call.data.split("_")[1]
        db_op("UPDATE settings SET reciter_code = ?", (code,))
        handle_queries(type('obj', (object,), {'from_user': call.from_user, 'data': 'list_recs', 'message': call.message}))

    # نظام الصفحات للسور
    elif call.data.startswith("pg_"):
        p = int(call.data.split("_")[1])
        bot.edit_message_text("🎼 **اختر السور المراد نشرها صوتياً:**", call.message.chat.id, call.message.message_id, reply_markup=get_surahs_markup(p))

    elif call.data.startswith("as_"):
        _, s_num, p = call.data.split("_")
        if db_op("SELECT * FROM selected_surahs WHERE surah_no = ?", (s_num,), fetch=True):
            db_op("DELETE FROM selected_surahs WHERE surah_no = ?", (s_num,))
        else: db_op("INSERT INTO selected_surahs VALUES (?)", (s_num,))
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=get_surahs_markup(int(p)))

    elif call.data == "back_main":
        show_main_menu(call.message.chat.id, call.message.message_id)

# ================= محرك النشر التلقائي ================= #

def loop_thread():
    while True:
        try:
            conf = db_op("SELECT is_running, interval FROM settings", fetch=True)[0]
            if conf[0] == 1:
                active = [s[0] for s in db_op("SELECT name FROM services WHERE status = 1", fetch=True)]
                if active:
                    srv = random.choice(active)
                    res = get_audio_surah() if srv == 'audio_surahs' else get_tadabor() if srv == 'tadabor_video' else ("text", None, "📿 ذكر الله يطمئن القلوب")
                    if res:
                        chats = db_op("SELECT chat_id FROM chats", fetch=True)
                        for c in chats:
                            try:
                                if res[0] == "audio": bot.send_audio(c[0], res[1], caption=res[2], parse_mode="Markdown")
                                elif res[0] == "video": bot.send_video(c[0], res[1], caption=res[2], parse_mode="Markdown")
                                else: bot.send_message(c[0], res[2], parse_mode="Markdown")
                            except: continue
            time.sleep(conf[1] * 60)
        except: time.sleep(60)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=loop_thread, daemon=True).start()
    bot.infinity_polling()
