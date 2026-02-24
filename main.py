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
ADMIN_ID = os.getenv("ADMIN_ID") # آيدي حسابك لتلقي الرسائل الخاصة

ALGERIA_TZ = pytz.timezone("Africa/Algiers")
IMAGE_PATH = "icons/image.jpg"

scheduler = AsyncIOScheduler(timezone=ALGERIA_TZ)

# دالة إرسال الرسائل (إلى القناة أو الخاص)
def send_msg(target_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": target_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error: {e}")

# دالة تشغيل المحرك FFmpeg
def run_ffmpeg(source_url):
    command = [
        'ffmpeg', '-re', '-loop', '1', '-i', IMAGE_PATH,
        '-i', source_url, '-c:v', 'libx264', '-preset', 'ultrafast',
        '-b:v', '600k', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k',
        '-f', 'flv', RTMP_URL
    ]
    subprocess.Popen(command)

# المهمة التي ترسل المنشور للقناة وتبدأ البث
async def start_broadcast_job(reciter, surah_name, source_url):
    post_text = (
        f"📡 **بدأ البث المباشر الآن (توقيت الجزائر)**\n\n"
        f"📖 **السورة:** {surah_name}\n"
        f"🎙 **القارئ:** {reciter}\n\n"
        f"🤲 اللهم اجعل القرآن الكريم ربيع قلوبنا ونور صدورنا.\n\n"
        f"🎧 **للاستماع:** اضغط على زر 'انضمام' في أعلى القناة."
    )
    # إرسال المنشور للقناة فقط عند بدء البث
    send_msg(CHAT_ID, post_text)
    run_ffmpeg(source_url)

# نظام مراقبة الأوامر
async def bot_polling():
    last_update_id = 0
    print("✅ البث المجدول والفوري يعمل الآن...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=30"
            resp = requests.get(url).json()
            for update in resp.get("result", []):
                last_update_id = update["update_id"]
                msg = update.get("message", {})
                text = msg.get("text", "")
                user_id = str(msg.get("from", {}).get("id", ""))
                chat_type = msg.get("chat", {}).get("type")

                # يجب أن يكون الأمر من المدير فقط
                if user_id == ADMIN_ID:
                    
                    # 1. أمر الجدولة: /schedule [القارئ] [السورة] [الرابط] [HH:MM]
                    if text.startswith("/schedule"):
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
                            # الرد في الخاص فقط
                            send_msg(user_id, f"✅ **تم ضبط الجدول بنجاح:**\n📖 {surah}\n⏰ الساعة {t_str} بتوقيت الجزائر\n📢 سيتم النشر في القناة عند بدء البث.")

                    # 2. أمر البث الفوري للتجربة: /stream [القارئ] [السورة] [الرابط]
                    elif text.startswith("/stream"):
                        parts = text.split(maxsplit=3)
                        if len(parts) == 4:
                            reciter, surah, s_url = parts[1], parts[2], parts[3]
                            send_msg(user_id, f"🚀 جاري بدء البث التجريبي الفوري لـ {surah}...")
                            await start_broadcast_job(reciter, surah, s_url)

        except Exception as e:
            await asyncio.sleep(5)
        await asyncio.sleep(1)

async def main():
    scheduler.start()
    await bot_polling()

if __name__ == "__main__":
    asyncio.run(main())
