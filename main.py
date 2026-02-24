import os
import asyncio
import subprocess
import pytz
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- الإعدادات ---
# يتم جلبها من متغيرات Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")
RTMP_URL = os.getenv("RTMP_URL")
CHAT_ID = os.getenv("CHAT_ID")
ADMIN_ID = os.getenv("ADMIN_ID")

# توقيت الجزائر
ALGERIA_TZ = pytz.timezone("Africa/Algiers")
IMAGE_PATH = "icons/image.jpg"

scheduler = AsyncIOScheduler(timezone=ALGERIA_TZ)

# دالة إرسال الرسائل (بدون Pyrogram لتجنب أخطاء API_ID)
def send_msg(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending message: {e}")

# دالة تشغيل البث عبر FFmpeg
def run_ffmpeg(source_url):
    command = [
        'ffmpeg', '-re', '-loop', '1', '-i', IMAGE_PATH,
        '-i', source_url, '-c:v', 'libx264', '-preset', 'ultrafast',
        '-b:v', '600k', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k',
        '-f', 'flv', RTMP_URL
    ]
    # التشغيل كعملية مستقلة في الخلفية
    subprocess.Popen(command)

# المهمة المنفذة وقت البث
async def start_broadcast_job(reciter, surah_name, source_url):
    post_text = (
        f"📡 **بدأ البث المباشر الآن (توقيت الجزائر)**\n\n"
        f"📖 **السورة:** {surah_name}\n"
        f"🎙 **القارئ:** {reciter}\n\n"
        f"🤲 اللهم اجعل القرآن الكريم ربيع قلوبنا.\n\n"
        f"🎧 انضم للبث في أعلى القناة للاستماع."
    )
    send_msg(post_text)
    run_ffmpeg(source_url)
    print(f"🚀 بدأ البث المباشر لـ {surah_name}")

# نظام مراقبة الأوامر (بديل خفيف لـ Pyrogram)
async def bot_polling():
    last_update_id = 0
    print("✅ البث المجدول يعمل الآن... في انتظار الأوامر.")
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=30"
            resp = requests.get(url).json()
            for update in resp.get("result", []):
                last_update_id = update["update_id"]
                msg = update.get("message", {})
                text = msg.get("text", "")
                user_id = str(msg.get("from", {}).get("id", ""))

                if text.startswith("/schedule") and user_id == ADMIN_ID:
                    # /schedule [القارئ] [السورة] [الرابط] [HH:MM]
                    parts = text.split(maxsplit=4)
                    if len(parts) == 5:
                        reciter, surah, s_url, t_str = parts[1], parts[2], parts[3], parts[4]
                        h, m = t_str.split(":")
                        scheduler.add_job(
                            start_broadcast_job, "cron", 
                            hour=int(h), minute=int(m), 
                            args=[reciter, surah, s_url],
                            id=f"job_{h}_{m}", replace_existing=True
                        )
                        send_msg(f"✅ تم ضبط الجدول:\n📖 {surah}\n⏰ الساعة {t_str} بتوقيت الجزائر")
        except Exception as e:
            await asyncio.sleep(5)
        await asyncio.sleep(1)

async def main():
    scheduler.start()
    await bot_polling()

if __name__ == "__main__":
    asyncio.run(main())
