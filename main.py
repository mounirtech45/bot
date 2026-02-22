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
    if not db_op("SELECT * FROM settings", fetch=True):
        db_op("INSERT INTO settings VALUES (1, 1, 60)")

# ================= جلب المحتوى من API التدبر ================= #

def fetch_tadabor_data():
    try:
        res = requests.get("https://mp3quran.net/api/v3/tadabor", timeout=20).json()
        all_items = []
        if 'tadabor' in res:
            for sora_id in res['tadabor']:
                for item in res['tadabor'][sora_id]:
                    all_items.append(item)
        return all_items
    except:
        return []

def get_content(target_type=None):
    mode = target_type if target_type else random.choice(["video", "image", "hadith", "azkar"])
    
    if mode in ["video", "image"]:
        items = fetch_tadabor_data()
        if items:
            item = random.choice(items)
            caption = f"📖 *سورة {item.get('sora_name', '')}*\n🎙 القارئ: {item.get('reciter_name', 'غير معروف')}\n\n✨ {item.get('title', '')}"
            if mode == "video" and item.get('video_url'):
                return "video", item['video_url'], caption
            elif mode == "image" and item.get('image_url'):
                return "photo", item['image_url'], caption
        mode = "hadith"

    if mode == "hadith":
        try:
            res = requests.get("https://hadeethenc.com/api/v1/hadeeths/list/?language=ar&category_id=1&per_page=50").json()
            h_id = random.choice(res['data'])['id']
            h = requests.get(f"https://hadeethenc.com/api/v1/hadeeths/one/?language=ar&id={h_id}").json()
            return "text", None, f"📜 *حديث نبوي:*\n\n{h['hadeeth']}\n\n📖 {h['attribution']}"
        except:
            return "text", None, "📿 سبحان الله وبحمده، سبحان الله العظيم."

    return "text", None, "📿 لا إله إلا الله وحده لا شريك له"

# ================= وظائف النشر ================= #

def publish_to_all(ctype, media, msg):
    chats = db_op("SELECT chat_id FROM chats", fetch=True)
    success = 0
    for c_id in chats:
        try:
            if ctype == "video":
                bot.send_video(c_id[0], media, caption=msg, parse_mode="Markdown")
            elif ctype == "photo":
                bot.send_photo(c_id[0], media, caption=msg, parse_mode="Markdown")
            else:
                bot.send_message(c_id[0], msg, parse_mode="Markdown")
            success += 1
        except:
            continue
    return success

def auto_loop():
    while True:
        conf = db_op("SELECT is_running, interval FROM settings", fetch=True)[0]
        if conf[0] == 1:
            ctype, media, msg = get_content()
            publish_to_all(ctype, media, msg)
        time.sleep(conf[1] * 60)

# ================= لوحة تحكم الأدمن ================= #

def main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    conf = db_op("SELECT is_running, interval FROM settings", fetch=True)[0]
    status_text = "✅ النشر يعمل" if conf[0] == 1 else "🛑 النشر متوقف"
    
    markup.add(InlineKeyboardButton(status_text, callback_data="toggle_run"))
    markup.add(InlineKeyboardButton(f"⏱ كل {conf[1]} دقيقة", callback_data="menu_time"))
    markup.add(InlineKeyboardButton("📊 عرض القنوات", callback_data="list_chats"))
    markup.add(InlineKeyboardButton("🎥 نشر فيديو فوري", callback_data="inst_video"))
    markup.add(InlineKeyboardButton("🖼 نشر صورة فورية", callback_data="inst_image"))
    markup.add(InlineKeyboardButton("📢 إذاعة (نص)", callback_data="broadcast"))
    return markup

@bot.message_handler(commands=['start', 'admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⚠️ هذا البوت للنشر التلقائي في القنوات.")
        return
    bot.send_message(message.chat.id, "🛠 **لوحة تحكم الأدمن:**", reply_markup=main_menu(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.from_user.id != ADMIN_ID: return

    if call.data == "toggle_run":
        db_op("UPDATE settings SET is_running = 1 - is_running")
    
    elif call.data == "list_chats":
        chats = db_op("SELECT chat_id, title FROM chats", fetch=True)
        if not chats:
            text = "❌ لا توجد قنوات مسجلة حالياً."
        else:
            text = "📊 **القنوات والمجموعات المسجلة:**\n\n"
            for i, c in enumerate(chats, 1):
                text += f"{i}. `{c[0]}` - {c[1]}\n"
        
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ عودة", callback_data="back_main"))
        return bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "menu_time":
        markup = InlineKeyboardMarkup()
        for t in [15, 30, 60, 120, 360]:
            markup.add(InlineKeyboardButton(f"كل {t} دقيقة", callback_data=f"set_{t}"))
        markup.add(InlineKeyboardButton("⬅️ عودة", callback_data="back_main"))
        return bot.edit_message_text("⏱ اختر وقت النشر التلقائي:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("set_"):
        t = int(call.data.split("_")[1])
        db_op("UPDATE settings SET interval = ?", (t,))
        bot.answer_callback_query(call.id, f"تم تغيير الوقت إلى {t} دقيقة")

    elif call.data.startswith("inst_"):
        ctype, media, msg = get_content(call.data.split("_")[1])
        bot.answer_callback_query(call.id, "جاري النشر...")
        res = publish_to_all(ctype, media, msg)
        bot.send_message(call.message.chat.id, f"✅ تم النشر في {res} قناة.")

    elif call.data == "back_main":
        pass # سيقوم التحديث في الأسفل بإعادة القائمة الرئيسية

    bot.edit_message_text("🛠 **لوحة تحكم الأدمن:**", call.message.chat.id, call.message.message_id, reply_markup=main_menu(), parse_mode="Markdown")

# ================= إدارة القنوات تلقائياً ================= #

@bot.my_chat_member_handler()
def auto_track(message):
    new = message.new_chat_member
    if new.status in ["administrator", "member"]:
        title = message.chat.title if message.chat.title else "بدون عنوان"
        db_op("INSERT OR IGNORE INTO chats VALUES (?, ?)", (message.chat.id, title))
    else:
        db_op("DELETE FROM chats WHERE chat_id = ?", (message.chat.id,))

# ================= التشغيل ================= #
if __name__ == "__main__":
    init_db()
    threading.Thread(target=auto_loop, daemon=True).start()
    print("Bot is ready...")
    bot.infinity_polling()
