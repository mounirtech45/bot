import asyncio
import random

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import InputStream, InputAudioStream

API_ID = int("API_ID")
API_HASH = "API_HASH"
SESSION = "SESSION_STRING"

CHAT_ID = -100xxxxxxxx
ADMIN_ID = 123456789

app = Client(
    ":memory:",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION
)

call = PyTgCalls(app)

radio_mode = False
queue = []

reciter = "afs"

surahs = ["الفاتحة","البقرة","آل عمران","النساء","المائدة","الأنعام","الأعراف","الأنفال","التوبة","يونس",
"هود","يوسف","الرعد","إبراهيم","الحجر","النحل","الإسراء","الكهف","مريم","طه",
"الأنبياء","الحج","المؤمنون","النور","الفرقان","الشعراء","النمل","القصص","العنكبوت","الروم",
"لقمان","السجدة","الأحزاب","سبأ","فاطر","يس","الصافات","ص","الزمر","غافر",
"فصلت","الشورى","الزخرف","الدخان","الجاثية","الأحقاف","محمد","الفتح","الحجرات","ق",
"الذاريات","الطور","النجم","القمر","الرحمن","الواقعة","الحديد","المجادلة","الحشر","الممتحنة",
"الصف","الجمعة","المنافقون","التغابن","الطلاق","التحريم","الملك","القلم","الحاقة","المعارج",
"نوح","الجن","المزمل","المدثر","القيامة","الإنسان","المرسلات","النبأ","النازعات","عبس",
"التكوير","الإنفطار","المطففين","الإنشقاق","البروج","الطارق","الأعلى","الغاشية","الفجر","البلد",
"الشمس","الليل","الضحى","الشرح","التين","العلق","القدر","البينة","الزلزلة","العاديات",
"القارعة","التكاثر","العصر","الهمزة","الفيل","قريش","الماعون","الكوثر","الكافرون","النصر",
"المسد","الإخلاص","الفلق","الناس"]

def url(s):

    return f"https://server8.mp3quran.net/{reciter}/{s:03}.mp3"

async def play(s):

    await call.join_group_call(

        CHAT_ID,

        InputStream(

            InputAudioStream(

                url(s)

            )

        )

    )

# لوحة التحكم

def panel():

    return InlineKeyboardMarkup([

        [

            InlineKeyboardButton("▶️ تشغيل",callback_data="play"),

            InlineKeyboardButton("⏸ إيقاف مؤقت",callback_data="pause")

        ],

        [

            InlineKeyboardButton("⏹ إيقاف",callback_data="stop"),

            InlineKeyboardButton("⏭ التالي",callback_data="next")

        ],

        [

            InlineKeyboardButton("📻 راديو",callback_data="radio"),

            InlineKeyboardButton("🎧 قارئ",callback_data="reciter")

        ]

    ])

@app.on_message(filters.command("radio") & filters.user(ADMIN_ID))
async def radio(_,msg):

    await msg.reply(

        "📻 لوحة التحكم",

        reply_markup=panel()

    )

@app.on_callback_query()

async def cb(_,q):

    global radio_mode

    if q.data=="play":

        s=random.randint(1,114)

        await play(s)

        await q.message.reply(f"▶️ تشغيل {surahs[s-1]}")

    elif q.data=="pause":

        await call.pause_stream(CHAT_ID)

    elif q.data=="stop":

        await call.leave_group_call(CHAT_ID)

    elif q.data=="next":

        s=random.randint(1,114)

        await play(s)

    elif q.data=="radio":

        radio_mode=not radio_mode

        await q.message.reply(

            "📻 تم تشغيل الراديو"

        )

# راديو تلقائي

async def auto():

    global radio_mode

    while True:

        if radio_mode:

            s=random.randint(1,114)

            await play(s)

            await asyncio.sleep(600)

        await asyncio.sleep(5)

async def main():

    await app.start()

    await call.start()

    asyncio.create_task(auto())

    print("RADIO READY")

    await asyncio.Event().wait()

asyncio.run(main())