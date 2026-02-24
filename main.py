import os
import asyncio
import subprocess
import pytz
from pyrogram import Client, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# الإعدادات
BOT_TOKEN = os.getenv("BOT_TOKEN")
RTMP_URL = os.getenv("RTMP_URL")
CHAT_ID = os.getenv("CHAT_ID")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# توقيت الجزائر
ALGERIA_TZ = pytz.timezone("Africa/Algiers")

app = Client("stream_bot", bot_token=BOT_TOKEN, api_id=2040, api_hash="b18441a1ff765110c22fa0589762a6d7")
scheduler = AsyncIOScheduler(timezone=ALGERIA_TZ)

IMAGE_PATH = "icons/image.jpg"

# دالة تشغيل البث عبر FFmpeg
def run_ffmpeg(source_url):
    command = [
        'ffmpeg', '-re', '-loop', '1', '-i', IMAGE_PATH,
        '-i', source_url, '-c:v', 'libx264', '-preset', 'veryfast',
        '-b:v', '1000k', '-maxrate', '1000k', '-bufsize', '2000k',
        '-pix_fmt', 'yuv420p', '-g', '50', '-c:a', 'aac', '-b:a', '128k',
        '-f', 'flv', RTMP_URL
    ]
    return subprocess.Popen(command)

# المهمة التي ستنفذ وقت البث
async def start_broadcast_job(reciter, surah_name, source_url):
    # 1. إرسال المنشور للقناة
    post_text = (
        f"📡 **بدأ البث المباشر الآن**\n\n"
        f"📖 **السورة:** {surah_name}\n"
        f"🎙 **القارئ:** {reciter}\n\n"
        f"🎧 اضغط على 'انضمام للبث' في أعلى القناة للاستماع."
    )
    await app.send_message(CHAT_ID, post_text)
    
    # 2. بدء عملية البث
    print(f"🚀 بدأ البث: {surah_name}")
    process = run_ffmpeg(source_url)
    # ملاحظة: سيبقى البث شغالاً حتى ينتهي الملف الصوتي أو يتم إيقاف العملية

# أمر الجدولة: /schedule [القارئ] [اسم_السورة] [رابط_mp3] [الوقت HH:MM]
@app.on_message(filters.command("schedule") & filters.user(ADMIN_ID))
async def schedule_handler(_, msg):
    try:
        # مثال: /schedule العفاسي الفاتحة https://server.com/1.mp3 08:00
        args = msg.text.split(maxsplit=4)
        reciter, surah_name, url, time_str = args[1], args[2], args[3], args[4]
        h, m = time_str.split(":")
        
        scheduler.add_job(
            start_broadcast_job, "cron", 
            hour=int(h), minute=int(m), 
            args=[reciter, surah_name, url]
        )
        await msg.reply(f"✅ تم جدولة بث {surah_name} للقارئ {reciter} يومياً الساعة {time_str}")
    except:
        await msg.reply("❌ خطأ! الصيغة: `/schedule [القارئ] [السورة] [الرابط] [الوقت]`")

async def main():
    await app.start()
    scheduler.start()
    print("✅ البث المجدول جاهز لتبخير البيانات إلى RTMP!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
