#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ربات بازی کلمات - نسخه پایتون (تبدیل‌شده از سورس PHP)
اجرا:  python3 bot.py
نیازمندی:  pip install "python-telegram-bot>=20"
"""
import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, Update,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters,
)

# ============================== تنظیمات ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN", "9042877202:AAFBZD3CYZzZsgmdS-QYIuL0UgLbYRVL9H4")
ADMINS = [int(x) for x in os.getenv("ADMIN_IDS", "5888377320").split(",") if x.strip()]
CHANNEL = os.getenv("CHANNEL", "@PERSIIA_TEAM")  # کانال اجباری
# =====================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
WORDS_FILE = os.path.join(DATA_DIR, "wordlist.json")
ADS_FILE = os.path.join(BASE_DIR, "ads")
os.makedirs(DATA_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("wordgame")
logging.getLogger("httpx").setLevel(logging.WARNING)

CIRCLE = "\u2b55\ufe0f"  # ⭕️
SEP = "➖➖➖➖➖➖➖➖➖"
EMPTY_TEXT = "`هنوز هیچی وارد نکردی!`"
MD = ParseMode.MARKDOWN

# ============================== متن‌ها ==============================
MAIN_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🎲 شروع بازی")],
        [KeyboardButton("👤 اطلاعات من 👤"), KeyboardButton("🏆 برترین کاربران")],
        [KeyboardButton("🏵 جمع آوری سکه"), KeyboardButton("🔸 راهنما")],
    ],
    resize_keyboard=True,
)
ADMIN_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📊 آمار"), KeyboardButton("🗄 پشتیبان گیری از مراحل")],
        [KeyboardButton("📮 فوروارد همگانی"), KeyboardButton("📩 ارسال همگانی")],
        [KeyboardButton("➖ حذف یک مرحله"), KeyboardButton("➕ ساخت مرحله جدید")],
        [KeyboardButton("🔹 حذف کلمه از مرحله"), KeyboardButton("🔸 افزودن کلمه به مرحله")],
        [KeyboardButton("📟 ثبت تبلیغ")],
        [KeyboardButton("▫️ برگشت")],
    ],
    resize_keyboard=True,
)
BACK_KB = ReplyKeyboardMarkup([[KeyboardButton("↩️ برگشت")]], resize_keyboard=True)
YESNO_KB = ReplyKeyboardMarkup(
    [[KeyboardButton("✅ بله")], [KeyboardButton("↩️ برگشت")]], resize_keyboard=True
)

HELP_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("🏵 راهنمای افزایش سکه", callback_data="coinup"),
     InlineKeyboardButton("🎮 راهنمای بازی کردن", callback_data="play")],
    [InlineKeyboardButton("💡 درباره بازی", callback_data="info"),
     InlineKeyboardButton("🥁 راهنمای استفاده از سکه", callback_data="coinuse")],
])

WELCOME = (
    "😎 سلام به ربات بازی کلمات خوش آومدی!\n\n"
    "🙃 این بازی یه جور بازی با کلماته که مرحله های زیادی داره و با جمع آوری سکه "
    "میتونی در هر مرحله ای که هستی کمک بگیری.\n\n"
    "📍 برای شروع بازی از کلید های زیر استفاده کن."
)

ABOUT = (
    "💡 با کلمات به یک استاد واژگان تبدیل شوید!\n"
    "فقط با زدن بر روی حروف، کلمات با معنی بسیاری بسازید و به یک استاد واژگان تبدیل شوید!\n"
    "برای استاد شدن تلاش زیادی لازمه، پس وقتشه که رمز و رموز موجود در کلمات را بیابید "
    "و ذهن خود را چندین برابر ارتقا دهید.\n\n"
    "📌 ویژگی های کلمات :\n"
    "- ساده، آسان و گیم پلی اعتیاد آور!\n"
    "- هر روز یک چالش جدید تجربه کنید!\n"
    "- از اعضای خانواده و دوستان خود برای کمک به یکدیگر بپرسید!\n"
    "- جمع آوری سکه از طریق دعوت دوستان\n"
    "- مشاهده برترین کاربران (لِوِل بالاترین ها)\n"
    "- مشاهده رتبه جهانی شما بین کل کاربران ربات\n\n"
    "💬 کلمات یک بازی طراحی شده برای آموزش مغز و یادگیری کلمات جدید است که در هر زمان "
    "و مکان میتوان بازی کرد. با اشتراک گذاری کلمات همه از این بازی لذت ببریم و به رشد "
    "هم کمک کنیم.\n\n"
    "‼️ توجه : این بازی هیچ ارتباطی به بازی اصلی `کلمات نسخه اندروید` موجود در مارکت های "
    "ایرانی ندارد و فقط الگوبرداری شده است!"
)

HELP_TEXTS = {
    "coinup": (
        "📍 راه های بالا بردن سکه \n\n"
        "🔸 شما پس از عبور کردن از هر مرحله با موفقیت ، 9 سکه دریافت می کنید.\n"
        "🔸 روش مرسوم و پیشنهادی ما روش زیرمجموعه گیری است که شما با زدن روی دکمه "
        "`'🏵 جمع آوری سکه'` بنر مخصوص خود را دریافت می کنید و با انتشار بنر مخصوص تان "
        "بین دوستان و آشنایان در گروه ها و شخصی افراد ، نسبت به جمع آوری زیرمجموعه اقدام "
        "می کنید و با عضو شدن هر زیرمجموعه از طرف شما ، به شما 10 سکه تعلق می گیرد.\n"
        "🔸 روش سوم بالا بردن سکه توسط خریداری سکه توسط درگاه بانکی می باشد که به زودی "
        "این قسمت فعال می گردد ."
    ),
    "play": (
        "📍 راهنمای بازی کردن :\n\n"
        "ابتدا روی دکمه `'🎲 شروع بازی'` بزنید.\n"
        "خب اکنون مرحله ای که در آن حاضر هستید شناسایی و باز می شود.\n"
        "بالای پیام تعداد کلمات مراحل و مرحله فعلی شما ذکر شده است.\n"
        "عبارات حل نشده به صورت ⭕️ نمایش داده می شوند و هر ⭕️ به معنای یک کاراکتر است!\n"
        "از کلمات تعبیه شده به صورت شیشه ای در پایین، شما باید کلمات مجهول را بیابید و "
        "متن شما رو به روی قسمت ( >> نوشته شما ) به صورت زنده قابل مشاهده است.\n"
        "در هر جا شما با استفاده از دکمه '✖️ یک حذف' می توانید یک حرف را از نوشته فعلی تان "
        "حذف و درصورت تمایل به حذف کامل متن شما از کلید `'🗑 حذف کامل نوشته من'` بهره مند شوید.\n"
        "اکنون پس از نوشتن کلمه فرضیه ای شما روی دکمه `'🔄 برسی کلمه نوشته شده'` بزنید و "
        "نتیجه را مشاهده کنید.\n"
        "اگر کلمه فرضیه ای (حدسی) شما درست باشد پس از نمایش پیغام موفقیت ، به صورت خودکار "
        "جایگزین ⭕️ ها در متن می شود.\n"
        "پس از حل کامل کلمات مرحله روی دکمه `'😎 بریم مرحله بعدی'` بزنید تا سیستم برسی کند ، "
        "اگر تمامی کلمات پاسخ داده شده باشند شما به مرحله بعد راه پیدا می کنید در غیر "
        "اینصورت پیغامی مبنی بر کامل نبودن کلمات مشاهده خواهید کرد."
    ),
    "info": ABOUT,
    "coinuse": (
        "📍 آموزش استفاده از سکه ها\n\n"
        "🤔 شما درحین بازی اگر جایی رو گیر کردید و نتونستید از اون عبور کنید می تونید از کلید های :\n"
        "`'💡 یک حرف | 10 سکه'`  (مشاهده یک حرف از حروف کلمه ای که شما در آن گیر کردید)\n"
        "`'💡 یک کلمه کامل | 25 سکه'`  (مشاهده کامل کلمه ای که شما در آن گیر کردید)\n"
        "استفاده کنید !"
    ),
}

MENU_TEXTS = {"🎲 شروع بازی", "👤 اطلاعات من 👤", "🏆 برترین کاربران", "🏵 جمع آوری سکه", "🔸 راهنما"}
FINISHED_MSG = (
    "😳 شما بازی رو تموم کردی و مرحله آخر هم تموم شد.\n"
    "🤓 اما نگران نباش چون قراره مرحله های جدید قرار بگیره ، هروقت مرحله های جدید رو "
    "گذاشتیم من بهت اطلاع میدم تا بتونی بازم بازی کنی!"
)
STATIC_CB = {"coinup", "play", "info", "coinuse", "rename", "clean", "del",
             "oneanswer", "onew", "check", "nextlevel", "sp"}

# ============================== ذخیره‌سازی ==============================
def user_file(uid) -> str:
    return os.path.join(DATA_DIR, str(uid), "data.json")


def load_user(uid):
    try:
        with open(user_file(uid), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def _atomic_write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def save_user(uid, d: dict) -> None:
    _atomic_write(user_file(uid), json.dumps(d, ensure_ascii=False))


def all_user_ids() -> list:
    ids = []
    for name in os.listdir(DATA_DIR):
        if name.isdigit() and os.path.isfile(user_file(name)):
            ids.append(int(name))
    return ids


def load_words() -> list:
    """لیست مراحل؛ هر مرحله لیستی از کلمات. با خروجی قدیمی PHP هم سازگار است."""
    try:
        with open(WORDS_FILE, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return []

    def as_list(x):
        if isinstance(x, dict):
            return [x[k] for k in sorted(x, key=lambda k: int(k) if str(k).isdigit() else 0)]
        return list(x) if isinstance(x, list) else []

    return [[str(w) for w in as_list(level)] for level in as_list(raw)]


def save_words(wl: list) -> None:
    _atomic_write(WORDS_FILE, json.dumps(wl, ensure_ascii=False))


def level_words(wl: list, level: int):
    if 1 <= level <= len(wl) and wl[level - 1]:
        return wl[level - 1]
    return None


def load_ads() -> str:
    try:
        with open(ADS_FILE, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def get_or_create(tg_user):
    """(user_dict, created)"""
    d = load_user(tg_user.id)
    if d:
        return d, False
    d = {"coin": 50, "level": 1, "esm": clean_name(tg_user.first_name or "کاربر"), "step": "none"}
    save_user(tg_user.id, d)
    return d, True


def clean_name(s: str) -> str:
    s = re.sub(r"[\[\]*`_]", " ", s or "").strip()
    return s[:30] or "کاربر"

# ============================== تاریخ شمسی ==============================
def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy, gy = 979, gy - 1600
    else:
        jy, gy = 0, gy - 621
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
            - 80 + gd + g_d_m[gm - 1])
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


WEEKDAYS = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]


def today_fa():
    now = datetime.now(timezone(timedelta(hours=3, minutes=30)))
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    return WEEKDAYS[now.weekday()], f"{jy}/{jm:02d}/{jd:02d}"

# ============================== ابزارهای تلگرام ==============================
async def send(bot, chat_id, text, markup=None, md=True):
    try:
        return await bot.send_message(chat_id, text, parse_mode=MD if md else None, reply_markup=markup)
    except BadRequest as e:
        if md:  # احتمالاً خطای مارک‌داون؛ بدون فرمت بفرست
            return await bot.send_message(chat_id, text, reply_markup=markup)
        raise e


async def edit(bot, chat_id, message_id, text, markup=None, md=True):
    try:
        return await bot.edit_message_text(
            text, chat_id=chat_id, message_id=message_id,
            parse_mode=MD if md else None, reply_markup=markup)
    except BadRequest as e:
        msg = str(e).lower()
        if "not modified" in msg:
            return None
        if md and "parse" in msg:
            return await edit(bot, chat_id, message_id, text, markup, md=False)
        raise e


async def safe_answer(q, text=None, alert=False):
    try:
        await q.answer(text, show_alert=alert)
    except TelegramError:
        pass


_member_cache = {}


async def is_member(bot, uid) -> bool:
    if time.time() - _member_cache.get(uid, 0) < 120:
        return True
    try:
        m = await bot.get_chat_member(CHANNEL, uid)
        if m.status in ("left", "kicked"):
            return False
    except TelegramError as e:
        # اگر ربات در کانال ادمین نباشد خطا می‌دهد؛ مثل نسخه PHP اجازه عبور می‌دهیم
        log.warning("getChatMember failed (ربات را در کانال ادمین کنید): %s", e)
    _member_cache[uid] = time.time()
    return True


def join_text() -> str:
    return ("🍃  برای استفاده از این ربات لازم است ابتدا وارد کانال زیر شوید \n\n"
            f"{CHANNEL}   {CHANNEL}  📣\n\n☑️ بعد از عضویت روی /Start کلیک کنید")


def join_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("📣 عضویت در کانال", url=f"https://t.me/{CHANNEL.lstrip('@')}")]])

# ============================== صفحه بازی ==============================
def sync_lines(user: dict, words: list) -> list:
    """خطوط ⭕️ هر کلمه؛ اگر ادمین کلمات را تغییر داده باشد پیشرفت معتبر حفظ می‌شود."""
    old = (user.get("datalevel") or "").split("\n")
    lines = []
    for i, w in enumerate(words):
        if i < len(old) and old[i] == f"📍 {w}":
            lines.append(old[i])
        else:
            lines.append("📍 " + CIRCLE * len(w))
    user["datalevel"] = "\n".join(lines)
    return lines


def build_screen(user: dict, words: list):
    level = user["level"]
    sync_lines(user, words)
    letters = sorted({ch for w in words for ch in w})
    buttons = [InlineKeyboardButton("␣" if ch == " " else ch, callback_data="sp" if ch == " " else ch)
               for ch in letters]
    rows = [buttons[i:i + 4] for i in range(0, len(buttons), 4)]
    rows += [
        [InlineKeyboardButton("🗑 حذف کامل نوشته من", callback_data="clean"),
         InlineKeyboardButton("✖️ یک حذف", callback_data="del")],
        [InlineKeyboardButton("💡 یک کلمه کامل | 25 سکه", callback_data="oneanswer"),
         InlineKeyboardButton("💡 یک حرف | 10 سکه", callback_data="onew")],
        [InlineKeyboardButton("🔄 برسی کلمه نوشته شده", callback_data="check")],
        [InlineKeyboardButton("😎 بریم مرحله بعدی", callback_data="nextlevel")],
    ]
    ytext = user.get("text") or EMPTY_TEXT
    text = (f"🔮 مرحله : *{level}* | 📚 تعداد کلمات : *{len(words)}*\n{SEP}\n"
            f">> نوشته شما : {ytext}\n\nعبارات :\n{user['datalevel']}\n{SEP}\n{load_ads()}")
    return text, InlineKeyboardMarkup(rows)

# ============================== پیام‌ها ==============================
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user or msg.from_user.is_bot:
        return
    bot = context.bot
    u = msg.from_user
    uid, chat_id = u.id, msg.chat_id
    text = msg.text
    user, created = get_or_create(u)
    is_admin = uid in ADMINS

    async def welcome_bonus():
        if created:
            await send(bot, chat_id, "🍿 50 سکه به عنوان ورود شما به ربات برای حساب شما اعمال شد.")

    # ---- /start و برگشت ----
    if text and (re.fullmatch(r"/start(@\w+)?", text, re.I) or text == "▫️ برگشت"):
        user["step"] = "none"
        save_user(uid, user)
        await send(bot, chat_id, WELCOME, MAIN_KB, md=False)
        await welcome_bonus()
        return

    # ---- /start <id> (زیرمجموعه‌گیری) ----
    m = re.fullmatch(r"/start(?:@\w+)?\s+(\d+)", text or "", re.I)
    if m:
        ref = int(m.group(1))
        user["step"] = "none"
        save_user(uid, user)
        await send(bot, chat_id, WELCOME, MAIN_KB, md=False)
        if created and ref != uid:
            ref_data = load_user(ref)
            if ref_data:
                ref_data["coin"] = ref_data.get("coin", 0) + 10
                save_user(ref, ref_data)
                try:
                    await send(bot, ref, f"😬 کاربر [{uid}](tg://user?id={uid}) با لینک تو وارد ربات شد و بهت 10 سکه دادم 🙏🏻")
                except TelegramError:
                    pass
        await welcome_bonus()
        return

    # ---- پنل ادمین ----
    if is_admin and await admin_message(update, context, user):
        return

    # ---- عضویت اجباری ----
    if not is_admin and not await is_member(bot, uid):
        await send(bot, chat_id, join_text(), join_markup(), md=False)
        return

    step = user.get("step", "none")

    if text == "🔸 راهنما":
        await send(bot, chat_id, ABOUT, HELP_KB)
    elif text == "👤 اطلاعات من 👤":
        await show_profile(bot, chat_id, uid, user)
    elif text == "🏆 برترین کاربران":
        await show_top(bot, chat_id, uid)
    elif text == "🏵 جمع آوری سکه":
        me = await bot.get_me()
        await send(bot, chat_id,
                   "🎮 ربات بازی کلمات (بازی با کلمات)\n\n"
                   "😅 رمز و رموز موجود در کلمات را بیابید و ذهن خود را چندین برابر ارتقا دهید.\n\n"
                   "🙃 قابلیت مشاهده سطح جهانی شما بین کل کاربران\n\n"
                   f"👉🏻 https://t.me/{me.username}?start={uid}", md=False)
        await send(bot, chat_id,
                   "📍 پیام بالا حاوی لینک شخصی شماست، آن را برای دوستان و گروه های خود ارسال کنید "
                   "و با عضویت هر یک زیرمجموعه ، ده سکه دریافت کنید.\n➖➖\n"
                   "🌱 برای اطلاع از سکه های فعلی تان از دکمه `'👤 اطلاعات من 👤'` استفاده کنید.\n\n"
                   "🌚 به یاد داشته باشید ، به محض عضو شدن شخصی از طریق لینک شما ، به شما اطلاع داده "
                   "خواهد شد و سکه جایزه شما آنی بر روی حساب شما اعمال خواهد شد.")
    elif text == "🎲 شروع بازی":
        await start_game(bot, chat_id, uid, user)
    elif step == "rename" and text:
        user["esm"] = clean_name(text)
        user["step"] = "none"
        save_user(uid, user)
        await send(bot, chat_id, f"✅ نام شما به [{user['esm']}] در بازی تغییر یافت.", md=False)
    else:
        await welcome_bonus()


async def show_profile(bot, chat_id, uid, user):
    wl = load_words()
    level = user.get("level", 1)
    level_txt = f"{level} (مرحله آخر)" if wl and level > len(wl) else str(level)
    levels = [(i, (load_user(i) or {}).get("level", 1)) for i in all_user_ids()]
    rank = 1 + sum(1 for _, lv in levels if lv > level)
    caption = (f"📍 اطلاعات شما :\n\n👤 اسم شما در بازی : {user.get('esm', '')}\n\n"
               f"🏵 سکه های شما : *{user.get('coin', 0)}*\n\n🔹 مرحله : *{level_txt}*\n\n"
               f"🌐 رتبه جهانی شما : *{rank}*")
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("✏️ تغییر نام من در بازی", callback_data="rename")]])
    photo = None
    try:
        photos = await bot.get_user_profile_photos(uid, limit=1)
        if photos.total_count:
            photo = photos.photos[0][0].file_id
    except TelegramError:
        pass
    if photo:
        try:
            await bot.send_photo(chat_id, photo, caption=caption, parse_mode=MD, reply_markup=markup)
            return
        except TelegramError:
            pass
    await send(bot, chat_id, caption, markup)


async def show_top(bot, chat_id, uid):
    rows = sorted(((i, load_user(i) or {}) for i in all_user_ids()),
                  key=lambda r: (-r[1].get("level", 1), r[0]))[:10]
    out = ""
    for i, d in rows:
        name = re.sub(r"[\[\]*`_]", " ", d.get("esm", "")) or "کاربر"
        lv = d.get("level", 1)
        label = f"You : {lv}" if i == uid else f"{lv}"
        out += f"👤 [{name}](tg://user?id={i})\n🔮 *{label}*\n\n"
    day, date = today_fa()
    await send(bot, chat_id,
               f"🏆 لیست برترین کاربران ربات از نظر مرحله ،\n آپدیت شده در روز *({day})* تاریخ *({date})* :\n\n{out}")


async def start_game(bot, chat_id, uid, user):
    wl = load_words()
    words = level_words(wl, user.get("level", 1))
    if not words:
        await send(bot, chat_id, FINISHED_MSG)
        user.pop("text", None)
        user.pop("datalevel", None)
        save_user(uid, user)
        return
    loading = await send(bot, chat_id, "🔄 درحال پردازش اطلاعات مراحل ...\n💡 لطفاَ منتظر باشید !")
    user.pop("text", None)
    text, markup = build_screen(user, words)
    save_user(uid, user)
    await edit(bot, chat_id, loading.message_id, text, markup)

# ============================== دکمه‌های شیشه‌ای ==============================
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.message:
        return
    bot = context.bot
    uid, chat_id, mid = q.from_user.id, q.message.chat_id, q.message.message_id
    cb = q.data or ""
    user, _ = get_or_create(q.from_user)

    if uid not in ADMINS and not await is_member(bot, uid):
        await safe_answer(q, f"🍃 ابتدا وارد کانال {CHANNEL} شوید و سپس /start بزنید.", True)
        return

    # ---- راهنما ----
    if cb in HELP_TEXTS:
        await safe_answer(q)
        await edit(bot, chat_id, mid, HELP_TEXTS[cb], HELP_KB)
        return
    if cb == "rename":
        await safe_answer(q)
        user["step"] = "rename"
        save_user(uid, user)
        await send(bot, chat_id, "✏️ نام جدید خود را ارسال کنید :\nدرصورت تمایل به انصراف /start", md=False)
        return

    # ---- بازی ----
    wl = load_words()
    level = user.get("level", 1)
    words = level_words(wl, level)
    if not words:
        await safe_answer(q, FINISHED_MSG, True)
        return

    async def rerender():
        text, markup = build_screen(user, words)
        save_user(uid, user)
        await edit(bot, chat_id, mid, text, markup)

    if cb in ("del", "clean") or (cb not in STATIC_CB and len(cb) <= 4):
        await safe_answer(q)
        cur = user.get("text") or ""
        if cb == "del":
            cur = cur[:-1]
        elif cb == "clean":
            cur = ""
        else:
            if len(cur) < 60:
                cur += " " if cb == "sp" else cb
        if cur:
            user["text"] = cur
        else:
            user.pop("text", None)
        await rerender()
        return
    if cb == "sp":
        return

    if cb == "check":
        yt = user.get("text") or ""
        if not yt:
            await safe_answer(q, "😐 هیچی وارد نشده!", True)
            return
        if yt not in words:
            await safe_answer(q, "❌ متاسفم ، اشتباه بود!", True)
            return
        lines = sync_lines(user, words)
        idx = next((i for i, w in enumerate(words) if w == yt and CIRCLE in lines[i]), None)
        if idx is None:
            await safe_answer(q, "📍اینو از قبل وارد کردی .", True)
            return
        lines[idx] = f"📍 {yt}"
        user["datalevel"] = "\n".join(lines)
        user.pop("text", None)
        await safe_answer(q, "🎉 آفرین ، درست وارد کردی.", True)
        await rerender()
        return

    if cb in ("oneanswer", "onew"):
        cost = 25 if cb == "oneanswer" else 10
        if user.get("coin", 0) < cost:
            await safe_answer(q, f"❗️ سکه های شما کافی نیست !\n🏵 شما باید {cost - user.get('coin', 0)} سکه دیگر داشته باشید.", True)
            return
        lines = sync_lines(user, words)
        idx = next((i for i, ln in enumerate(lines) if CIRCLE in ln), None)
        if idx is None:
            await safe_answer(q, "❗️ خطا ، ممکن است به همه کلمات پاسخ داده باشید.", True)
            return
        if cb == "oneanswer":
            msg = f"📍 کلمه شماره {idx + 1} می شود : {words[idx]}"
        else:
            msg = f"📍 کلمه شماره {idx + 1} حرف اولش '{words[idx][0]}' است!"
        user["coin"] -= cost
        save_user(uid, user)
        await safe_answer(q, msg, True)
        return

    if cb == "nextlevel":
        lines = sync_lines(user, words)
        if any(CIRCLE in ln for ln in lines):
            await safe_answer(q, "😫 هنوز همه رو جواب ندادی که ...", True)
            return
        has_next = level_words(wl, level + 1) is not None
        user.pop("text", None)
        user.pop("datalevel", None)
        user["level"] = level + 1
        if has_next:
            user["coin"] = user.get("coin", 0) + 9
        save_user(uid, user)
        try:
            await bot.delete_message(chat_id, mid)
        except TelegramError:
            pass
        if has_next:
            await safe_answer(q, f"😃 با موفقیت مرحله {level} رو پشت سر گذاشتی و 9 سکه گرفتی!\n\n"
                                 "👈🏻 تا 3 ثانیه دیگر به صورت خودکار مرحله بعدی آغاز می شود ...", True)

            async def later():
                await asyncio.sleep(3)
                fresh = load_user(uid) or user
                nxt = level_words(load_words(), fresh["level"])
                if nxt:
                    t, mk = build_screen(fresh, nxt)
                    save_user(uid, fresh)
                    await send(bot, chat_id, t, mk)
            context.application.create_task(later())
        else:
            await safe_answer(q, FINISHED_MSG, True)

# ============================== پنل ادمین ==============================
async def admin_message(update, context, user) -> bool:
    """True یعنی پیام توسط پنل ادمین مصرف شد."""
    msg = update.message
    bot = context.bot
    uid, chat_id = msg.from_user.id, msg.chat_id
    text = msg.text
    step = user.get("step", "none")

    def set_step(s):
        user["step"] = s
        save_user(uid, user)

    async def back_to_panel(t="🖲 یکی از گزینه های زیر را انتخاب کنید :"):
        set_step("none")
        await send(bot, chat_id, t, ADMIN_KB, md=False)

    if text and (text.lower() == "/panel" or text == "↩️ برگشت"):
        await back_to_panel()
        return True

    # دریافت کلمات یکی‌یکی
    if step.startswith("words|") and text:
        lv = int(step.split("|")[1])
        wl = load_words()
        while len(wl) < lv:
            wl.append([])
        word = text.strip()
        if word and word not in wl[lv - 1]:
            wl[lv - 1].append(word)
            save_words(wl)
        return True

    if text == "📊 آمار":
        await send(bot, chat_id, f"📯 آمار کاربران ربات : *{len(all_user_ids())}*\n"
                                 f"🔮 آمار کل مرحله های ربات : *{len(load_words())}*")
        return True

    if text == "🗄 پشتیبان گیری از مراحل":
        if not os.path.exists(WORDS_FILE):
            save_words([])
        with open(WORDS_FILE, "rb") as f:
            await bot.send_document(chat_id, f, filename="wordlist.json",
                                    caption="🗃 آخرین نسخه پشتیبان از مراحل ثبت شده توسط شما")
        return True

    if text == "➕ ساخت مرحله جدید":
        set_step("createlevel")
        await send(bot, chat_id, f"❄️ اکنون ربات دارای {len(load_words())} مرحله است !\n\n"
                                 "🤔 آیا تمایل به ساخت مرحله بعدی را دارید؟", YESNO_KB, md=False)
        return True
    if step == "createlevel" and text == "✅ بله":
        wl = load_words()
        wl.append([])
        save_words(wl)
        await back_to_panel("✅ هم اکنون از قسمت افزودن کلمه به مرحله ، به این مرحله کلمه اضافه کنید.")
        return True

    if text == "➖ حذف یک مرحله":
        set_step("deletelevel")
        await send(bot, chat_id, f"❄️ اکنون ربات دارای {len(load_words())} مرحله است !\n\n"
                                 "🤔 شماره مرحله ای که قصد حذف آن را دارید به لاتین ارسال کنید.", BACK_KB, md=False)
        return True
    if step == "deletelevel" and text and text.strip().isdigit():
        n, wl = int(text), load_words()
        if not 1 <= n <= len(wl):
            await send(bot, chat_id, "❌ چنین مرحله ای وجود ندارد.", md=False)
            return True
        wl.pop(n - 1)
        save_words(wl)
        await back_to_panel(f"✅ مرحله {n} به همراه کلماتش با موفقیت حذف شد.")
        return True

    if text == "🔸 افزودن کلمه به مرحله":
        set_step("addtolevel")
        await send(bot, chat_id, "👈🏻 قصد اضافه کردن کلمه به کدام مرحله دارید؟ به لاتین ارسال کنید. ", BACK_KB, md=False)
        return True
    if step == "addtolevel" and text and text.strip().isdigit():
        n = int(text)
        if not 1 <= n <= len(load_words()):
            await send(bot, chat_id, "❌ چنین مرحله ای وجود ندارد. اول مرحله بسازید.", md=False)
            return True
        set_step(f"words|{n}")
        await send(bot, chat_id, "✅ اکنون کلمات را تک به تک ارسال کنید و در پایان روی برگشت بزنید !\n"
                                 "📍 توجه ، درحین ارسال کلمات ربات پیامی ارسال نمی کند و منتظر است تا "
                                 "دکمه برگشت را بزنید تا کلمات را ثبت کند.", BACK_KB, md=False)
        return True

    if text == "🔹 حذف کلمه از مرحله":
        set_step("delfromlevel")
        await send(bot, chat_id, "👈🏻 قصد حذف کردن از کدام مرحله دارید؟ به لاتین ارسال کنید. ", BACK_KB, md=False)
        return True
    if step == "delfromlevel" and text and text.strip().isdigit():
        n = int(text)
        if not 1 <= n <= len(load_words()):
            await send(bot, chat_id, "❌ چنین مرحله ای وجود ندارد.", md=False)
            return True
        set_step(f"delwords|{n}")
        await send(bot, chat_id, f"✅ کلمه مورد نظر را برای حذف شدن از مرحله {n} ارسال کنید.", BACK_KB, md=False)
        return True
    if step.startswith("delwords|") and text:
        n = int(step.split("|")[1])
        wl = load_words()
        if n <= len(wl) and text.strip() in wl[n - 1]:
            wl[n - 1].remove(text.strip())
            save_words(wl)
            await back_to_panel(f"✅ کلمه {text} با موفقیت از مرحله {n} حذف شد.")
        else:
            await send(bot, chat_id, "❌ این کلمه در آن مرحله پیدا نشد. دوباره بفرستید یا برگشت بزنید.", md=False)
        return True

    if text == "📟 ثبت تبلیغ":
        set_step("setads")
        await send(bot, chat_id, "🖲 متن تبلیغ مورد نظر را برای قرار گرفتن زیر بازی ها ، در قالب متن ارسال کنید.", BACK_KB, md=False)
        return True
    if step == "setads" and text:
        _atomic_write(ADS_FILE, text)
        await back_to_panel("✅ ثبت شد!")
        return True

    if text == "📩 ارسال همگانی":
        set_step("s2all")
        await send(bot, chat_id, "🖲 پیام مورد نظر را در قالب متن ارسال کنید :", BACK_KB, md=False)
        return True
    if text == "📮 فوروارد همگانی":
        set_step("f2all")
        await send(bot, chat_id, "🖲 پیام مورد نظر را در هر قالبی فوروارد کنید :", BACK_KB, md=False)
        return True
    if step in ("s2all", "f2all"):
        if step == "s2all" and not text:
            return True
        mode, src_id = step, msg.message_id
        await back_to_panel("⏳ ارسال همگانی شروع شد؛ پس از پایان گزارش می‌دهم.")

        async def broadcast():
            ok = fail = 0
            for target in all_user_ids():
                try:
                    if mode == "s2all":
                        await bot.send_message(target, text)
                    else:
                        await bot.forward_message(target, chat_id, src_id)
                    ok += 1
                except TelegramError:
                    fail += 1
                await asyncio.sleep(0.05)
            await send(bot, chat_id, f"✅ ارسال تمام شد.\nموفق: {ok} | ناموفق: {fail}", md=False)
        context.application.create_task(broadcast())
        return True

    return False


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    log.error("خطا:", exc_info=context.error)


def main():
    if not os.path.exists(WORDS_FILE):
        save_words([])
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE, on_message))
    app.add_error_handler(on_error)
    log.info("ربات روشن شد ✅")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
