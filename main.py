import os
import asyncio
import subprocess
import pytz
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- الإعدادات ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
RTMP_URL = os.getenv("RTMP_URL")
CHAT_ID = os.getenv("CHAT_ID")
ADMIN_ID = os.getenv("ADMIN_ID")

ALGERIA_TZ = pytz.timezone("Africa/Algiers")
IMAGE_PATH = "icons/image.jpg"

scheduler = AsyncIOScheduler(timezone=ALGERIA_TZ)

# --- قائمة الإذاعات (مدمجة من الكود الخاص بك) ---
STATIONS = {
    "مشارى العفاسي": "https://backup.qurango.net/radio/mishary_alafasi",
    "ماهر المعيقلي": "https://backup.qurango.net/radio/maher",
    "عبدالباسط مجود": "https://backup.qurango.net/radio/abdulbasit_abdulsamad_mojawwad",
    "المنشاوي": "https://backup.qurango.net/radio/mohammed_siddiq_alminshawi",
    "ياسر الدوسري": "https://backup.qurango.net/radio/yasser_aldosari",
    "سعد الغامدي": "https://backup.qurango.net/radio/saad_alghamdi",
    "إذاعة البقرة": "https://backup.qurango.net/radio/albaqarah",
    "الرقية الشرعية": "https://backup.qurango.net/radio/roqiah",
    "أذكار الصباح": "https://backup.qurango.net/radio/athkar_sabah",
    "أذكار المساء": "https://backup.qurango.net/radio/athkar_masa",
}

# دالة إرسال الرسائل
def send_msg(target_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": target_id, "text": text, "parse_mode": "Markdown"})

# دالة تشغيل البث FFmpeg
def run_ffmpeg(url):
    # pkill لإيقاف أي بث سابق قبل بدء الجديد
    subprocess.run(["pkill", "-f", "ffmpeg"])
    
    command = [
        'ffmpeg', '-re', '-loop', '1', '-i', IMAGE_PATH,
        '-i', url, '-c:v', 'libx264', '-preset', 'ultrafast',
        '-b:v', '600k', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k',
        '-f', 'flv', RTMP_URL
    ]
    subprocess.Popen(command)

# مهمة البث
async def broadcast_task(name, url):
    post_text = (
        f"📡 **بدأ البث المباشر الآن (إذاعة القرآن)**\n\n"
        f"🎙 **المحتوى:** {name}\n"
        f"🕒 **التوقيت:** الجزائر العاصمة\n\n"
        f"🤲 نسأل الله أن يتقبل منا ومنكم صالح الأعمال.\n\n"
        f"🎧 انضم للبث الصوتي في أعلى القناة."
    )
    send_msg(CHAT_ID, post_text)
    run_ffmpeg(url)

# نظام استقبال الأوامر
async def bot_polling():
    last_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_id + 1}&timeout=10"
            updates = requests.get(url).json().get("result", [])
            for up in updates:
                last_id = up["update_id"]
                msg = up.get("message", {})
                text = msg.get("text", "")
                user_id = str(msg.get("from", {}).get("id", ""))

                if user_id == ADMIN_ID:
                    # 1. بث فوري للتجربة: /stream اسم_الإذاعة
                    # مثال: /stream مشارى العفاسي
                    if text.startswith("/stream"):
                        name = text.replace("/stream ", "").strip()
                        if name in STATIONS:
                            send_msg(ADMIN_ID, f"🚀 جاري بدء بث {name} فوراً...")
                            await broadcast_task(name, STATIONS[name])
                        else:
                            send_msg(ADMIN_ID, "❌ الاسم غير موجود في القائمة.")

                    # 2. جدولة: /schedule اسم_الإذاعة 04:40
                    elif text.startswith("/schedule"):
                        parts = text.split()
                        if len(parts) >= 3:
                            time_str = parts[-1]
                            name = " ".join(parts[1:-1])
                            if name in STATIONS:
                                h, m = time_str.split(":")
                                scheduler.add_job(broadcast_task, "cron", hour=int(h), minute=int(m), args=[name, STATIONS[name]])
                                send_msg(ADMIN_ID, f"✅ تم جدولة {name} الساعة {time_str} (الجزائر).")

        except: pass
        await asyncio.sleep(1)

async def main():
    scheduler.start()
    await bot_polling()

if __name__ == "__main__":
    asyncio.run(main())
