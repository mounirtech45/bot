limport os
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

# عينة من الإذاعات (يمكنك إضافة البقية لاحقاً)
STATIONS = {
    "مشارى العفاسي": "https://backup.qurango.net/radio/mishary_alafasi",
    "ماهر المعيقلي": "https://backup.qurango.net/radio/maher",
    "إذاعة البقرة": "https://backup.qurango.net/radio/albaqarah",
    "الرقية الشرعية": "https://backup.qurango.net/radio/roqiah"
}

def send_msg(target_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": target_id, "text": text, "parse_mode": "Markdown"})
    except: pass

def run_ffmpeg(url):
    # إيقاف أي بث قديم فوراً
    subprocess.run("pkill -9 ffmpeg", shell=True)
    
    # أمر البث المعدل ليكون أكثر توافقاً مع الخوادم
    # أضفنا -reconnect لضمان عدم انقطاع البث إذا تعثر الإنترنت
    command = (
        f'ffmpeg -re -loop 1 -i {IMAGE_PATH} '
        f'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 '
        f'-i "{url}" -c:v libx264 -preset ultrafast -tune zerolatency '
        f'-b:v 600k -pix_fmt yuv420p -c:a aac -b:a 128k -ar 44100 '
        f'-f flv "{RTMP_URL}"'
    )
    
    # تشغيل الأمر وتسجيل المخرجات في الـ Logs لمراقبتها
    subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

async def broadcast_task(name, url):
    post_text = (
        f"📡 **بدأ البث المباشر الآن**\n\n"
        f"🎙 **المحتوى:** {name}\n"
        f"🎧 انضم للبث الصوتي في أعلى القناة."
    )
    send_msg(CHAT_ID, post_text)
    run_ffmpeg(url)
    print(f"🚀 Attempting to stream: {name}")

async def bot_polling():
    last_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_id + 1}&timeout=20"
            resp = requests.get(url).json()
            for up in resp.get("result", []):
                last_id = up["update_id"]
                msg = up.get("message", {})
                text = msg.get("text", "")
                user_id = str(msg.get("from", {}).get("id", ""))

                if user_id == ADMIN_ID:
                    if text.startswith("/stream"):
                        name = text.replace("/stream ", "").strip()
                        if name in STATIONS:
                            send_msg(ADMIN_ID, f"⏳ جاري تشغيل بث {name}...")
                            await broadcast_task(name, STATIONS[name])
                    
                    elif text.startswith("/schedule"):
                        parts = text.split()
                        if len(parts) >= 3:
                            time_str = parts[-1]
                            name = " ".join(parts[1:-1])
                            if name in STATIONS:
                                h, m = time_str.split(":")
                                scheduler.add_job(broadcast_task, "cron", hour=int(h), minute=int(m), args=[name, STATIONS[name]])
                                send_msg(ADMIN_ID, f"✅ تم جدولة {name} الساعة {time_str}")
        except: await asyncio.sleep(5)
        await asyncio.sleep(1)

async def main():
    scheduler.start()
    await bot_polling()

if __name__ == "__main__":
    asyncio.run(main())
