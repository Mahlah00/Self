# ============================================================
# LIFE RP V6 — UNIFIED ONE-BOT ARCHITECTURE
# One bot / one world / one character / one main menu.
# /start = canonical entry point; /life = same entry point.
# All management is button/panel driven.
# King = absolute game-owner authority.
# ============================================================

"""
Life RP Combined — شبیه‌ساز زندگی و شهر تلگرامی
=====================================

این فایل نسخه‌ی توسعه‌یافته‌ی هسته‌ی فعلی بازی است. ساختار اصلی اقتصاد، شغل،
مهارت، بانک، دارایی، شرکت، بازار، بورس، خانواده، جرم، دادگاه و شهر حفظ شده؛
تمرکز این نسخه روی تجربه‌ی کاربری بهتر است. مسیر اصلی بازیکن منوی دکمه‌ای است
و دستورهای قدیمی برای سازگاری همچنان فعال می‌مانند.

تنظیمات محیطی:
    BOT_TOKEN       توکن ربات تلگرام
    ADMIN_IDS       شناسه‌های مدیر، جداشده با کاما
    GROQ_API_KEY    اختیاری، برای مشاور هوش مصنوعی
    GROQ_MODEL      اختیاری، نام مدل مشاور
    LIFEBOT_DB      اختیاری، مسیر دیتابیس SQLite
\نکته امنیتی: توکن ربات را داخل سورس ذخیره نکن.

راهنمای معماری:
    • لایه‌ی دیتابیس و وضعیت بازیکن
    • سیستم‌های بازی و اقتصاد
    • سیستم‌های اجتماعی و شهری
    • رابط دکمه‌ای و فرم‌های مرحله‌ای
    • پنل‌های مدیریت و مقام‌ها

هدف این است که هسته‌ی بازی عوض نشود، اما بازیکن به‌جای حفظ‌کردن commandها
از مسیرهای فارسی، دکمه‌ها، انتخاب‌ها و پیامدها استفاده کند.
"""

import os

# ---------- V6 WORLD CONTRACT ----------
LIFE_RP_CANONICAL_ENTRY = "start"
LIFE_RP_ENTRY_ALIASES = {"life": "start"}
LIFE_RP_ONE_WORLD = True
LIFE_RP_PANEL_ONLY_MANAGEMENT = True
LIFE_RP_KING_ABSOLUTE_AUTHORITY = True

V6_SYSTEMS = {
    "personal": ("زندگی شخصی", "نیازها، خانواده، دارایی و روابط"),
    "career": ("شغل و حرفه", "مهارت، استخدام، عملکرد و ارتقا"),
    "economy": ("اقتصاد", "درآمد، هزینه، مالیات، بانک و اعتبار"),
    "property": ("املاک", "خرید، اجاره، نگهداری، درآمد و فروش"),
    "vehicles": ("حمل‌ونقل", "خرید، استفاده، سوخت، تعمیر و فروش"),
    "companies": ("شرکت‌ها", "مالکیت، تولید، استخدام و سود"),
    "market": ("بازار", "خرید و فروش واقعی بین بازیکنان"),
    "stocks": ("بورس", "سهام، سفارش، قیمت و سود/زیان"),
    "city": ("شهر", "خدمات عمومی، بودجه، پروژه و اشتغال"),
    "government": ("دولت", "وزارتخانه، سیاست و بودجه"),
    "law": ("حقوق", "گزارش، تحقیق، مدرک، دادگاه و حکم"),
    "security": ("امنیت", "پلیس، ارتش، تحقیقات و عملیات"),
    "health": ("سلامت", "بیماری، درمان، بیمارستان و هزینه"),
    "education": ("آموزش", "یادگیری، مهارت و پیشرفت"),
    "politics": ("سیاست", "انتخابات، مقام، محبوبیت و مسئولیت"),
    "social": ("جامعه", "روابط، اعتبار، رویداد و تعامل"),
    "news": ("رسانه", "اخبار رسمی و رویدادهای جهان"),
    "support": ("پشتیبانی", "تیکت، پیوست و رسیدگی"),
}

import re
import sqlite3
import random
import time
import logging
from datetime import datetime, date, timedelta
from contextlib import contextmanager

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ApplicationHandlerStop,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("lifebot")

DB_PATH = os.environ.get("LIFEBOT_DB", "lifebot.db")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "6625504512:AAEmWjFSZ-qUbvIpiA7zIxNpX-HLxC2WFoo").strip()

ADMIN_IDS_RAW = os.environ.get("ADMIN_IDS", "5888377320")
ADMIN_IDS = {int(x) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()} | {8556474195}

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


START_CASH = 50_000
START_BANK = 0
ENERGY_MAX = 100
HUNGER_MAX = 100
SLEEP_MAX = 100
HAPPINESS_MAX = 100
STRESS_MAX = 100
WORK_COOLDOWN_MIN = 30          # فاصله بین دو شیفت کاری (دقیقه، شبیه‌سازی‌شده با timestamp)
TRAIN_COOLDOWN_MIN = 20
SLEEP_COOLDOWN_MIN = 60
LOAN_INTEREST = 0.08            # ۸ درصد سود وام
LOAN_MAX_MULTIPLIER = 3         # سقف وام بر اساس امتیاز اعتبار

# ----------------------------------------------------------------------------
# داده‌های ثابت بازی (Static Game Data)
# ----------------------------------------------------------------------------

SKILLS = {
    "programming": "برنامه‌نویسی",
    "medicine": "پزشکی",
    "management": "مدیریت",
    "business": "تجارت",
    "driving": "رانندگی",
    "cooking": "آشپزی",
    "farming": "کشاورزی",
    "art": "هنر",
    "investing": "سرمایه‌گذاری",
}

# هر شغل: نیازمندی سطح مهارت، حقوق پایه هر شیفت، هزینه انرژی، XP
JOBS = {
    "worker":    {"name": "کارگر",        "skill": None,          "min_level": 0, "pay": 1200,  "energy": 20, "xp": 5,  "stress": 8},
    "seller":    {"name": "فروشنده",       "skill": "business",   "min_level": 0, "pay": 1800,  "energy": 15, "xp": 8,  "stress": 6},
    "driver":    {"name": "راننده",        "skill": "driving",    "min_level": 1, "pay": 2200,  "energy": 25, "xp": 10, "stress": 10},
    "cook":      {"name": "آشپز",          "skill": "cooking",    "min_level": 1, "pay": 2500,  "energy": 20, "xp": 10, "stress": 9},
    "teacher":   {"name": "معلم",          "skill": "management", "min_level": 2, "pay": 3200,  "energy": 18, "xp": 14, "stress": 7},
    "nurse":     {"name": "پرستار",        "skill": "medicine",   "min_level": 2, "pay": 3600,  "energy": 25, "xp": 15, "stress": 15},
    "engineer":  {"name": "مهندس",         "skill": "programming","min_level": 3, "pay": 5200,  "energy": 22, "xp": 20, "stress": 12},
    "developer": {"name": "برنامه‌نویس",    "skill": "programming","min_level": 4, "pay": 7000,  "energy": 20, "xp": 25, "stress": 14},
    "doctor":    {"name": "پزشک",          "skill": "medicine",   "min_level": 5, "pay": 9500,  "energy": 30, "xp": 30, "stress": 20},
    "manager":   {"name": "مدیر",          "skill": "management", "min_level": 5, "pay": 11000, "energy": 25, "xp": 30, "stress": 22},
    "investor":  {"name": "سرمایه‌گذار",   "skill": "investing",  "min_level": 6, "pay": 15000, "energy": 15, "xp": 35, "stress": 18},
}

# حداقل مدرک تحصیلی لازم برای بعضی مشاغل (سطح تحصیلات: تعریفش پایین‌تر در EDU_LEVELS اومده)
JOB_EDU_MIN = {
    "teacher": 1, "nurse": 1, "engineer": 2, "developer": 2,
    "doctor": 3, "manager": 2, "investor": 2,
}

# سطح مهارت لازم برای هر شغل به معنیِ سطح مهارت مرتبط (نه سطح کلی کاربر)
PROPERTIES = {
    "land_small":   {"name": "زمین کوچک",        "price": 80_000,    "income": 0,    "type": "زمین"},
    "apartment":    {"name": "آپارتمان",          "price": 250_000,   "income": 400,  "type": "مسکونی"},
    "house":        {"name": "خانه ویلایی",       "price": 600_000,   "income": 900,  "type": "مسکونی"},
    "shop":         {"name": "مغازه",             "price": 350_000,   "income": 700,  "type": "تجاری"},
    "villa":        {"name": "ویلا",              "price": 1_200_000, "income": 1500, "type": "مسکونی لوکس"},
    "factory":      {"name": "کارخانه",           "price": 3_000_000, "income": 5000, "type": "صنعتی"},
    "hotel":        {"name": "هتل",               "price": 5_000_000, "income": 9000, "type": "تجاری لوکس"},
}

VEHICLES = {
    "bike":       {"name": "دوچرخه",      "price": 3_000,      "happiness": 2},
    "motorcycle": {"name": "موتور",       "price": 25_000,     "happiness": 5},
    "car":        {"name": "ماشین",       "price": 180_000,    "happiness": 10},
    "luxury_car": {"name": "ماشین لوکس",  "price": 900_000,    "happiness": 20},
    "truck":      {"name": "کامیون",      "price": 400_000,    "happiness": 8},
    "boat":       {"name": "قایق",        "price": 1_500_000,  "happiness": 25},
    "helicopter": {"name": "هلیکوپتر",    "price": 6_000_000,  "happiness": 40},
    "airplane":   {"name": "هواپیما",     "price": 20_000_000, "happiness": 60},
}

DAILY_MISSIONS = [
    {"key": "work_3", "desc": "۳ بار کار کن", "target": 3, "reward_cash": 3000, "reward_xp": 15},
    {"key": "train_2", "desc": "۲ بار مهارت تمرین کن", "target": 2, "reward_cash": 2000, "reward_xp": 20},
    {"key": "sleep_1", "desc": "۱ بار بخواب", "target": 1, "reward_cash": 1000, "reward_xp": 5},
    {"key": "eat_2", "desc": "۲ بار غذا بخور", "target": 2, "reward_cash": 1500, "reward_xp": 8},
]

# آستانه‌های سطح‌بندی بر اساس دارایی خالص (Net Worth)
LEVEL_THRESHOLDS = [
    (0, "تازه‌وارد"),
    (50_000, "کارگر ساده"),
    (200_000, "شهروند معمولی"),
    (600_000, "شهروند فعال"),
    (1_500_000, "متمول"),
    (4_000_000, "ثروتمند"),
    (10_000_000, "الیت شهر"),
    (30_000_000, "میلیاردر"),
    (100_000_000, "افسانه"),
]

# ----------------------------------------------------------------------------
# لایه دیتابیس
# ----------------------------------------------------------------------------

@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                bio TEXT DEFAULT 'یک شهروند تازه‌وارد',
                avatar TEXT DEFAULT '🙂',
                cash INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0,
                credit_score INTEGER DEFAULT 500,
                age INTEGER DEFAULT 18,
                energy INTEGER DEFAULT 100,
                health INTEGER DEFAULT 100,
                happiness INTEGER DEFAULT 100,
                stress INTEGER DEFAULT 0,
                hunger INTEGER DEFAULT 0,
                sleep INTEGER DEFAULT 100,
                intelligence INTEGER DEFAULT 10,
                xp INTEGER DEFAULT 0,
                job TEXT DEFAULT NULL,
                loan_amount INTEGER DEFAULT 0,
                last_work REAL DEFAULT 0,
                last_train REAL DEFAULT 0,
                last_sleep REAL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                married_to INTEGER DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS user_skills (
                user_id INTEGER,
                skill TEXT,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, skill),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS user_properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                prop_key TEXT,
                bought_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS user_vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                veh_key TEXT,
                bought_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS friendships (
                user_id INTEGER,
                friend_id INTEGER,
                PRIMARY KEY (user_id, friend_id)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                kind TEXT,
                amount INTEGER,
                note TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS daily_missions (
                user_id INTEGER,
                mission_key TEXT,
                progress INTEGER DEFAULT 0,
                claimed INTEGER DEFAULT 0,
                day TEXT,
                PRIMARY KEY (user_id, mission_key, day)
            );
            """
        )


def get_user(user_id: int):
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def ensure_user(user_id: int, username: str):
    u = get_user(user_id)
    if u:
        return u
    with db() as conn:
        card_number = _generate_card_number(conn)
        conn.execute(
            "INSERT INTO users (user_id, username, cash, bank, card_number) VALUES (?,?,?,?,?)",
            (user_id, username, START_CASH, START_BANK, card_number),
        )
        for skill in SKILLS:
            conn.execute(
                "INSERT INTO user_skills (user_id, skill, level, xp) VALUES (?,?,1,0)",
                (user_id, skill),
            )
    return get_user(user_id)


def update_user(user_id: int, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [user_id]
    with db() as conn:
        conn.execute(f"UPDATE users SET {cols} WHERE user_id=?", vals)


def log_tx(user_id: int, kind: str, amount: int, note: str = ""):
    with db() as conn:
        conn.execute(
            "INSERT INTO transactions (user_id, kind, amount, note) VALUES (?,?,?,?)",
            (user_id, kind, amount, note),
        )


def get_skill(user_id: int, skill: str):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM user_skills WHERE user_id=? AND skill=?", (user_id, skill)
        ).fetchone()
        return dict(row) if row else {"level": 1, "xp": 0}


def add_skill_xp(user_id: int, skill: str, amount: int):
    s = get_skill(user_id, skill)
    new_xp = s["xp"] + amount
    new_level = s["level"]
    needed = new_level * 100
    leveled_up = False
    while new_xp >= needed:
        new_xp -= needed
        new_level += 1
        needed = new_level * 100
        leveled_up = True
    with db() as conn:
        conn.execute(
            "UPDATE user_skills SET level=?, xp=? WHERE user_id=? AND skill=?",
            (new_level, new_xp, user_id, skill),
        )
    return new_level, leveled_up


def net_worth(u: dict) -> int:
    with db() as conn:
        props = conn.execute(
            "SELECT prop_key FROM user_properties WHERE user_id=?", (u["user_id"],)
        ).fetchall()
        vehs = conn.execute(
            "SELECT veh_key FROM user_vehicles WHERE user_id=?", (u["user_id"],)
        ).fetchall()
    prop_value = sum(PROPERTIES[p["prop_key"]]["price"] for p in props if p["prop_key"] in PROPERTIES)
    veh_value = sum(VEHICLES[v["veh_key"]]["price"] for v in vehs if v["veh_key"] in VEHICLES)
    return u["cash"] + u["bank"] + prop_value + veh_value - u["loan_amount"]


def level_for_networth(nw: int):
    title = LEVEL_THRESHOLDS[0][1]
    idx = 0
    for i, (threshold, name) in enumerate(LEVEL_THRESHOLDS):
        if nw >= threshold:
            title = name
            idx = i
        else:
            break
    return idx, title


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def today_str():
    return date.today().isoformat()


# ----------------------------------------------------------------------------
# ابزارهای کمکی برای ماموریت روزانه
# ----------------------------------------------------------------------------

def bump_mission(user_id: int, mission_key: str, amount: int = 1):
    day = today_str()
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM daily_missions WHERE user_id=? AND mission_key=? AND day=?",
            (user_id, mission_key, day),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE daily_missions SET progress=progress+? WHERE user_id=? AND mission_key=? AND day=?",
                (amount, user_id, mission_key, day),
            )
        else:
            conn.execute(
                "INSERT INTO daily_missions (user_id, mission_key, progress, day) VALUES (?,?,?,?)",
                (user_id, mission_key, amount, day),
            )


def get_missions_today(user_id: int):
    day = today_str()
    with db() as conn:
        rows = {
            r["mission_key"]: dict(r)
            for r in conn.execute(
                "SELECT * FROM daily_missions WHERE user_id=? AND day=?", (user_id, day)
            ).fetchall()
        }
    result = []
    for m in DAILY_MISSIONS:
        state = rows.get(m["key"], {"progress": 0, "claimed": 0})
        result.append({**m, "progress": state["progress"], "claimed": state["claimed"]})
    return result


# ----------------------------------------------------------------------------
# دستورات بات (Handlers)
# ----------------------------------------------------------------------------

def fmt_money(n: int) -> str:
    return f"{n:,} تومان"


def md_escape(text) -> str:
    """فرار دادن کاراکترهای خاص Markdown (legacy) قبل از قرار دادن متن دلخواه (مثل یوزرنیم) داخل پیام‌های بولد/کد."""
    text = str(text)
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, "\\" + ch)
    return text


def stat_bar(value, max_value=100, length=10):
    value = clamp(value, 0, max_value)
    filled = round((value / max_value) * length) if max_value else 0
    return "▰" * filled + "▱" * (length - filled)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    u = ensure_user(tg_user.id, tg_user.username or tg_user.first_name)
    if not await enforce_maintenance(update, context):
        return
    if not await enforce_force_join(update, context):
        return
    idx, title = level_for_networth(net_worth(u))
    text = (
        f"🌆 *به LifeBot خوش اومدی، {md_escape(tg_user.first_name)}!*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "اینجا زندگی خودت رو می‌سازی؛ شغل بگیر، درس بخون، پول دربیار،\n"
        "خونه و دارایی بخر، رابطه بساز و حتی روی آینده‌ی شهرت اثر بذار.\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"💰 سرمایه شروع: *{fmt_money(u['cash'])}*   🏅 رتبه: *{title}* (سطح {idx})\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "🎮 بیشتر کارهای بازی از همین منوی دکمه‌ای انجام می‌شن.\n"
        "هر انتخاب می‌تونه روی پول، انرژی، روابط و مسیر زندگی‌ات اثر بذاره."
    )
    is_private = update.effective_chat.type == "private"
    await update.message.reply_text(
        text,
        reply_markup=main_menu_keyboard(tg_user.id, is_private),
        parse_mode="Markdown",
    )
    # برای منوی گروهی، پیام جداگانه نمی‌سازیم؛ /menu همچنان مسیر اصلی بازکردن منوی مالک‌شده است.

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *راهنمای LifeBot*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "🎮 *روش بازی:* مسیر اصلی از منوی دکمه‌ایه؛ لازم نیست commandها رو حفظ کنی.\n\n"
        "👤 *پروفایل* — وضعیت شخصیت، پول، شغل، سلامت و رتبه\n"
        "💼 *شغل و مهارت* — استخدام، کار، تمرین و رشد مهارت\n"
        "🏦 *بانک و اعتبار* — موجودی، انتقال، وام و سابقه اعتباری\n"
        "🏠 *خانه و دارایی* — ملک، وسیله نقلیه و سرمایه‌گذاری\n"
        "👥 *روابط* — دوستان، ازدواج و خانواده\n"
        "🏙️ *شهرداری* — فقط در گروه؛ انتخابات، رأی‌گیری و بودجه شهر\n"
        "🎯 *ماموریت‌ها* — جایزه‌های روزانه، هفتگی و ماهانه\n"
        "🌍 *وضعیت جهان* — رویدادهایی که روی شرایط بازی اثر می‌ذارن\n\n"
        "⌨️ دستورهای قبلی هنوز فعال‌اند تا سازگاری نسخه‌های قبلی حفظ بشه.\n"
        "اما برای بازیکن عادی، تقریباً همه‌چیز از همین منو قابل انجامه.\n\n"
        "💡 دکمه «بازگشت» توی هر صفحه تو رو بدون دردسر به مرحله قبل برمی‌گردونه."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    u = ensure_user(tg_user.id, tg_user.username or tg_user.first_name)
    nw = net_worth(u)
    idx, title = level_for_networth(nw)
    job_name = get_job_label(u)
    text = (
        f"{u['avatar']} پروفایل {tg_user.first_name}\n"
        f"📝 بیو: {u['bio']}\n"
        f"🏅 رتبه: {title} (سطح {idx})\n"
        f"💵 پول نقد: {fmt_money(u['cash'])}\n"
        f"🏦 موجودی بانک: {fmt_money(u['bank'])}\n"
        f"📊 اعتبار بانکی: {u['credit_score']}\n"
        f"💎 دارایی خالص: {fmt_money(nw)}\n"
        f"💼 شغل: {job_name}\n"
        f"🎂 سن: {u['age']}\n"
        f"⚡ انرژی: {u['energy']}/{ENERGY_MAX}\n"
        f"❤️ سلامت: {u['health']}/100\n"
        f"😊 شادی: {u['happiness']}/100\n"
        f"😰 استرس: {u['stress']}/100\n"
        f"🍔 گرسنگی: {u['hunger']}/100\n"
        f"😴 خواب: {u['sleep']}/100\n"
        f"🧠 هوش: {u['intelligence']}\n"
        f"⭐ تجربه (XP): {u['xp']}\n"
    )
    if u["loan_amount"] > 0:
        text += f"💳 بدهی وام: {fmt_money(u['loan_amount'])}\n"
    await update.message.reply_text(text)


async def cmd_setbio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    bio = " ".join(context.args)
    if not bio:
        await update.message.reply_text("استفاده: /setbio متن بیو شما")
        return
    update_user(u["user_id"], bio=bio[:200])
    await update.message.reply_text("✅ بیو شما به‌روزرسانی شد.")


async def cmd_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["💼 لیست شغل‌های موجود:\n"]
    for key, j in JOBS.items():
        skill_txt = SKILLS.get(j["skill"], "بدون نیاز مهارتی") if j["skill"] else "بدون نیاز مهارتی"
        lines.append(
            f"• /apply {key} — {j['name']} | حقوق هر شیفت: {fmt_money(j['pay'])} | "
            f"نیاز: سطح {j['min_level']} مهارت {skill_txt}"
        )
    await update.message.reply_text("\n".join(lines))


async def cmd_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if not context.args:
        await update.message.reply_text("استفاده: /apply <کد شغل> — مثلا /apply driver")
        return
    key = context.args[0].lower()
    job = JOBS.get(key)
    if not job:
        await update.message.reply_text("چنین شغلی وجود نداره. با /jobs لیست شغل‌ها رو ببین.")
        return
    edu_min = JOB_EDU_MIN.get(key, 0)
    if edu_min > u.get("edu_level", 0):
        await update.message.reply_text(
            f"❌ برای این شغل به مدرک «{edu_name(edu_min)}» نیاز داری "
            f"(فعلی: {edu_name(u.get('edu_level', 0))}). با /study درس بخون."
        )
        return
    if job["skill"]:
        s = get_skill(u["user_id"], job["skill"])
        if s["level"] < job["min_level"]:
            await update.message.reply_text(
                f"❌ برای این شغل به سطح {job['min_level']} مهارت {SKILLS[job['skill']]} نیاز داری "
                f"(سطح فعلی تو: {s['level']}). با /train {job['skill']} تمرین کن."
            )
            return
    update_user(u["user_id"], job=key)
    await update.message.reply_text(f"✅ استخدام شدی! شغل جدید: {job['name']}\nحالا می‌تونی با /work کار کنی.")


async def cmd_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if not u["job"]:
        await update.message.reply_text("❌ اول باید استخدام بشی. لیست شغل‌ها: /jobs")
        return
    if u.get("jailed_until", 0) and u["jailed_until"] > time.time():
        remain = int((u["jailed_until"] - time.time()) / 60) + 1
        await update.message.reply_text(f"🚔 تو در زندانی و {remain} دقیقه دیگه آزاد می‌شی. برای آزادی زودتر: /bail <مبلغ>")
        return

    job = JOBS[u["job"]]
    now = time.time()
    elapsed_min = (now - u["last_work"]) / 60
    if elapsed_min < WORK_COOLDOWN_MIN:
        remain = int(WORK_COOLDOWN_MIN - elapsed_min)
        await update.message.reply_text(f"⏳ باید {remain} دقیقه دیگه صبر کنی تا بتونی دوباره کار کنی.")
        return
    if u["energy"] < job["energy"]:
        await update.message.reply_text("⚡ انرژی کافی نداری! با /sleep استراحت کن.")
        return

    # عملکرد بر اساس سطح مهارت مرتبط، تصادفی بودن جزئی برای واقعی‌تر شدن
    skill_level = 1
    if job["skill"]:
        skill_level = get_skill(u["user_id"], job["skill"])["level"]
    performance = random.uniform(0.9, 1.15) * (1 + 0.05 * (skill_level - 1))
    pay = int(job["pay"] * performance)

    new_energy = clamp(u["energy"] - job["energy"], 0, ENERGY_MAX)
    new_stress = clamp(u["stress"] + job["stress"], 0, STRESS_MAX)
    new_hunger = clamp(u["hunger"] + 8, 0, HUNGER_MAX)

    update_user(
        u["user_id"],
        cash=u["cash"] + pay,
        energy=new_energy,
        stress=new_stress,
        hunger=new_hunger,
        xp=u["xp"] + job["xp"],
        last_work=now,
    )
    log_tx(u["user_id"], "salary", pay, job["name"])
    bump_mission(u["user_id"], "work_3")
    bump_periodic_mission(u["user_id"], "w_work_15", period_id_week())
    bump_periodic_mission(u["user_id"], "m_networth_up", period_id_month())

    level_up_note = ""
    if job["skill"]:
        new_level, leveled = add_skill_xp(u["user_id"], job["skill"], job["xp"])
        if leveled:
            level_up_note = f"\n🎉 مهارت {SKILLS[job['skill']]} به سطح {new_level} رسید!"

    await update.message.reply_text(
        f"🛠 یک شیفت کار کردی و {fmt_money(pay)} گرفتی.\n"
        f"⚡ انرژی: {new_energy}/{ENERGY_MAX} | 😰 استرس: {new_stress}{level_up_note}"
    )


async def cmd_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    lines = ["🧩 مهارت‌های شما:\n"]
    for key, name in SKILLS.items():
        s = get_skill(u["user_id"], key)
        needed = s["level"] * 100
        lines.append(f"• {name}: سطح {s['level']} (XP {s['xp']}/{needed})")
    lines.append("\nبرای تمرین: /train <کد مهارت>  — مثلا /train programming")
    await update.message.reply_text("\n".join(lines))


async def cmd_train(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if not context.args:
        await update.message.reply_text("استفاده: /train <کد مهارت>. کدها: " + ", ".join(SKILLS.keys()))
        return
    skill = context.args[0].lower()
    if skill not in SKILLS:
        await update.message.reply_text("مهارت نامعتبره. کدها: " + ", ".join(SKILLS.keys()))
        return
    now = time.time()
    elapsed_min = (now - u["last_train"]) / 60
    if elapsed_min < TRAIN_COOLDOWN_MIN:
        remain = int(TRAIN_COOLDOWN_MIN - elapsed_min)
        await update.message.reply_text(f"⏳ {remain} دقیقه دیگه صبر کن.")
        return
    if u["energy"] < 15:
        await update.message.reply_text("⚡ انرژی کافی نداری.")
        return

    gained_xp = random.randint(8, 20) + u["intelligence"] // 5
    new_level, leveled = add_skill_xp(u["user_id"], skill, gained_xp)
    new_energy = clamp(u["energy"] - 15, 0, ENERGY_MAX)
    update_user(u["user_id"], energy=new_energy, last_train=now, intelligence=u["intelligence"] + 1)
    bump_mission(u["user_id"], "train_2")
    bump_periodic_mission(u["user_id"], "w_train_10", period_id_week())

    msg = f"📚 تمرین {SKILLS[skill]} انجام شد. +{gained_xp} XP مهارت."
    if leveled:
        msg += f"\n🎉 مهارت به سطح {new_level} رسید!"
    await update.message.reply_text(msg)


async def cmd_sleep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    now = time.time()
    elapsed_min = (now - u["last_sleep"]) / 60
    if elapsed_min < SLEEP_COOLDOWN_MIN:
        remain = int(SLEEP_COOLDOWN_MIN - elapsed_min)
        await update.message.reply_text(f"⏳ هنوز خسته نیستی، {remain} دقیقه دیگه صبر کن.")
        return
    update_user(
        u["user_id"],
        energy=ENERGY_MAX,
        sleep=SLEEP_MAX,
        stress=clamp(u["stress"] - 30, 0, STRESS_MAX),
        last_sleep=now,
    )
    bump_mission(u["user_id"], "sleep_1")
    await update.message.reply_text("😴 خوب خوابیدی! انرژی و خواب کامل شد و استرس کم شد.")


async def cmd_eat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    cost = 500
    if u["cash"] < cost:
        await update.message.reply_text("💸 پول نقد کافی نداری (هزینه غذا: 500 تومان).")
        return
    update_user(
        u["user_id"],
        cash=u["cash"] - cost,
        hunger=clamp(u["hunger"] - 40, 0, HUNGER_MAX),
        happiness=clamp(u["happiness"] + 5, 0, HAPPINESS_MAX),
    )
    log_tx(u["user_id"], "food", -cost, "غذا")
    bump_mission(u["user_id"], "eat_2")
    await update.message.reply_text("🍔 غذا خوردی. گرسنگی کم شد و کمی شادتر شدی.")


async def cmd_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    max_loan = u["credit_score"] * get_loan_max_multiplier()
    await update.message.reply_text(
        f"🏦 وضعیت بانکی\n"
        f"💵 پول نقد: {fmt_money(u['cash'])}\n"
        f"🏦 موجودی بانک: {fmt_money(u['bank'])}\n"
        f"📊 امتیاز اعتبار: {u['credit_score']}\n"
        f"💳 بدهی وام فعلی: {fmt_money(u['loan_amount'])}\n"
        f"📈 سقف وام قابل دریافت: {fmt_money(max_loan)}\n\n"
        "دستورات: /deposit <مبلغ> — /withdraw <مبلغ> — /loan <مبلغ> — /payloan <مبلغ>"
    )


async def cmd_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    amount = _parse_amount(context.args)
    if amount is None or amount <= 0:
        await update.message.reply_text("استفاده: /deposit <مبلغ>")
        return
    if amount > u["cash"]:
        await update.message.reply_text("پول نقد کافی نداری.")
        return
    update_user(u["user_id"], cash=u["cash"] - amount, bank=u["bank"] + amount)
    await update.message.reply_text(f"✅ {fmt_money(amount)} به بانک واریز شد.")


async def cmd_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    amount = _parse_amount(context.args)
    if amount is None or amount <= 0:
        await update.message.reply_text("استفاده: /withdraw <مبلغ>")
        return
    if amount > u["bank"]:
        await update.message.reply_text("موجودی بانکی کافی نیست.")
        return
    update_user(u["user_id"], cash=u["cash"] + amount, bank=u["bank"] - amount)
    await update.message.reply_text(f"✅ {fmt_money(amount)} برداشت شد.")


async def cmd_loan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    amount = _parse_amount(context.args)
    if amount is None or amount <= 0:
        await update.message.reply_text("استفاده: /loan <مبلغ>")
        return
    max_loan = u["credit_score"] * get_loan_max_multiplier()
    if u["loan_amount"] + amount > max_loan:
        await update.message.reply_text(f"❌ سقف وام قابل دریافت تو {fmt_money(max_loan)} است.")
        return
    total_due = int(amount * (1 + LOAN_INTEREST))
    update_user(
        u["user_id"],
        cash=u["cash"] + amount,
        loan_amount=u["loan_amount"] + total_due,
        credit_score=max(300, u["credit_score"] - 15),
    )
    log_tx(u["user_id"], "loan", amount, "دریافت وام")
    await update.message.reply_text(
        f"💰 وام {fmt_money(amount)} دریافت شد.\nبدهی با سود: {fmt_money(total_due)}\n"
        "توجه: امتیاز اعتباری تو کمی کاهش یافت تا وام رو بازپرداخت کنی."
    )


async def cmd_payloan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    amount = _parse_amount(context.args)
    if amount is None or amount <= 0:
        await update.message.reply_text("استفاده: /payloan <مبلغ>")
        return
    if amount > u["cash"]:
        await update.message.reply_text("پول نقد کافی نداری.")
        return
    pay = min(amount, u["loan_amount"])
    update_user(
        u["user_id"],
        cash=u["cash"] - pay,
        loan_amount=u["loan_amount"] - pay,
        credit_score=min(900, u["credit_score"] + 10),
    )
    log_tx(u["user_id"], "loan_payment", -pay, "بازپرداخت وام")
    remain = u["loan_amount"] - pay
    msg = f"✅ {fmt_money(pay)} بازپرداخت شد."
    if remain <= 0:
        msg += "\n🎉 وام تو کاملاً تسویه شد و امتیاز اعتباری‌ات بهتر شد!"
    await update.message.reply_text(msg)


def _parse_amount(args):
    if not args:
        return None
    try:
        return int(args[0].replace(",", ""))
    except ValueError:
        return None


async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["🏠 فروشگاه املاک:\n"]
    for key, p in PROPERTIES.items():
        income_txt = f" | درآمد غیرفعال: {fmt_money(p['income'])}/شیفت" if p["income"] else ""
        lines.append(f"• /buyprop {key} — {p['name']} ({p['type']}) — {fmt_money(p['price'])}{income_txt}")
    lines.append("\n🚗 فروشگاه وسایل نقلیه:\n")
    for key, v in VEHICLES.items():
        lines.append(f"• /buyveh {key} — {v['name']} — {fmt_money(v['price'])} (+{v['happiness']} شادی)")
    await update.message.reply_text("\n".join(lines))


async def cmd_buyprop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if not context.args:
        await update.message.reply_text("استفاده: /buyprop <کد ملک>")
        return
    key = context.args[0].lower()
    prop = PROPERTIES.get(key)
    if not prop:
        await update.message.reply_text("چنین ملکی وجود نداره. با /shop لیست رو ببین.")
        return
    total = u["cash"] + u["bank"]
    if total < prop["price"]:
        await update.message.reply_text(f"❌ دارایی کافی نداری. قیمت: {fmt_money(prop['price'])}")
        return
    # اول از پول نقد کم می‌کنه، بعد از بانک
    from_cash = min(u["cash"], prop["price"])
    from_bank = prop["price"] - from_cash
    with db() as conn:
        conn.execute(
            "UPDATE users SET cash=cash-?, bank=bank-? WHERE user_id=?",
            (from_cash, from_bank, u["user_id"]),
        )
        conn.execute(
            "INSERT INTO user_properties (user_id, prop_key) VALUES (?,?)", (u["user_id"], key)
        )
    log_tx(u["user_id"], "buy_property", -prop["price"], prop["name"])
    bump_periodic_mission(u["user_id"], "m_property", period_id_month())
    await update.message.reply_text(f"🏠 تبریک! {prop['name']} رو خریدی.")


async def cmd_buyveh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if not context.args:
        await update.message.reply_text("استفاده: /buyveh <کد وسیله نقلیه>")
        return
    key = context.args[0].lower()
    veh = VEHICLES.get(key)
    if not veh:
        await update.message.reply_text("چنین وسیله‌ای وجود نداره. با /shop لیست رو ببین.")
        return
    total = u["cash"] + u["bank"]
    if total < veh["price"]:
        await update.message.reply_text(f"❌ دارایی کافی نداری. قیمت: {fmt_money(veh['price'])}")
        return
    from_cash = min(u["cash"], veh["price"])
    from_bank = veh["price"] - from_cash
    with db() as conn:
        conn.execute(
            "UPDATE users SET cash=cash-?, bank=bank-?, happiness=MIN(100, happiness+?) WHERE user_id=?",
            (from_cash, from_bank, veh["happiness"], u["user_id"]),
        )
        conn.execute("INSERT INTO user_vehicles (user_id, veh_key) VALUES (?,?)", (u["user_id"], key))
    log_tx(u["user_id"], "buy_vehicle", -veh["price"], veh["name"])
    bump_periodic_mission(u["user_id"], "m_property", period_id_month())
    await update.message.reply_text(f"🚗 تبریک! {veh['name']} رو خریدی.")


async def cmd_myassets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    with db() as conn:
        props = conn.execute(
            "SELECT prop_key FROM user_properties WHERE user_id=?", (u["user_id"],)
        ).fetchall()
        vehs = conn.execute(
            "SELECT veh_key FROM user_vehicles WHERE user_id=?", (u["user_id"],)
        ).fetchall()
    lines = ["🏠 املاک شما:"]
    if props:
        for p in props:
            info = PROPERTIES.get(p["prop_key"])
            if info:
                lines.append(f"• {info['name']} — ارزش {fmt_money(info['price'])}")
    else:
        lines.append("چیزی نداری.")
    lines.append("\n🚗 وسایل نقلیه شما:")
    if vehs:
        for v in vehs:
            info = VEHICLES.get(v["veh_key"])
            if info:
                lines.append(f"• {info['name']} — ارزش {fmt_money(info['price'])}")
    else:
        lines.append("چیزی نداری.")
    await update.message.reply_text("\n".join(lines))


async def cmd_mission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    missions = get_missions_today(u["user_id"])
    lines = ["🎯 ماموریت‌های امروز:\n"]
    for m in missions:
        status = "✅ انجام شد" if m["progress"] >= m["target"] else f"{m['progress']}/{m['target']}"
        claimed = " (دریافت شده)" if m["claimed"] else ""
        lines.append(f"• {m['desc']} — {status}{claimed}")
    lines.append("\nبرای دریافت جایزه: /claim <کد ماموریت> — کدها: " + ", ".join(m["key"] for m in DAILY_MISSIONS))
    await update.message.reply_text("\n".join(lines))


async def cmd_claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if not context.args:
        await update.message.reply_text("استفاده: /claim <کد ماموریت>")
        return
    key = context.args[0]
    mission_def = next((m for m in DAILY_MISSIONS if m["key"] == key), None)
    if not mission_def:
        await update.message.reply_text("ماموریت نامعتبره.")
        return
    day = today_str()
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM daily_missions WHERE user_id=? AND mission_key=? AND day=?",
            (u["user_id"], key, day),
        ).fetchone()
    progress = row["progress"] if row else 0
    claimed = row["claimed"] if row else 0
    if claimed:
        await update.message.reply_text("قبلاً جایزه این ماموریت رو گرفتی.")
        return
    if progress < mission_def["target"]:
        await update.message.reply_text("هنوز این ماموریت رو کامل نکردی.")
        return
    with db() as conn:
        conn.execute(
            "UPDATE daily_missions SET claimed=1 WHERE user_id=? AND mission_key=? AND day=?",
            (u["user_id"], key, day),
        )
    update_user(u["user_id"], cash=u["cash"] + mission_def["reward_cash"], xp=u["xp"] + mission_def["reward_xp"])
    log_tx(u["user_id"], "mission_reward", mission_def["reward_cash"], mission_def["desc"])
    await update.message.reply_text(
        f"🎉 جایزه دریافت شد: {fmt_money(mission_def['reward_cash'])} + {mission_def['reward_xp']} XP"
    )


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        rows = conn.execute("SELECT * FROM users").fetchall()
    users = [dict(r) for r in rows]
    ranked = sorted(users, key=lambda u: net_worth(u), reverse=True)[:10]
    lines = ["🏆 جدول رتبه‌بندی ثروتمندترین شهروندان:\n"]
    for i, u in enumerate(ranked, 1):
        name = u["username"] or f"کاربر {u['user_id']}"
        lines.append(f"{i}. {name} — {fmt_money(net_worth(u))}")
    if not ranked:
        lines.append("هنوز کسی بازی نکرده!")
    await update.message.reply_text("\n".join(lines))


async def cmd_give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if not update.message.reply_to_message:
        await update.message.reply_text("برای هدیه دادن، روی پیام فرد مقصد ریپلای کن و بنویس: /give <مبلغ>")
        return
    target = update.message.reply_to_message.from_user
    if target.id == u["user_id"]:
        await update.message.reply_text("نمی‌تونی به خودت هدیه بدی!")
        return
    amount = _parse_amount(context.args)
    if amount is None or amount <= 0:
        await update.message.reply_text("استفاده: (ریپلای) /give <مبلغ>")
        return
    if amount > u["cash"]:
        await update.message.reply_text("پول نقد کافی نداری.")
        return
    ensure_user(target.id, target.username or target.first_name)
    target_u = get_user(target.id)
    update_user(u["user_id"], cash=u["cash"] - amount)
    update_user(target.id, cash=target_u["cash"] + amount)
    log_tx(u["user_id"], "gift_sent", -amount, f"به {target.first_name}")
    log_tx(target.id, "gift_received", amount, f"از {update.effective_user.first_name}")
    await update.message.reply_text(f"🎁 {fmt_money(amount)} به {target.first_name} هدیه دادی!")


# ----------------------------------------------------------------------------
# Job قدیمی: افت طبیعی وضعیت شخصیت با گذر زمان (شبیه‌سازی گذر واقعیِ زندگی)
# ----------------------------------------------------------------------------

async def periodic_decay(context: ContextTypes.DEFAULT_TYPE):
    """هر چند دقیقه یک بار روی همه کاربران اجرا می‌شه: گرسنگی بالا می‌ره،
    خواب و انرژی کم می‌شه، در صورت غفلت شادی افت می‌کنه."""
    with db() as conn:
        rows = conn.execute("SELECT user_id, hunger, sleep, energy, happiness, health, stress FROM users").fetchall()
        for r in rows:
            new_hunger = clamp(r["hunger"] + 2, 0, HUNGER_MAX)
            new_sleep = clamp(r["sleep"] - 2, 0, SLEEP_MAX)
            new_happiness = clamp(r["happiness"] - 1, 0, HAPPINESS_MAX)
            new_health = r["health"]
            if new_hunger >= 90 or new_sleep <= 10:
                new_health = clamp(r["health"] - 3, 0, 100)
            conn.execute(
                "UPDATE users SET hunger=?, sleep=?, happiness=?, health=? WHERE user_id=?",
                (new_hunger, new_sleep, new_happiness, new_health, r["user_id"]),
            )


# ==============================================================================
# فاز ۲ — سیستم‌های پیشرفته (شرکت‌ها، بازار آزاد، بورس، ازدواج/خانواده، شهرها،
# جرم و قانون، رویدادهای جهانی، سرگرمی‌ها، مشاور هوش مصنوعی، VIP، پنل مدیریت)
# ==============================================================================

# -*- coding: utf-8 -*-


GROUP_TYPES = ("group", "supergroup")
CITY_ELECTION_INTERVAL = 240 * 60 * 60  # هر ۱۰ روز یک انتخابات خودکار
CITY_ELECTION_CHECK_INTERVAL = 60 * 10  # بررسی زمان انتخابات هر ۱۰ دقیقه
CITY_ELECTION_DURATION = 24 * 60 * 60  # مهلت رأی‌گیری هر دوره: ۲۴ ساعت

COMPANY_COST = 500_000
JAIL_BASE_SECONDS = 10 * 60  # ۱۰ دقیقه پایه برای زندان

# ----------------------------------------------------------------------------
# دیتابیس فاز ۲
# ----------------------------------------------------------------------------

def init_extra_db():
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                name TEXT,
                capital INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS company_employees (
                company_id INTEGER,
                user_id INTEGER,
                salary INTEGER DEFAULT 2000,
                PRIMARY KEY (company_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS market_listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER,
                item_name TEXT,
                price INTEGER,
                quantity INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS stocks (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                price INTEGER
            );
            CREATE TABLE IF NOT EXISTS user_stocks (
                user_id INTEGER,
                symbol TEXT,
                qty INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, symbol)
            );
            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposer_id INTEGER,
                target_id INTEGER,
                kind TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS families (
                user_id INTEGER PRIMARY KEY,
                spouse_id INTEGER,
                children INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS cities (
                chat_id INTEGER PRIMARY KEY,
                name TEXT,
                mayor_id INTEGER,
                budget INTEGER DEFAULT 0,
                score INTEGER DEFAULT 0,
                election_interval_hours INTEGER DEFAULT 240,
                next_election_at REAL DEFAULT 0,
                active INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS elections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                status TEXT DEFAULT 'open',
                created_at TEXT DEFAULT (datetime('now')),
                started_at REAL DEFAULT 0,
                finished_at REAL DEFAULT 0,
                automatic INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS election_candidates (
                election_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (election_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS election_votes (
                election_id INTEGER,
                voter_id INTEGER,
                candidate_id INTEGER,
                PRIMARY KEY (election_id, voter_id)
            );
            CREATE TABLE IF NOT EXISTS crime_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id INTEGER,
                target_id INTEGER,
                kind TEXT,
                amount INTEGER DEFAULT 0,
                caught INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS bot_admins (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id INTEGER,
                target_id INTEGER,
                reason TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                reviewed INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS world_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                event TEXT DEFAULT 'normal',
                description TEXT DEFAULT 'اوضاع اقتصاد عادیه.',
                pay_multiplier REAL DEFAULT 1.0,
                updated_at TEXT DEFAULT (datetime('now'))
            );
            """
        )
        conn.execute("INSERT OR IGNORE INTO world_state (id) VALUES (1)")
        # سهام پایه‌ی چند شرکت فرضی بزرگ برای شروع بورس
        default_stocks = [
            ("TAK", "شرکت فناوری تاک", 12_000),
            ("PRD", "هلدینگ پارادایس", 8_500),
            ("ENR", "انرژی نوین", 5_000),
            ("AGR", "کشاورزی سبز", 2_200),
            ("BLD", "ساختمانی بنا", 15_000),
        ]
        for sym, name, price in default_stocks:
            conn.execute(
                "INSERT OR IGNORE INTO stocks (symbol, name, price) VALUES (?,?,?)",
                (sym, name, price),
            )
    # ستون‌های اضافی روی جدول users (اگر قبلاً اضافه نشده باشن، خطا رو نادیده می‌گیریم)
    extra_columns = [
        ("jailed_until", "REAL DEFAULT 0"),
        ("banned", "INTEGER DEFAULT 0"),
        ("city_election_interval_hours", "INTEGER DEFAULT 240"),
    ]
    city_columns = [
        ("election_interval_hours", "INTEGER DEFAULT 240"),
        ("next_election_at", "REAL DEFAULT 0"),
        ("active", "INTEGER DEFAULT 1"),
    ]
    election_columns = [
        ("started_at", "REAL DEFAULT 0"),
        ("finished_at", "REAL DEFAULT 0"),
        ("automatic", "INTEGER DEFAULT 0"),
    ]
    with db() as conn:
        for col, decl in extra_columns:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {decl}")
            except Exception:
                pass  # ستون از قبل وجود داره
        for col, decl in city_columns:
            try:
                conn.execute(f"ALTER TABLE cities ADD COLUMN {col} {decl}")
            except Exception:
                pass
        for col, decl in election_columns:
            try:
                conn.execute(f"ALTER TABLE elections ADD COLUMN {col} {decl}")
            except Exception:
                pass
        conn.execute("UPDATE cities SET active=0 WHERE active IS NULL")
        conn.execute("UPDATE cities SET election_interval_hours=240 WHERE election_interval_hours IS NULL OR election_interval_hours<=0")
        conn.execute("UPDATE cities SET next_election_at=? WHERE next_election_at IS NULL OR next_election_at<=0", (time.time() + CITY_ELECTION_INTERVAL,))


def is_admin(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    try:
        with db() as conn:
            return bool(conn.execute("SELECT 1 FROM bot_admins WHERE user_id=?", (user_id,)).fetchone())
    except Exception:
        return False


def is_jailed(u: dict) -> bool:
    return bool(
        (u.get("jailed_until", 0) and u["jailed_until"] > time.time())
        or (u.get("detention_until", 0) and u["detention_until"] > time.time())
        or (u.get("prison_until", 0) and u["prison_until"] > time.time())
    )


def require_not_jailed(u: dict):
    now = time.time()
    if u.get("prison_until", 0) and u["prison_until"] > now:
        remain = int((u["prison_until"] - now) / 60) + 1
        return f"🔒 تو توی زندانی و {remain} دقیقه دیگه آزاد می‌شی."
    if u.get("detention_until", 0) and u["detention_until"] > now:
        remain = int((u["detention_until"] - now) / 60) + 1
        return f"🚔 تو توی بازداشتگاهی و {remain} دقیقه دیگه آزاد می‌شی."
    if is_jailed(u):
        remain = int((u["jailed_until"] - now) / 60) + 1
        return f"🚔 تو در زندانی و {remain} دقیقه دیگه آزاد می‌شی. برای آزادی زودتر: /bail <مبلغ>"
    return None


def require_not_banned(u: dict):
    return u.get("banned", 0) == 1


# ----------------------------------------------------------------------------
# ۱. شرکت‌ها
# ----------------------------------------------------------------------------

async def cmd_createcompany(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    name = " ".join(context.args)
    if not name:
        await update.message.reply_text(f"استفاده: /createcompany <نام شرکت>\nهزینه ثبت: {fmt_money(COMPANY_COST)}")
        return
    if u["cash"] < COMPANY_COST:
        await update.message.reply_text(f"❌ پول نقد کافی نداری. هزینه: {fmt_money(COMPANY_COST)}")
        return
    with db() as conn:
        existing = conn.execute("SELECT id FROM companies WHERE owner_id=?", (u["user_id"],)).fetchone()
        if existing:
            await update.message.reply_text("تو قبلاً یک شرکت داری. هر کاربر فقط یک شرکت می‌تونه ثبت کنه.")
            return
        conn.execute(
            "INSERT INTO companies (owner_id, name, capital) VALUES (?,?,?)",
            (u["user_id"], name[:50], 0),
        )
    update_user(u["user_id"], cash=u["cash"] - COMPANY_COST)
    log_tx(u["user_id"], "create_company", -COMPANY_COST, name)
    await update.message.reply_text(f"🏢 شرکت «{name}» ثبت شد! با /companyinvest سرمایه اضافه کن و با /hire (ریپلای) استخدام کن.")


async def cmd_mycompany(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    with db() as conn:
        c = conn.execute("SELECT * FROM companies WHERE owner_id=?", (u["user_id"],)).fetchone()
        if not c:
            await update.message.reply_text("شرکتی نداری. با /createcompany <نام> یکی بساز.")
            return
        employees = conn.execute(
            "SELECT * FROM company_employees WHERE company_id=?", (c["id"],)
        ).fetchall()
    lines = [
        f"🏢 شرکت: {c['name']}",
        f"💰 سرمایه: {fmt_money(c['capital'])}",
        f"📈 سطح: {c['level']}",
        f"👥 کارمندان: {len(employees)}",
    ]
    for e in employees:
        emp_u = get_user(e["user_id"])
        name = emp_u["username"] if emp_u else str(e["user_id"])
        lines.append(f"  • {name} — حقوق: {fmt_money(e['salary'])}")
    await update.message.reply_text("\n".join(lines))


async def cmd_companyinvest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    amount = _parse_amount(context.args)
    if amount is None or amount <= 0:
        await update.message.reply_text("استفاده: /companyinvest <مبلغ>")
        return
    with db() as conn:
        c = conn.execute("SELECT * FROM companies WHERE owner_id=?", (u["user_id"],)).fetchone()
        if not c:
            await update.message.reply_text("اول باید شرکت بسازی: /createcompany <نام>")
            return
        if amount > u["cash"]:
            await update.message.reply_text("پول نقد کافی نداری.")
            return
        new_capital = c["capital"] + amount
        new_level = 1 + new_capital // 1_000_000
        conn.execute("UPDATE companies SET capital=?, level=? WHERE id=?", (new_capital, new_level, c["id"]))
    update_user(u["user_id"], cash=u["cash"] - amount)
    await update.message.reply_text(f"✅ {fmt_money(amount)} سرمایه‌ی شرکت اضافه شد. سرمایه‌ی فعلی: {fmt_money(new_capital)}")


async def cmd_hire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if not update.message.reply_to_message:
        await update.message.reply_text("روی پیام فردی که می‌خوای استخدام کنی ریپلای کن: (ریپلای) /hire <حقوق>")
        return
    target = update.message.reply_to_message.from_user
    salary = _parse_amount(context.args) or 2000
    ensure_user(target.id, target.username or target.first_name)  # قبل از باز کردن تراکنش دیگه، تا قفل نگیره
    with db() as conn:
        c = conn.execute("SELECT * FROM companies WHERE owner_id=?", (u["user_id"],)).fetchone()
        if not c:
            await update.message.reply_text("اول باید شرکت بسازی: /createcompany <نام>")
            return
        conn.execute(
            "INSERT OR REPLACE INTO company_employees (company_id, user_id, salary) VALUES (?,?,?)",
            (c["id"], target.id, salary),
        )
    await update.message.reply_text(f"✅ {target.first_name} با حقوق {fmt_money(salary)} استخدام شد.")


async def cmd_payroll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    with db() as conn:
        c = conn.execute("SELECT * FROM companies WHERE owner_id=?", (u["user_id"],)).fetchone()
        if not c:
            await update.message.reply_text("شرکتی نداری.")
            return
        employees = conn.execute("SELECT * FROM company_employees WHERE company_id=?", (c["id"],)).fetchall()
        total_salary = sum(e["salary"] for e in employees)
        if total_salary > c["capital"]:
            await update.message.reply_text(
                f"❌ سرمایه‌ی شرکت کافی نیست. لازم: {fmt_money(total_salary)}، موجودی: {fmt_money(c['capital'])}"
            )
            return
        conn.execute("UPDATE companies SET capital=capital-? WHERE id=?", (total_salary, c["id"]))
    # پرداخت حقوق هر کارمند بعد از بسته‌شدن تراکنش بالا انجام می‌شه تا دیتابیس قفل نگیره
    for e in employees:
        emp = get_user(e["user_id"])
        if emp:
            update_user(e["user_id"], cash=emp["cash"] + e["salary"])
    await update.message.reply_text(f"✅ حقوق {len(employees)} کارمند پرداخت شد. مجموع: {fmt_money(total_salary)}")


async def cmd_companies_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        rows = conn.execute("SELECT * FROM companies ORDER BY capital DESC LIMIT 10").fetchall()
    lines = ["🏆 بزرگ‌ترین شرکت‌ها:\n"]
    for i, c in enumerate(rows, 1):
        lines.append(f"{i}. {c['name']} — سرمایه: {fmt_money(c['capital'])} (سطح {c['level']})")
    if not rows:
        lines.append("هنوز شرکتی ثبت نشده.")
    await update.message.reply_text("\n".join(lines))


# ----------------------------------------------------------------------------
# ۲. بازار آزاد (قیمت‌گذاری توسط خود کاربران)
# ----------------------------------------------------------------------------

async def cmd_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if len(context.args) < 3:
        await update.message.reply_text("استفاده: /sell <نام کالا> <تعداد> <قیمت واحد>")
        return
    *name_parts, qty_s, price_s = context.args
    item_name = " ".join(name_parts)
    try:
        qty = int(qty_s)
        price = int(price_s)
    except ValueError:
        await update.message.reply_text("تعداد و قیمت باید عدد باشن.")
        return
    if qty <= 0 or price <= 0 or not item_name:
        await update.message.reply_text("مقادیر نامعتبر.")
        return
    with db() as conn:
        conn.execute(
            "INSERT INTO market_listings (seller_id, item_name, price, quantity) VALUES (?,?,?,?)",
            (u["user_id"], item_name[:50], price, qty),
        )
    await update.message.reply_text(f"🛒 آگهی ثبت شد: {item_name} × {qty} به قیمت {fmt_money(price)} هرکدوم.")


async def cmd_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM market_listings WHERE quantity > 0 ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    if not rows:
        await update.message.reply_text("🛒 بازار خالیه. با /sell کالای خودت رو بفروش.")
        return
    lines = ["🛒 آگهی‌های بازار آزاد (قیمت توسط خود کاربران تعیین می‌شه):\n"]
    for r in rows:
        seller = get_user(r["seller_id"])
        seller_name = seller["username"] if seller else str(r["seller_id"])
        lines.append(
            f"#{r['id']} — {r['item_name']} × {r['quantity']} — {fmt_money(r['price'])}/عدد — فروشنده: {seller_name}"
        )
    lines.append("\nخرید: /buyitem <شماره آگهی> <تعداد>")
    await update.message.reply_text("\n".join(lines))


async def cmd_buyitem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if len(context.args) < 2:
        await update.message.reply_text("استفاده: /buyitem <شماره آگهی> <تعداد>")
        return
    try:
        listing_id = int(context.args[0])
        qty = int(context.args[1])
    except ValueError:
        await update.message.reply_text("مقادیر نامعتبر.")
        return
    with db() as conn:
        listing = conn.execute("SELECT * FROM market_listings WHERE id=?", (listing_id,)).fetchone()
        if not listing or listing["quantity"] <= 0:
            await update.message.reply_text("این آگهی وجود نداره یا موجودی‌ش تموم شده.")
            return
        if listing["seller_id"] == u["user_id"]:
            await update.message.reply_text("نمی‌تونی از خودت بخری!")
            return
        qty = min(qty, listing["quantity"])
        total = qty * listing["price"]
        if total > u["cash"]:
            await update.message.reply_text(f"پول نقد کافی نداری. مبلغ لازم: {fmt_money(total)}")
            return
        conn.execute("UPDATE market_listings SET quantity=quantity-? WHERE id=?", (qty, listing_id))
    # خواندن/نوشتنِ کاربر فروشنده بعد از بسته‌شدن تراکنش بالا انجام می‌شه تا دیتابیس قفل نگیره
    seller = get_user(listing["seller_id"])
    update_user(u["user_id"], cash=u["cash"] - total)
    if seller:
        update_user(seller["user_id"], cash=seller["cash"] + total)
    log_tx(u["user_id"], "market_buy", -total, listing["item_name"])
    await update.message.reply_text(f"✅ {qty} عدد {listing['item_name']} خریداری شد به مبلغ {fmt_money(total)}.")


async def cmd_mylistings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM market_listings WHERE seller_id=? AND quantity>0", (u["user_id"],)
        ).fetchall()
    if not rows:
        await update.message.reply_text("آگهی فعالی نداری.")
        return
    lines = ["📋 آگهی‌های شما:\n"]
    for r in rows:
        lines.append(f"#{r['id']} — {r['item_name']} × {r['quantity']} — {fmt_money(r['price'])}/عدد")
    lines.append("\nلغو: /cancellisting <شماره>")
    await update.message.reply_text("\n".join(lines))


async def cmd_cancellisting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if not context.args:
        await update.message.reply_text("استفاده: /cancellisting <شماره آگهی>")
        return
    try:
        listing_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("شماره نامعتبر.")
        return
    with db() as conn:
        listing = conn.execute(
            "SELECT * FROM market_listings WHERE id=? AND seller_id=?", (listing_id, u["user_id"])
        ).fetchone()
        if not listing:
            await update.message.reply_text("چنین آگهی‌ای پیدا نشد.")
            return
        conn.execute("UPDATE market_listings SET quantity=0 WHERE id=?", (listing_id,))
    await update.message.reply_text("✅ آگهی لغو شد.")


# ----------------------------------------------------------------------------
# ۳. بورس (نوسان بر اساس معاملات واقعی = مدل عرضه/تقاضای ساده)
# ----------------------------------------------------------------------------

STOCK_IMPACT = 0.01  # هر واحد خرید/فروش چقدر روی قیمت اثر بذاره


async def cmd_stocks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        rows = conn.execute("SELECT * FROM stocks ORDER BY asset_type, symbol").fetchall()
    labels = {"stock": "📈 سهام شرکت‌ها", "crypto": "🪙 ارز دیجیتال", "gold": "🥇 طلا"}
    sections = {}
    for r in rows:
        atype = r["asset_type"] if "asset_type" in r.keys() and r["asset_type"] else "stock"
        sections.setdefault(atype, []).append(r)
    lines = []
    for atype, label in labels.items():
        if atype not in sections:
            continue
        lines.append(f"{label}:")
        for r in sections[atype]:
            lines.append(f"• {r['symbol']} ({r['name']}) — {fmt_money(r['price'])}")
        lines.append("")
    lines.append("خرید: /buystock <نماد> <تعداد>\nفروش: /sellstock <نماد> <تعداد>\nپرتفوی: /mystocks")
    await update.message.reply_text("\n".join(lines))


async def cmd_buystock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if len(context.args) < 2:
        await update.message.reply_text("استفاده: /buystock <نماد> <تعداد>")
        return
    symbol = context.args[0].upper()
    try:
        qty = int(context.args[1])
    except ValueError:
        await update.message.reply_text("تعداد نامعتبر.")
        return
    if qty <= 0:
        await update.message.reply_text("تعداد باید مثبت باشه.")
        return
    with db() as conn:
        stock = conn.execute("SELECT * FROM stocks WHERE symbol=?", (symbol,)).fetchone()
        if not stock:
            await update.message.reply_text("چنین نمادی وجود نداره. با /stocks لیست رو ببین.")
            return
        total = qty * stock["price"]
        if total > u["cash"]:
            await update.message.reply_text(f"پول نقد کافی نداری. مبلغ لازم: {fmt_money(total)}")
            return
        new_price = int(stock["price"] * (1 + STOCK_IMPACT * qty))
        conn.execute("UPDATE stocks SET price=? WHERE symbol=?", (new_price, symbol))
        existing = conn.execute(
            "SELECT * FROM user_stocks WHERE user_id=? AND symbol=?", (u["user_id"], symbol)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE user_stocks SET qty=qty+? WHERE user_id=? AND symbol=?",
                (qty, u["user_id"], symbol),
            )
        else:
            conn.execute(
                "INSERT INTO user_stocks (user_id, symbol, qty) VALUES (?,?,?)",
                (u["user_id"], symbol, qty),
            )
    update_user(u["user_id"], cash=u["cash"] - total)
    log_tx(u["user_id"], "buy_stock", -total, symbol)
    await update.message.reply_text(
        f"✅ {qty} سهم {symbol} خریداری شد به مبلغ {fmt_money(total)}.\n"
        f"📈 قیمت جدید سهم (اثر تقاضا): {fmt_money(new_price)}"
    )


async def cmd_sellstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if len(context.args) < 2:
        await update.message.reply_text("استفاده: /sellstock <نماد> <تعداد>")
        return
    symbol = context.args[0].upper()
    try:
        qty = int(context.args[1])
    except ValueError:
        await update.message.reply_text("تعداد نامعتبر.")
        return
    with db() as conn:
        owned = conn.execute(
            "SELECT * FROM user_stocks WHERE user_id=? AND symbol=?", (u["user_id"], symbol)
        ).fetchone()
        if not owned or owned["qty"] < qty:
            await update.message.reply_text("این تعداد سهم رو نداری.")
            return
        stock = conn.execute("SELECT * FROM stocks WHERE symbol=?", (symbol,)).fetchone()
        total = qty * stock["price"]
        new_price = max(100, int(stock["price"] * (1 - STOCK_IMPACT * qty)))
        conn.execute("UPDATE stocks SET price=? WHERE symbol=?", (new_price, symbol))
        conn.execute(
            "UPDATE user_stocks SET qty=qty-? WHERE user_id=? AND symbol=?", (qty, u["user_id"], symbol)
        )
    update_user(u["user_id"], cash=u["cash"] + total)
    log_tx(u["user_id"], "sell_stock", total, symbol)
    await update.message.reply_text(
        f"✅ {qty} سهم {symbol} فروخته شد به مبلغ {fmt_money(total)}.\n"
        f"📉 قیمت جدید سهم (اثر عرضه): {fmt_money(new_price)}"
    )


async def cmd_mystocks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM user_stocks WHERE user_id=? AND qty>0", (u["user_id"],)
        ).fetchall()
    if not rows:
        await update.message.reply_text("سهامی نداری.")
        return
    lines = ["💼 پرتفوی سهام شما:\n"]
    with db() as conn:
        for r in rows:
            stock = conn.execute("SELECT * FROM stocks WHERE symbol=?", (r["symbol"],)).fetchone()
            value = r["qty"] * stock["price"] if stock else 0
            lines.append(f"• {r['symbol']} × {r['qty']} — ارزش فعلی: {fmt_money(value)}")
    await update.message.reply_text("\n".join(lines))


async def stock_drift_job(context: ContextTypes.DEFAULT_TYPE):
    """نوسان تصادفی کوچک روی سهام برای شبیه‌سازی بازار، مستقل از معاملات کاربران."""
    with db() as conn:
        rows = conn.execute("SELECT * FROM stocks").fetchall()
        for r in rows:
            change = random.uniform(-0.03, 0.03)
            new_price = max(100, int(r["price"] * (1 + change)))
            conn.execute("UPDATE stocks SET price=? WHERE symbol=?", (new_price, r["symbol"]))


# ----------------------------------------------------------------------------
# ۴. ازدواج، خانواده و طلاق
# ----------------------------------------------------------------------------

async def cmd_propose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if not update.message.reply_to_message:
        await update.message.reply_text("روی پیام فردی که می‌خوای بهش پیشنهاد ازدواج بدی ریپلای کن: (ریپلای) /propose")
        return
    target = update.message.reply_to_message.from_user
    if target.id == u["user_id"]:
        await update.message.reply_text("نمی‌تونی به خودت پیشنهاد بدی!")
        return
    with db() as conn:
        fam = conn.execute("SELECT * FROM families WHERE user_id=?", (u["user_id"],)).fetchone()
        if fam and fam["spouse_id"]:
            await update.message.reply_text("تو الان متأهلی. اول باید /divorce کنی.")
            return
        conn.execute(
            "INSERT INTO proposals (proposer_id, target_id, kind) VALUES (?,?, 'marriage')",
            (u["user_id"], target.id),
        )
    ensure_user(target.id, target.username or target.first_name)
    await update.message.reply_text(
        f"💍 پیشنهاد ازدواج به {target.first_name} ارسال شد!\n"
        f"{target.first_name} می‌تونه با ریپلای‌کردن روی این پیام دستور /accept رو بزنه."
    )


async def cmd_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    with db() as conn:
        proposal = conn.execute(
            "SELECT * FROM proposals WHERE target_id=? AND kind='marriage' AND status='pending' ORDER BY id DESC LIMIT 1",
            (u["user_id"],),
        ).fetchone()
        if not proposal:
            await update.message.reply_text("پیشنهاد ازدواج فعالی برای تو ثبت نشده.")
            return
        proposer_id = proposal["proposer_id"]
        conn.execute("UPDATE proposals SET status='accepted' WHERE id=?", (proposal["id"],))
        conn.execute(
            "INSERT OR REPLACE INTO families (user_id, spouse_id, children) VALUES (?,?, COALESCE((SELECT children FROM families WHERE user_id=?),0))",
            (u["user_id"], proposer_id, u["user_id"]),
        )
        conn.execute(
            "INSERT OR REPLACE INTO families (user_id, spouse_id, children) VALUES (?,?, COALESCE((SELECT children FROM families WHERE user_id=?),0))",
            (proposer_id, u["user_id"], proposer_id),
        )
    update_user(u["user_id"], married_to=proposer_id)
    update_user(proposer_id, married_to=u["user_id"])
    proposer = get_user(proposer_id)
    await update.message.reply_text(
        f"💒 تبریک! تو و {proposer['username'] or proposer_id} الان رسماً ازدواج کردید!"
    )


async def cmd_divorce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    with db() as conn:
        fam = conn.execute("SELECT * FROM families WHERE user_id=?", (u["user_id"],)).fetchone()
        if not fam or not fam["spouse_id"]:
            await update.message.reply_text("تو الان متأهل نیستی.")
            return
        spouse_id = fam["spouse_id"]
        conn.execute("UPDATE families SET spouse_id=NULL WHERE user_id=?", (u["user_id"],))
        conn.execute("UPDATE families SET spouse_id=NULL WHERE user_id=?", (spouse_id,))
    update_user(u["user_id"], married_to=None, happiness=clamp(u["happiness"] - 20, 0, 100))
    update_user(spouse_id, married_to=None)
    await update.message.reply_text("💔 طلاق ثبت شد.")


async def cmd_family(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    with db() as conn:
        fam = conn.execute("SELECT * FROM families WHERE user_id=?", (u["user_id"],)).fetchone()
    if not fam or not fam["spouse_id"]:
        await update.message.reply_text("👤 تو الان مجرد هستی و فرزندی نداری.")
        return
    spouse = get_user(fam["spouse_id"])
    spouse_name = spouse["username"] if spouse else str(fam["spouse_id"])
    await update.message.reply_text(
        f"👨‍👩‍👧 خانواده شما:\n💑 همسر: {spouse_name}\n👶 تعداد فرزندان: {fam['children']}"
    )


CHILD_COST = 100_000


async def cmd_havechild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    with db() as conn:
        fam = conn.execute("SELECT * FROM families WHERE user_id=?", (u["user_id"],)).fetchone()
        if not fam or not fam["spouse_id"]:
            await update.message.reply_text("برای بچه‌دار شدن اول باید ازدواج کنی.")
            return
        if u["cash"] < CHILD_COST:
            await update.message.reply_text(f"❌ هزینه بزرگ‌کردن بچه {fmt_money(CHILD_COST)} است و پول نقد کافی نداری.")
            return
        conn.execute("UPDATE families SET children=children+1 WHERE user_id=?", (u["user_id"],))
        conn.execute("UPDATE families SET children=children+1 WHERE user_id=?", (fam["spouse_id"],))
    update_user(u["user_id"], cash=u["cash"] - CHILD_COST, happiness=clamp(u["happiness"] + 15, 0, 100))
    await update.message.reply_text("👶 تبریک! صاحب فرزند شدید. شادی خانواده بالا رفت.")


# ----------------------------------------------------------------------------
# ۵. شهرها (گروه‌های تلگرام) — شهردار، انتخابات، بودجه، پروژه
# ----------------------------------------------------------------------------

def _in_group(update: Update) -> bool:
    return update.effective_chat.type in GROUP_TYPES


async def cmd_registercity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط مالک ربات می‌تواند شهر را فعال کند."); return
    if not _in_group(update):
        await update.message.reply_text("این دستور فقط داخل گروه کار می‌کنه.")
        return
    name = " ".join(context.args) or update.effective_chat.title
    chat_id = update.effective_chat.id
    with db() as conn:
        existing = conn.execute("SELECT * FROM cities WHERE chat_id=?", (chat_id,)).fetchone()
        if existing:
            await update.message.reply_text(f"این گروه از قبل به‌عنوان شهر «{existing['name']}» ثبت شده.")
            return
        conn.execute("INSERT INTO cities (chat_id, name, budget) VALUES (?,?,0)", (chat_id, name))
    await update.message.reply_text(f"🏙 این گروه به‌عنوان شهر «{name}» ثبت شد!\nبرای شروع انتخابات: /runformayor")


async def cmd_cityinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _in_group(update):
        await update.message.reply_text("این دستور فقط داخل گروه کار می‌کنه.")
        return
    with db() as conn:
        city = conn.execute("SELECT * FROM cities WHERE chat_id=?", (update.effective_chat.id,)).fetchone()
    if not city:
        await update.message.reply_text("این گروه هنوز شهر ثبت‌شده نیست. با /registercity <نام> ثبتش کن.")
        return
    mayor_name = "بدون شهردار"
    if city["mayor_id"]:
        mayor = get_user(city["mayor_id"])
        mayor_name = mayor["username"] if mayor else str(city["mayor_id"])
    await update.message.reply_text(
        f"🏙 شهر: {city['name']}\n👑 شهردار: {mayor_name}\n💰 بودجه شهر: {fmt_money(city['budget'])}\n🏆 امتیاز شهر: {city['score']}"
    )


async def cmd_cityfund(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _in_group(update):
        await update.message.reply_text("این دستور فقط داخل گروه کار می‌کنه.")
        return
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    amount = _parse_amount(context.args)
    if amount is None or amount <= 0:
        await update.message.reply_text("استفاده: /cityfund <مبلغ>")
        return
    if amount > u["cash"]:
        await update.message.reply_text("پول نقد کافی نداری.")
        return
    with db() as conn:
        city = conn.execute("SELECT * FROM cities WHERE chat_id=?", (update.effective_chat.id,)).fetchone()
        if not city:
            await update.message.reply_text("این گروه شهر ثبت‌شده نیست.")
            return
        conn.execute("UPDATE cities SET budget=budget+? WHERE chat_id=?", (amount, update.effective_chat.id))
    update_user(u["user_id"], cash=u["cash"] - amount)
    await update.message.reply_text(f"✅ {fmt_money(amount)} به بودجه شهر «{city['name']}» اضافه شد.")


async def cmd_runformayor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _in_group(update):
        await update.message.reply_text("این دستور فقط داخل گروه کار می‌کنه.")
        return
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    chat_id = update.effective_chat.id
    with db() as conn:
        city = conn.execute("SELECT * FROM cities WHERE chat_id=?", (chat_id,)).fetchone()
        if not city:
            await update.message.reply_text("اول این گروه رو با /registercity <نام> به‌عنوان شهر ثبت کن.")
            return
        election = conn.execute(
            "SELECT * FROM elections WHERE chat_id=? AND status='open'", (chat_id,)
        ).fetchone()
        if not election:
            cur = conn.execute("INSERT INTO elections (chat_id, status) VALUES (?, 'open')", (chat_id,))
            election_id = cur.lastrowid
        else:
            election_id = election["id"]
        conn.execute(
            "INSERT OR IGNORE INTO election_candidates (election_id, user_id) VALUES (?,?)",
            (election_id, u["user_id"]),
        )
    await update.message.reply_text(
        f"🗳 {update.effective_user.first_name} کاندید شهرداری شد!\n"
        f"رای‌دهی: (ریپلای روی پیام کاندید) /vote\nپایان انتخابات: /endelection"
    )


async def cmd_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _in_group(update):
        await update.message.reply_text("این دستور فقط داخل گروه کار می‌کنه.")
        return
    voter = ensure_user(update.effective_user.id, update.effective_user.username)
    if not update.message.reply_to_message:
        await update.message.reply_text("روی پیام کاندید موردنظر ریپلای کن و بنویس /vote")
        return
    candidate = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    with db() as conn:
        election = conn.execute(
            "SELECT * FROM elections WHERE chat_id=? AND status='open'", (chat_id,)
        ).fetchone()
        if not election:
            await update.message.reply_text("انتخابات فعالی در این شهر نیست. با /runformayor شروعش کن.")
            return
        is_candidate = conn.execute(
            "SELECT 1 FROM election_candidates WHERE election_id=? AND user_id=?",
            (election["id"], candidate.id),
        ).fetchone()
        if not is_candidate:
            await update.message.reply_text("این فرد کاندید نیست.")
            return
        conn.execute(
            "INSERT OR REPLACE INTO election_votes (election_id, voter_id, candidate_id) VALUES (?,?,?)",
            (election["id"], voter["user_id"], candidate.id),
        )
    await update.message.reply_text(f"🗳 رای تو برای {candidate.first_name} ثبت شد.")


async def cmd_endelection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _in_group(update):
        await update.message.reply_text("این دستور فقط داخل گروه کار می‌کنه.")
        return
    chat_id = update.effective_chat.id
    with db() as conn:
        election = conn.execute(
            "SELECT * FROM elections WHERE chat_id=? AND status='open'", (chat_id,)
        ).fetchone()
        if not election:
            await update.message.reply_text("انتخابات فعالی نیست.")
            return
        votes = conn.execute(
            "SELECT candidate_id, COUNT(*) as c FROM election_votes WHERE election_id=? GROUP BY candidate_id ORDER BY c DESC",
            (election["id"],),
        ).fetchall()
        conn.execute("UPDATE elections SET status='closed' WHERE id=?", (election["id"],))
        if votes:
            winner_id = votes[0]["candidate_id"]
            conn.execute("UPDATE cities SET mayor_id=? WHERE chat_id=?", (winner_id, chat_id))
        else:
            winner_id = None
    if winner_id:
        winner = get_user(winner_id)
        name = winner["username"] if winner else str(winner_id)
        await update.message.reply_text(f"🏆 انتخابات پایان یافت! شهردار جدید: {name}")
    else:
        await update.message.reply_text("انتخابات بدون رای پایان یافت. شهرداری خالی ماند.")


async def cmd_cityproject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _in_group(update):
        await update.message.reply_text("این دستور فقط داخل گروه کار می‌کنه.")
        return
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if len(context.args) < 2:
        await update.message.reply_text("استفاده: /cityproject <نام پروژه> <هزینه>")
        return
    cost_s = context.args[-1]
    project_name = " ".join(context.args[:-1])
    try:
        cost = int(cost_s)
    except ValueError:
        await update.message.reply_text("هزینه باید عدد باشه.")
        return
    with db() as conn:
        city = conn.execute("SELECT * FROM cities WHERE chat_id=?", (update.effective_chat.id,)).fetchone()
        if not city:
            await update.message.reply_text("این گروه شهر ثبت‌شده نیست.")
            return
        if city["mayor_id"] != u["user_id"]:
            await update.message.reply_text("فقط شهردار می‌تونه پروژه شهری تعریف کنه.")
            return
        if cost > city["budget"]:
            await update.message.reply_text(f"❌ بودجه شهر کافی نیست. بودجه فعلی: {fmt_money(city['budget'])}")
            return
        new_score = city["score"] + cost // 10_000
        conn.execute(
            "UPDATE cities SET budget=budget-?, score=? WHERE chat_id=?",
            (cost, new_score, update.effective_chat.id),
        )
    await update.message.reply_text(f"🏗 پروژه «{project_name}» با هزینه {fmt_money(cost)} اجرا شد! امتیاز شهر افزایش یافت.")


async def cmd_citytop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        rows = conn.execute("SELECT * FROM cities ORDER BY score DESC LIMIT 10").fetchall()
    lines = ["🏆 برترین شهرها:\n"]
    for i, c in enumerate(rows, 1):
        lines.append(f"{i}. {c['name']} — امتیاز: {c['score']} — بودجه: {fmt_money(c['budget'])}")
    if not rows:
        lines.append("هنوز شهری ثبت نشده.")
    await update.message.reply_text("\n".join(lines))


# ----------------------------------------------------------------------------
# ۶. جرم و قانون
# ----------------------------------------------------------------------------

async def cmd_crime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    jailed_msg = require_not_jailed(u)
    if jailed_msg:
        await update.message.reply_text(jailed_msg)
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("روی پیام هدف ریپلای کن: (ریپلای) /crime")
        return
    target_tg = update.message.reply_to_message.from_user
    if target_tg.id == u["user_id"]:
        await update.message.reply_text("نمی‌تونی از خودت بدزدی!")
        return
    target = ensure_user(target_tg.id, target_tg.username or target_tg.first_name)
    if target["cash"] <= 0:
        await update.message.reply_text("این فرد پول نقدی برای دزدیدن نداره.")
        return

    caught = random.random() < 0.4  # ۴۰٪ احتمال گیر افتادن
    if caught:
        insured = u.get("insurance_until", 0) > time.time()
        fine = 2500 if insured else 5000
        jail_seconds = JAIL_BASE_SECONDS // 2 if insured else JAIL_BASE_SECONDS
        new_jail_until = time.time() + jail_seconds
        with db() as conn:
            conn.execute(
                "INSERT INTO crime_log (actor_id, target_id, kind, amount, caught) VALUES (?,?,'theft',0,1)",
                (u["user_id"], target["user_id"]),
            )
        update_user(
            u["user_id"],
            cash=max(0, u["cash"] - fine),
            jailed_until=new_jail_until,
            credit_score=max(300, u["credit_score"] - 30),
        )
        note = " (بیمه‌ات نصف جریمه و زندان رو کم کرد)" if insured else ""
        await update.message.reply_text(
            f"🚔 گیر افتادی! جریمه {fmt_money(fine)} و {jail_seconds // 60} دقیقه زندان.{note}"
        )
    else:
        stolen = int(target["cash"] * random.uniform(0.05, 0.15))
        with db() as conn:
            conn.execute(
                "INSERT INTO crime_log (actor_id, target_id, kind, amount, caught) VALUES (?,?,'theft',?,0)",
                (u["user_id"], target["user_id"], stolen),
            )
        update_user(u["user_id"], cash=u["cash"] + stolen)
        update_user(target["user_id"], cash=target["cash"] - stolen)
        await update.message.reply_text(f"🕵️ موفق شدی! {fmt_money(stolen)} دزدیدی.")


async def cmd_reportcrime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if not update.message.reply_to_message:
        await update.message.reply_text("روی پیام فردی که می‌خوای گزارش بدی ریپلای کن: (ریپلای) /reportcrime <دلیل>")
        return
    target_tg = update.message.reply_to_message.from_user
    reason = " ".join(context.args) or "بدون توضیح"
    with db() as conn:
        conn.execute(
            "INSERT INTO reports (reporter_id, target_id, reason) VALUES (?,?,?)",
            (u["user_id"], target_tg.id, reason[:200]),
        )
    await update.message.reply_text("✅ گزارش ثبت شد و برای بررسی به مدیریت ارسال می‌شه.")


async def cmd_bail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if not is_jailed(u):
        await update.message.reply_text("تو الان زندانی نیستی.")
        return
    amount = _parse_amount(context.args)
    if amount is None or amount <= 0:
        await update.message.reply_text("استفاده: /bail <مبلغ> — هر ۱۰۰۰ تومان، ۱ دقیقه از زندان کم می‌کنه.")
        return
    if amount > u["cash"]:
        await update.message.reply_text("پول نقد کافی نداری.")
        return
    reduce_seconds = (amount // 1000) * 60
    new_until = max(time.time(), u["jailed_until"] - reduce_seconds)
    update_user(u["user_id"], cash=u["cash"] - amount, jailed_until=new_until)
    if new_until <= time.time():
        await update.message.reply_text("🔓 آزاد شدی!")
    else:
        remain = int((new_until - time.time()) / 60) + 1
        await update.message.reply_text(f"⏳ {remain} دقیقه دیگه تا آزادی باقی مونده.")


# ----------------------------------------------------------------------------
# ۷. رویدادهای جهانی
# ----------------------------------------------------------------------------

EVENTS = [
    ("normal", "اوضاع اقتصاد عادیه.", 1.0),
    ("recession", "📉 رکود اقتصادی! حقوق‌ها و قیمت سهام افت کردن.", 0.75),
    ("boom", "📈 رونق اقتصادی! حقوق‌ها بالا رفته.", 1.3),
    ("energy_crisis", "⚡ بحران انرژی! هزینه‌های زندگی بالا رفته.", 0.85),
    ("festival", "🎉 جشنواره‌ی شهری! همه‌ی شهروندان شادترن.", 1.1),
]


async def cmd_worldstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        state = conn.execute("SELECT * FROM world_state WHERE id=1").fetchone()
    await update.message.reply_text(
        f"🌍 وضعیت جهانی بازی:\n{state['description']}\nضریب تاثیر بر حقوق: ×{state['pay_multiplier']}"
    )


async def cmd_setevent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای مدیران است.")
        return
    if not context.args:
        keys = ", ".join(e[0] for e in EVENTS)
        await update.message.reply_text(f"استفاده: /setevent <کد رویداد>\nکدها: {keys}")
        return
    key = context.args[0]
    ev = next((e for e in EVENTS if e[0] == key), None)
    if not ev:
        await update.message.reply_text("رویداد نامعتبر.")
        return
    with db() as conn:
        conn.execute(
            "UPDATE world_state SET event=?, description=?, pay_multiplier=?, updated_at=datetime('now') WHERE id=1",
            ev,
        )
    await update.message.reply_text(f"✅ رویداد جهانی به «{ev[0]}» تغییر کرد.")


async def world_event_job(context: ContextTypes.DEFAULT_TYPE):
    """هر چند ساعت یک‌بار به‌صورت تصادفی یک رویداد جهانی جدید انتخاب می‌کنه."""
    ev = random.choice(EVENTS)
    with db() as conn:
        conn.execute(
            "UPDATE world_state SET event=?, description=?, pay_multiplier=?, updated_at=datetime('now') WHERE id=1",
            ev,
        )
    logger.info("World event changed to: %s", ev[0])


# ----------------------------------------------------------------------------
# ۸. سرگرمی‌ها
# ----------------------------------------------------------------------------

async def cmd_gym(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    cost = 1000
    if u["cash"] < cost:
        await update.message.reply_text("پول نقد کافی نداری (هزینه باشگاه: ۱۰۰۰ تومان).")
        return
    if u["energy"] < 15:
        await update.message.reply_text("انرژی کافی نداری.")
        return
    update_user(
        u["user_id"],
        cash=u["cash"] - cost,
        energy=clamp(u["energy"] - 15, 0, 100),
        health=clamp(u["health"] + 10, 0, 100),
        happiness=clamp(u["happiness"] + 5, 0, 100),
    )
    await update.message.reply_text("🏋️ تمرین کردی! سلامت و شادی بالا رفت.")


async def _minigame(update, u, energy_cost, skill, base_reward, label, emoji):
    if u["energy"] < energy_cost:
        await update.message.reply_text("انرژی کافی نداری.")
        return
    reward = int(base_reward * random.uniform(0.7, 1.4))
    update_user(
        u["user_id"],
        energy=clamp(u["energy"] - energy_cost, 0, 100),
        cash=u["cash"] + reward,
    )
    new_level, leveled = add_skill_xp(u["user_id"], skill, random.randint(5, 12))
    msg = f"{emoji} {label} انجام شد! +{fmt_money(reward)}"
    if leveled:
        msg += f"\n🎉 مهارت {SKILLS[skill]} به سطح {new_level} رسید!"
    await update.message.reply_text(msg)


async def cmd_fish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    await _minigame(update, u, 12, "farming", 1500, "ماهی‌گیری", "🎣")


async def cmd_mine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    await _minigame(update, u, 20, "business", 2500, "کار در معدن", "⛏")


async def cmd_farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    await _minigame(update, u, 15, "farming", 1800, "کشاورزی", "🌾")


async def cmd_restaurant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    cost = 3000
    if u["cash"] < cost:
        await update.message.reply_text(f"پول نقد کافی نداری (هزینه: {fmt_money(cost)}).")
        return
    update_user(
        u["user_id"],
        cash=u["cash"] - cost,
        hunger=clamp(u["hunger"] - 60, 0, 100),
        happiness=clamp(u["happiness"] + 15, 0, 100),
    )
    await update.message.reply_text("🍽 شام خوبی خوردی! گرسنگی و شادی به‌طرز چشمگیری بهتر شد.")


RIDDLES = [
    ("عددی که دو برابرش با ۱۰ برابر می‌شه ۸ عدد میشه، اون عدد چیه؟", "اشتباه در طراحی -  رد شو بعدی"),
    ("چه چیزی هر چقدر از آن برداری بزرگ‌تر می‌شود؟", "چاله"),
    ("چه چیزی بی‌آنکه نفس بکشد می‌میرد؟", "باتری"),
    ("کدام کلمه هر چه بیشتر از آن کم کنی بزرگ‌تر می‌شود؟", "کوتاه"),
]


async def cmd_puzzle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    q, _ = random.choice(RIDDLES)
    reward = random.randint(500, 1500)
    update_user(u["user_id"], cash=u["cash"] + reward, xp=u["xp"] + 5, intelligence=u["intelligence"] + 1)
    await update.message.reply_text(f"🧩 معما: {q}\n\n(فقط برای سرگرمی — جایزه‌ی مشارکت: {fmt_money(reward)} + XP هوش)")


# ----------------------------------------------------------------------------
# ۹. مشاور هوش مصنوعی (نیازمند GROQ_API_KEY)
# ----------------------------------------------------------------------------

async def cmd_advisor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not GROQ_API_KEY:
        await update.message.reply_text(
            "🤖 مشاور هوش مصنوعی فعال نیست.\n"
            "برای فعال‌سازی، متغیر محیطی GROQ_API_KEY رو با کلید رایگان خودت از "
            "console.groq.com ست کن و بات رو ری‌استارت کن."
        )
        return
    question = " ".join(context.args)
    if not question:
        await update.message.reply_text("استفاده: /advisor <سوالت درباره پول، شغل یا سرمایه‌گذاری داخل بازی>")
        return
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    try:
        import requests  # pip install requests

        nw = net_worth(u)
        prompt = (
            f"تو یک مشاور مالی/شغلی داخل یک بازی شبیه‌ساز زندگی تلگرامی هستی. "
            f"وضعیت کاربر: دارایی خالص {nw} تومان، پول نقد {u['cash']}، شغل {u['job']}.\n"
            f"سوال کاربر: {question}\n"
            "پاسخ کوتاه (حداکثر ۴-۵ خط)، دوستانه و عملی به فارسی بده."
        )
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        await update.message.reply_text(f"🤖 مشاور:\n{text}")
    except Exception as e:
        logger.exception("Advisor error")
        await update.message.reply_text(f"❌ خطا در ارتباط با مشاور هوش مصنوعی: {e}")


# ----------------------------------------------------------------------------
# ۱۰. درآمدزایی (VIP) — ساختار آماده، نیازمند Payment Provider Token واقعی
# ----------------------------------------------------------------------------

async def cmd_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💎 اشتراک VIP (به‌زودی):\n"
        "برای فعال‌سازی پرداخت واقعی، باید یک Payment Provider Token از طریق "
        "@BotFather → Payments تهیه کنی (مثل استرایپ یا یکی از درگاه‌های پشتیبانی‌شده). "
        "بعد از تهیه توکن، دستور /vip می‌تونه با استفاده از متد sendInvoice تلگرام "
        "فاکتور واقعی بفرسته. این بخش به‌عمد به‌صورت راهنما ساخته شده تا اطلاعات "
        "پرداخت ساختگی یا گمراه‌کننده نشون داده نشه."
    )


AVATAR_OPTIONS = ["🙂", "😎", "🤠", "🥷", "🦸", "🧙", "👑", "🐺", "🦊", "🐯"]


async def cmd_buyavatar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if not context.args or context.args[0] not in AVATAR_OPTIONS:
        await update.message.reply_text("انتخاب‌های موجود: " + " ".join(AVATAR_OPTIONS) + "\nاستفاده: /buyavatar <ایموجی>")
        return
    cost = 2000
    if u["cash"] < cost:
        await update.message.reply_text(f"پول نقد کافی نداری (هزینه: {fmt_money(cost)}).")
        return
    update_user(u["user_id"], cash=u["cash"] - cost, avatar=context.args[0])
    await update.message.reply_text(f"✅ آواتار تو به {context.args[0]} تغییر کرد.")


# ----------------------------------------------------------------------------
# ۱۱. امنیت و پنل مدیریت
# ----------------------------------------------------------------------------

async def cmd_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    lines = ["🔔 اعلان‌های شما:\n"]
    with db() as conn:
        proposals = conn.execute(
            "SELECT * FROM proposals WHERE target_id=? AND status='pending'", (u["user_id"],)
        ).fetchall()
    if proposals:
        for p in proposals:
            proposer = get_user(p["proposer_id"])
            name = proposer["username"] if proposer else str(p["proposer_id"])
            lines.append(f"💍 پیشنهاد ازدواج از {name} — با ریپلای روی پیامش /accept رو بزن.")
    if u["loan_amount"] > 0:
        lines.append(f"💳 بدهی وام فعال: {fmt_money(u['loan_amount'])} — /payloan برای پرداخت.")
    if is_jailed(u):
        lines.append("🚔 تو الان زندانی هستی. /bail برای آزادی زودتر.")
    if len(lines) == 1:
        lines.append("چیزی نداری.")
    await update.message.reply_text("\n".join(lines))




async def ban_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """این هندلر روی group=-1 (زودتر از بقیه) ثبت می‌شه تا کاربران بن‌شده رو متوقف کنه."""
    if not update.effective_user:
        return
    u = get_user(update.effective_user.id)
    if u and require_not_banned(u):
        if update.message:
            await update.message.reply_text("⛔️ حساب تو توسط مدیریت مسدود شده.")
        raise ApplicationHandlerStop


# ----------------------------------------------------------------------------
# ثبت هندلرها
# ----------------------------------------------------------------------------

def register_phase2(app):
    init_extra_db()

    # این هندلر با group=-1 زودتر از همه دستورات دیگه اجرا می‌شه تا کاربر بن‌شده
    # نتونه از هیچ دستوری (نه فقط دستورات فاز ۲) استفاده کنه.
    app.add_handler(MessageHandler(filters.ALL, ban_guard), group=-1)
    app.add_handler(MessageHandler(filters.ALL, inactive_group_guard), group=-2)
    app.add_handler(CallbackQueryHandler(inactive_group_guard), group=-2)

    handlers = [
        ("createcompany", cmd_createcompany),
        ("mycompany", cmd_mycompany),
        ("companyinvest", cmd_companyinvest),
        ("hire", cmd_hire),
        ("payroll", cmd_payroll),
        ("companiestop", cmd_companies_top),

        ("sell", cmd_sell),
        ("market", cmd_market),
        ("buyitem", cmd_buyitem),
        ("mylistings", cmd_mylistings),
        ("cancellisting", cmd_cancellisting),

        ("stocks", cmd_stocks),
        ("buystock", cmd_buystock),
        ("sellstock", cmd_sellstock),
        ("mystocks", cmd_mystocks),

        ("propose", cmd_propose),
        ("accept", cmd_accept),
        ("divorce", cmd_divorce),
        ("family", cmd_family),
        ("havechild", cmd_havechild),

        ("registercity", cmd_registercity),
        ("cityinfo", cmd_cityinfo),
        ("cityfund", cmd_cityfund),
        ("runformayor", cmd_runformayor),
        ("vote", cmd_vote),
        ("endelection", cmd_endelection),
        ("cityproject", cmd_cityproject),
        ("citytop", cmd_citytop),

        ("crime", cmd_crime),
        ("reportcrime", cmd_reportcrime),
        ("bail", cmd_bail),

        ("worldstatus", cmd_worldstatus),
        ("setevent", cmd_setevent),

        ("gym", cmd_gym),
        ("fish", cmd_fish),
        ("mine", cmd_mine),
        ("farm", cmd_farm),
        ("restaurant", cmd_restaurant),
        ("puzzle", cmd_puzzle),

        ("advisor", cmd_advisor),

        ("vip", cmd_vip),
        ("buyavatar", cmd_buyavatar),

        ("notifications", cmd_notifications),
    ]
    for name, fn in handlers:
        app.add_handler(CommandHandler(name, fn))

    if app.job_queue:
        app.job_queue.run_repeating(stock_drift_job, interval=900, first=900)       # هر ۱۵ دقیقه
        app.job_queue.run_repeating(world_event_job, interval=6 * 3600, first=3600)  # هر ۶ ساعت

    logger.info("Phase 2 handlers registered: %d commands", len(handlers))


# ==============================================================================
# فاز ۴ — آموزش، دوستی، بیمه، ارز دیجیتال/طلا، دادگاه، ماموریت‌های تازه
# ==============================================================================

EDU_LEVELS = [
    (0, "بدون تحصیلات", 0),
    (1, "دیپلم دبیرستان", 100),
    (2, "کاردانی", 300),
    (3, "لیسانس", 700),
    (4, "فوق‌لیسانس / دکترا", 1500),
]


def edu_level_for_xp(edu_xp: int) -> int:
    lvl = 0
    for level, _name, need in EDU_LEVELS:
        if edu_xp >= need:
            lvl = level
    return lvl


def edu_name(level: int) -> str:
    for l, name, _need in EDU_LEVELS:
        if l == level:
            return name
    return "نامشخص"


WEEKLY_MISSIONS = [
    {"key": "w_work_15", "desc": "۱۵ بار کار کن", "target": 15, "reward_cash": 20000, "reward_xp": 80},
    {"key": "w_train_10", "desc": "۱۰ بار مهارت تمرین کن", "target": 10, "reward_cash": 15000, "reward_xp": 90},
    {"key": "w_study_5", "desc": "۵ بار درس بخون", "target": 5, "reward_cash": 12000, "reward_xp": 60},
]

MONTHLY_MISSIONS = [
    {"key": "m_networth_up", "desc": "۳۰ بار کار کن", "target": 30, "reward_cash": 80000, "reward_xp": 300},
    {"key": "m_property", "desc": "یک ملک یا وسیله نقلیه بخر", "target": 1, "reward_cash": 50000, "reward_xp": 150},
]

SECRET_MISSIONS = [
    {"key": "s_millionaire", "desc": "🎁 مأموریت مخفی: دارایی خالص بالای ۱,۰۰۰,۰۰۰ تومان", "target": 1, "reward_cash": 100000, "reward_xp": 500},
]


def period_id_week():
    y, w, _ = datetime.utcnow().isocalendar()
    return f"week:{y}-W{w}"


def period_id_month():
    return f"month:{datetime.utcnow().strftime('%Y-%m')}"


def period_id_secret():
    return "secret"


def bump_periodic_mission(user_id, mission_key, period_id, amount=1):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM periodic_missions WHERE user_id=? AND mission_key=? AND period_id=?",
            (user_id, mission_key, period_id),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE periodic_missions SET progress=progress+? WHERE user_id=? AND mission_key=? AND period_id=?",
                (amount, user_id, mission_key, period_id),
            )
        else:
            conn.execute(
                "INSERT INTO periodic_missions (user_id, mission_key, period_id, progress) VALUES (?,?,?,?)",
                (user_id, mission_key, period_id, amount),
            )


def get_periodic_missions(user_id, definitions, period_id):
    with db() as conn:
        rows = {
            r["mission_key"]: dict(r)
            for r in conn.execute(
                "SELECT * FROM periodic_missions WHERE user_id=? AND period_id=?", (user_id, period_id)
            ).fetchall()
        }
    result = []
    for m in definitions:
        state = rows.get(m["key"], {"progress": 0, "claimed": 0})
        result.append({**m, "progress": state["progress"], "claimed": state["claimed"]})
    return result


def claim_periodic_mission(user_id, mission_key, period_id, definitions):
    m = next((x for x in definitions if x["key"] == mission_key), None)
    if not m:
        return None, "چنین ماموریتی وجود نداره."
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM periodic_missions WHERE user_id=? AND mission_key=? AND period_id=?",
            (user_id, mission_key, period_id),
        ).fetchone()
    if not row or row["progress"] < m["target"]:
        return None, "هنوز کامل نشده."
    if row["claimed"]:
        return None, "قبلاً دریافتش کردی."
    u = get_user(user_id)
    update_user(user_id, cash=u["cash"] + m["reward_cash"], xp=u["xp"] + m["reward_xp"])
    with db() as conn:
        conn.execute(
            "UPDATE periodic_missions SET claimed=1 WHERE user_id=? AND mission_key=? AND period_id=?",
            (user_id, mission_key, period_id),
        )
    return m, None


def init_phase4_db():
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS periodic_missions (
                user_id INTEGER,
                mission_key TEXT,
                period_id TEXT,
                progress INTEGER DEFAULT 0,
                claimed INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, mission_key, period_id)
            );
            CREATE TABLE IF NOT EXISTS court_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER,
                defendant_id INTEGER,
                outcome TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS force_join_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT,
                title TEXT,
                username TEXT,
                invite_link TEXT,
                added_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS menu_owners (
                chat_id INTEGER,
                message_id INTEGER,
                owner_id INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (chat_id, message_id)
            );
            CREATE TABLE IF NOT EXISTS gov_roles (
                user_id INTEGER PRIMARY KEY,
                role TEXT,
                assigned_by INTEGER,
                assigned_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS judicial_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                kind TEXT,
                reason TEXT,
                detail TEXT,
                issuer_id INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS court_summons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                judge_id INTEGER,
                scheduled_at TEXT,
                reason TEXT,
                status TEXT DEFAULT 'pending',
                verdict TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            """
        )
    # این ستون‌ها در init_db تعریف می‌شوند؛ اینجا هم باید برای دیتابیس‌های قدیمی
    # قبل از استفاده از ALTER TABLE در دسترس باشند.
    city_columns = [
        ("election_interval_hours", "INTEGER DEFAULT 240"),
        ("next_election_at", "REAL DEFAULT 0"),
        ("active", "INTEGER DEFAULT 0"),
    ]
    election_columns = [
        ("started_at", "REAL DEFAULT 0"),
        ("finished_at", "REAL DEFAULT 0"),
        ("automatic", "INTEGER DEFAULT 0"),
    ]
    extra_columns = [
        ("edu_level", "INTEGER DEFAULT 0"),
        ("edu_xp", "INTEGER DEFAULT 0"),
        ("insurance_until", "REAL DEFAULT 0"),
        ("card_number", "TEXT"),
        ("detention_until", "REAL DEFAULT 0"),
        ("prison_until", "REAL DEFAULT 0"),
        ("bank_frozen", "INTEGER DEFAULT 0"),
    ]
    with db() as conn:
        for col, decl in extra_columns:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {decl}")
            except Exception:
                pass  # ستون از قبل وجود داره
        for col, decl in city_columns:
            try:
                conn.execute(f"ALTER TABLE cities ADD COLUMN {col} {decl}")
            except Exception:
                pass
        for col, decl in election_columns:
            try:
                conn.execute(f"ALTER TABLE elections ADD COLUMN {col} {decl}")
            except Exception:
                pass
        try:
            conn.execute("ALTER TABLE stocks ADD COLUMN asset_type TEXT DEFAULT 'stock'")
        except Exception:
            pass
        default_crypto_gold = [
            ("BTS", "بیت‌کوین شهر", 900_000, "crypto"),
            ("ETC", "اتریوم شهر", 300_000, "crypto"),
            ("GLD", "طلای ۱۸ عیار (گرم)", 45_000, "gold"),
        ]
        for sym, name, price, atype in default_crypto_gold:
            conn.execute(
                "INSERT OR IGNORE INTO stocks (symbol, name, price, asset_type) VALUES (?,?,?,?)",
                (sym, name, price, atype),
            )
        rows = conn.execute("SELECT user_id FROM users WHERE card_number IS NULL OR card_number=''").fetchall()
        for r in rows:
            conn.execute("UPDATE users SET card_number=? WHERE user_id=?", (_generate_card_number(conn), r["user_id"]))
        for role, default_salary in (("police", 8000), ("soldier", 6000), ("captain", 12000), ("judge", 15000)):
            key = f"salary_{role}"
            existing = conn.execute("SELECT 1 FROM bot_settings WHERE key=?", (key,)).fetchone()
            if not existing:
                conn.execute("INSERT INTO bot_settings (key, value) VALUES (?,?)", (key, str(default_salary)))


def _generate_card_number(conn):
    while True:
        num = "6219" + "".join(str(random.randint(0, 9)) for _ in range(12))
        exists = conn.execute("SELECT 1 FROM users WHERE card_number=?", (num,)).fetchone()
        if not exists:
            return num


def format_card_number(num):
    if not num:
        return "—"
    return "-".join(num[i:i + 4] for i in range(0, len(num), 4))


def get_setting(key, default=None):
    with db() as conn:
        row = conn.execute("SELECT value FROM bot_settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with db() as conn:
        conn.execute(
            "INSERT INTO bot_settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def resolve_user_by_identifier(text):
    text = text.strip().lstrip("@")
    if text.isdigit():
        return get_user(int(text))
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (text,)).fetchone()
    return dict(row) if row else None


def get_force_join_list():
    with db() as conn:
        rows = conn.execute("SELECT * FROM force_join_channels ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_force_join_row(row_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM force_join_channels WHERE id=?", (row_id,)).fetchone()
    return dict(row) if row else None


def set_menu_owner(chat_id, message_id, owner_id):
    with db() as conn:
        conn.execute(
            "INSERT INTO menu_owners (chat_id, message_id, owner_id) VALUES (?,?,?) "
            "ON CONFLICT(chat_id, message_id) DO UPDATE SET owner_id=excluded.owner_id",
            (chat_id, message_id, owner_id),
        )


def get_loan_max_multiplier():
    val = get_setting("loan_max_multiplier")
    return int(val) if val and val.isdigit() else LOAN_MAX_MULTIPLIER


def get_menu_owner(chat_id, message_id):
    with db() as conn:
        row = conn.execute(
            "SELECT owner_id FROM menu_owners WHERE chat_id=? AND message_id=?", (chat_id, message_id)
        ).fetchone()
    return row["owner_id"] if row else None


# ----------------------------------------------------------------------------
# سیستم مقام‌ها و عدالت (پلیس، سرباز، سروان، قاضی)
# ----------------------------------------------------------------------------

GOV_ROLES = ["police", "soldier", "captain", "judge"]
ROLE_NAMES = {"police": "پلیس", "soldier": "سرباز", "captain": "سروان", "judge": "قاضی"}
ROLE_ICONS = {"police": "👮", "soldier": "🪖", "captain": "🎖️", "judge": "⚖️"}


def get_gov_role(user_id):
    with db() as conn:
        row = conn.execute("SELECT role FROM gov_roles WHERE user_id=?", (user_id,)).fetchone()
    return row["role"] if row else None


def get_job_label(u):
    """نمایش «شغل» کاربر: اگه مقام دولتی داره (پلیس/سرباز/سروان/قاضی) همون نشون داده می‌شه،
    وگرنه شغل عادیش از JOBS، وگرنه «بیکار»."""
    role = get_gov_role(u["user_id"])
    if role:
        return f"{ROLE_ICONS.get(role, '')} {ROLE_NAMES.get(role, role)}".strip()
    job = JOBS.get(u["job"])
    return job["name"] if job else "بیکار"


def set_gov_role(user_id, role, assigned_by):
    with db() as conn:
        conn.execute(
            "INSERT INTO gov_roles (user_id, role, assigned_by) VALUES (?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET role=excluded.role, assigned_by=excluded.assigned_by, "
            "assigned_at=datetime('now')",
            (user_id, role, assigned_by),
        )


def remove_gov_role(user_id):
    with db() as conn:
        conn.execute("DELETE FROM gov_roles WHERE user_id=?", (user_id,))


def list_gov_roles():
    with db() as conn:
        rows = conn.execute("SELECT * FROM gov_roles ORDER BY role").fetchall()
    return [dict(r) for r in rows]


def get_role_salary(role):
    val = get_setting(f"salary_{role}")
    return int(val) if val and val.isdigit() else 0


def set_role_salary(role, amount):
    set_setting(f"salary_{role}", str(amount))


def add_judicial_record(user_id, kind, reason, detail, issuer_id):
    with db() as conn:
        conn.execute(
            "INSERT INTO judicial_records (user_id, kind, reason, detail, issuer_id) VALUES (?,?,?,?,?)",
            (user_id, kind, reason, detail, issuer_id),
        )


def get_judicial_records(user_id, limit=20):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM judicial_records WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)
        ).fetchall()
    return [dict(r) for r in rows]


JUDICIAL_KIND_LABELS = {
    "arrest": "🚨 دستگیری",
    "summons": "📅 احضاریه دادگاه",
    "verdict": "⚖️ حکم دادگاه",
    "fine": "💸 جریمه نقدی",
    "detention": "🚔 بازداشت",
    "prison": "🔒 زندان",
    "release": "🔓 آزادی",
}


async def do_arrest(police_id, target_id, reason, duration_min, context):
    if police_id == target_id:
        return "❌ نمی‌تونی خودتو دستگیر کنی."
    target = get_user(target_id)
    if not target:
        return "❌ چنین کاربری پیدا نشد."
    until = time.time() + duration_min * 60
    update_user(target_id, detention_until=until)
    add_judicial_record(target_id, "arrest", reason, f"{duration_min} دقیقه", police_id)
    police = get_user(police_id)
    police_label = police.get("username") or police_id if police else police_id
    try:
        await context.bot.send_message(
            target_id,
            f"🚨 شما توسط پلیس دستگیر شدید و به بازداشتگاه منتقل شدید.\n"
            f"📄 دلیل: {reason}\n⏱ مدت بازداشت: {duration_min} دقیقه\n👮 دستگیرکننده: {police_label}",
        )
    except Exception:
        pass
    return f"✅ کاربر {target.get('username') or target_id} دستگیر و به بازداشتگاه منتقل شد."


async def do_release(target_id, which, issuer_id, context):
    target = get_user(target_id)
    if not target:
        return "❌ چنین کاربری پیدا نشد."
    if which == "detention":
        update_user(target_id, detention_until=0)
        label = "بازداشتگاه"
    else:
        update_user(target_id, prison_until=0)
        label = "زندان"
    add_judicial_record(target_id, "release", f"آزادی از {label}", "", issuer_id)
    try:
        await context.bot.send_message(target_id, f"🔓 شما از {label} آزاد شدید.")
    except Exception:
        pass
    return f"✅ کاربر {target.get('username') or target_id} از {label} آزاد شد."


async def do_court_summon(judge_id, target_id, scheduled_at, reason, context):
    target = get_user(target_id)
    if not target:
        return "❌ چنین کاربری پیدا نشد."
    with db() as conn:
        conn.execute(
            "INSERT INTO court_summons (user_id, judge_id, scheduled_at, reason) VALUES (?,?,?,?)",
            (target_id, judge_id, scheduled_at, reason),
        )
    add_judicial_record(target_id, "summons", reason, scheduled_at, judge_id)
    try:
        await context.bot.send_message(
            target_id,
            f"📩 احضاریه‌ی دادگاه\nشما به دادگاه احضار شدید.\n📅 زمان: {scheduled_at}\n📄 دلیل: {reason}",
        )
    except Exception:
        pass
    return f"✅ احضاریه برای {target.get('username') or target_id} صادر و ارسال شد."


VERDICT_TYPES = {
    "acquit": "✅ تبرئه",
    "fine": "💸 جریمه نقدی",
    "detention": "🚔 بازداشت",
    "prison": "🔒 زندان",
    "detention_fine": "🚔+💸 بازداشت + جریمه",
    "prison_fine": "🔒+💸 زندان + جریمه",
}


async def do_verdict(judge_id, target_id, verdict_type, fine_amount, duration_min, reason, context):
    target = get_user(target_id)
    if not target:
        return "❌ چنین کاربری پیدا نشد."
    judge = get_user(judge_id)
    judge_label = judge.get("username") or judge_id if judge else judge_id
    parts = [f"⚖️ حکم دادگاه\n📄 دلیل: {reason}\n👨‍⚖️ قاضی: {judge_label}\nحکم: {VERDICT_TYPES.get(verdict_type, verdict_type)}"]
    detail_bits = []

    if verdict_type in ("fine", "detention_fine", "prison_fine") and fine_amount:
        new_cash = max(0, target["cash"] - fine_amount)
        update_user(target_id, cash=new_cash)
        add_judicial_record(target_id, "fine", reason, fmt_money(fine_amount), judge_id)
        parts.append(f"💸 مبلغ جریمه: {fmt_money(fine_amount)}\nموجودی فعلی: {fmt_money(new_cash)}")
        detail_bits.append(f"جریمه {fmt_money(fine_amount)}")

    if verdict_type in ("detention", "detention_fine") and duration_min:
        until = time.time() + duration_min * 60
        update_user(target_id, detention_until=until)
        add_judicial_record(target_id, "detention", reason, f"{duration_min} دقیقه", judge_id)
        parts.append(f"🚔 مدت بازداشت: {duration_min} دقیقه")
        detail_bits.append(f"بازداشت {duration_min} دقیقه")

    if verdict_type in ("prison", "prison_fine") and duration_min:
        until = time.time() + duration_min * 60
        update_user(target_id, prison_until=until)
        add_judicial_record(target_id, "prison", reason, f"{duration_min} دقیقه", judge_id)
        parts.append(f"🔒 مدت زندان: {duration_min} دقیقه")
        detail_bits.append(f"زندان {duration_min} دقیقه")

    if verdict_type == "acquit":
        parts.append("✅ پرونده مختومه شد و کاربر تبرئه شد.")

    add_judicial_record(target_id, "verdict", reason, "؛ ".join(detail_bits) or "تبرئه", judge_id)
    with db() as conn:
        conn.execute(
            "UPDATE court_summons SET status='resolved', verdict=? WHERE user_id=? AND status='pending'",
            (verdict_type, target_id),
        )
    try:
        await context.bot.send_message(target_id, "\n".join(parts))
    except Exception:
        pass
    return f"✅ حکم برای {target.get('username') or target_id} صادر و اعلام شد."


async def judicial_release_job(context):
    now = time.time()
    with db() as conn:
        expired_detention = conn.execute(
            "SELECT user_id FROM users WHERE detention_until > 0 AND detention_until <= ?", (now,)
        ).fetchall()
        expired_prison = conn.execute(
            "SELECT user_id FROM users WHERE prison_until > 0 AND prison_until <= ?", (now,)
        ).fetchall()
    for r in expired_detention:
        update_user(r["user_id"], detention_until=0)
        add_judicial_record(r["user_id"], "release", "پایان مدت بازداشت", "", 0)
        try:
            await context.bot.send_message(r["user_id"], "🔓 مدت بازداشت شما تموم شد و آزاد شدید.")
        except Exception:
            pass
    for r in expired_prison:
        update_user(r["user_id"], prison_until=0)
        add_judicial_record(r["user_id"], "release", "پایان مدت زندان", "", 0)
        try:
            await context.bot.send_message(r["user_id"], "🔓 مدت زندان شما تموم شد و آزاد شدید.")
        except Exception:
            pass


async def pay_role_salaries(context, role_filter=None):
    roles = list_gov_roles()
    paid = []
    for r in roles:
        if role_filter and r["role"] != role_filter:
            continue
        salary = get_role_salary(r["role"])
        if salary <= 0:
            continue
        u = get_user(r["user_id"])
        if not u:
            continue
        update_user(r["user_id"], cash=u["cash"] + salary)
        paid.append((r["user_id"], salary))
        try:
            await context.bot.send_message(
                r["user_id"],
                f"💰 حقوق مقام {ROLE_ICONS.get(r['role'],'')} {ROLE_NAMES.get(r['role'], r['role'])} "
                f"واریز شد: {fmt_money(salary)}",
            )
        except Exception:
            pass
    return paid


def add_force_join_channel(chat_id, title, username, invite_link):
    with db() as conn:
        conn.execute(
            "INSERT INTO force_join_channels (chat_id, title, username, invite_link) VALUES (?,?,?,?)",
            (chat_id, title, username, invite_link),
        )


def remove_force_join_channel(row_id):
    with db() as conn:
        conn.execute("DELETE FROM force_join_channels WHERE id=?", (row_id,))


async def is_member_of_channel(context, chat_id, user_id):
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


async def resolve_and_validate_channel(context, identifier):
    identifier = identifier.strip()
    if identifier.lstrip("-").isdigit():
        chat_ref = int(identifier)
    else:
        chat_ref = identifier if identifier.startswith("@") else f"@{identifier.lstrip('@')}"
    try:
        chat = await context.bot.get_chat(chat_ref)
    except Exception:
        return None, "کانال یا گروه پیدا نشد. آیدی عددی یا یوزرنیم درست رو بفرست."
    try:
        me = await context.bot.get_me()
        member = await context.bot.get_chat_member(chat.id, me.id)
    except Exception:
        return None, "ربات به این کانال/گروه دسترسی نداره."
    if member.status not in ("administrator", "creator"):
        return None, "ربات باید عضو و ادمین اون کانال/گروه باشه. اول ربات رو اونجا اضافه و ادمین کن، بعد دوباره امتحان کن."
    invite_link = None
    if not chat.username:
        try:
            invite_link = await context.bot.export_chat_invite_link(chat.id)
        except Exception:
            invite_link = None
    return {
        "chat_id": str(chat.id),
        "title": chat.title or chat.username or str(chat.id),
        "username": chat.username or "",
        "invite_link": invite_link or "",
    }, None


async def enforce_force_join(update, context):
    user_id = update.effective_user.id
    if is_admin(user_id):
        return True
    channels = get_force_join_list()
    if not channels:
        return True
    missing = []
    for ch in channels:
        if not await is_member_of_channel(context, ch["chat_id"], user_id):
            missing.append(ch)
    if not missing:
        return True
    kb_rows = []
    for ch in missing:
        link = f"https://t.me/{ch['username']}" if ch.get("username") else ch.get("invite_link")
        if link:
            kb_rows.append([InlineKeyboardButton(f"📢 عضویت در {ch['title']}", url=link)])
    kb_rows.append([_btn("✅ عضو شدم", "checkjoin", style="success")])
    kb = InlineKeyboardMarkup(kb_rows)
    text = "برای استفاده از ربات باید اول عضو این کانال/گروه‌ها بشی، بعد دکمه‌ی «عضو شدم» رو بزن:\n\n" + "\n".join(
        f"• {ch['title']}" for ch in missing
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    return False


MAINTENANCE_KEY = "maintenance_mode"


async def enforce_maintenance(update, context):
    user_id = update.effective_user.id
    if is_admin(user_id):
        return True
    if get_setting(MAINTENANCE_KEY) != "1":
        return True
    text = "🔧 ربات از طرف مدیریت خاموش شده است."
    if update.callback_query:
        await update.callback_query.answer(text, show_alert=True)
    else:
        await update.message.reply_text(text)
    return False


# ---- آموزش: مدرسه / دانشگاه / درس خوندن / مدرک ----

async def cmd_addfriend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id, update.effective_user.username)
    if not update.message.reply_to_message:
        await update.message.reply_text("روی پیام فردی که می‌خوای دوستش بشی ریپلای کن و بنویس: (ریپلای) /addfriend")
        return
    target_tg = update.message.reply_to_message.from_user
    if target_tg.id == u["user_id"]:
        await update.message.reply_text("نمی‌تونی با خودت دوست بشی!")
        return
    ensure_user(target_tg.id, target_tg.username or target_tg.first_name)
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO friendships (user_id, friend_id) VALUES (?,?)", (u["user_id"], target_tg.id))
        conn.execute("INSERT OR IGNORE INTO friendships (user_id, friend_id) VALUES (?,?)", (target_tg.id, u["user_id"]))
    await update.message.reply_text(f"🤝 حالا با {target_tg.first_name} دوستی!")


INSURANCE_PRICE = 5000
INSURANCE_DAYS = 7
COURT_FEE = 3000


def register_phase4(app):
    init_phase4_db()
    handlers = [
        ("addfriend", cmd_addfriend),
    ]
    for name, fn in handlers:
        app.add_handler(CommandHandler(name, fn))
    logger.info("Phase 4 handlers registered: %d commands", len(handlers))


# ==============================================================================
# فاز ۳ — منوی کاملاً دکمه‌ای (Inline Keyboard)
# ==============================================================================

# -*- coding: utf-8 -*-


PRESET_AMOUNTS = [1000, 5000, 10000, 50000, 100000, 500000]
PRESET_QTYS = [1, 5, 10, 25, 50]


# ----------------------------------------------------------------------------
# ابزارهای کمکی مشترک
# ----------------------------------------------------------------------------

def _back(cb="m:main", label="⬅️ بازگشت"):
    return InlineKeyboardButton(label, callback_data=cb)


def _btn(text, callback_data, style=None):
    if style:
        try:
            return InlineKeyboardButton(text, callback_data=callback_data, style=style)
        except TypeError:
            pass
    return InlineKeyboardButton(text, callback_data=callback_data)


def _rows(buttons, cols=2):
    """لیست دکمه‌ها رو به ردیف‌های ۲تایی/۳تایی می‌شکونه."""
    return [buttons[i:i + cols] for i in range(0, len(buttons), cols)]


async def _answer(query, text, keyboard=None, parse_mode=None):
    """پنل را در همان پیام فعلی ویرایش می‌کند؛ برای کلیک‌های منو پیام جدید نمی‌سازد."""
    try:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=parse_mode)
    except Exception as first_error:
        # اگر فقط parse_mode مشکل داشت، باز هم همان پیام را ویرایش کن.
        if parse_mode:
            try:
                await query.edit_message_text(text, reply_markup=keyboard)
                return
            except Exception:
                pass
        logger.warning("Could not edit menu message; no new panel will be sent: %s", first_error)


def amount_keyboard(action, extra="", back_cb="m:main"):
    buttons = [
        _btn(f"{v:,}", f"amt:{action}:{extra}:{v}", style="primary")
        for v in PRESET_AMOUNTS
    ]
    rows = _rows(buttons, 3)
    rows.append([_btn("✏️ مبلغ دلخواه", f"amtcustom:{action}:{extra}", style="success")])
    rows.append([_back(back_cb)])
    return InlineKeyboardMarkup(rows)


def qty_keyboard(action, extra="", back_cb="m:main"):
    buttons = [
        _btn(str(v), f"qty:{action}:{extra}:{v}", style="primary")
        for v in PRESET_QTYS
    ]
    rows = _rows(buttons, 3)
    rows.append([_btn("✏️ تعداد دلخواه", f"qtycustom:{action}:{extra}", style="success")])
    rows.append([_back(back_cb)])
    return InlineKeyboardMarkup(rows)


# ----------------------------------------------------------------------------
# منوی اصلی
# ----------------------------------------------------------------------------

def main_menu_keyboard(user_id=None, is_private=True):
    """منوی اصلی فارسی بازی؛ commandها در پس‌زمینه حفظ می‌شوند اما مسیر کاربر دکمه‌ای است."""
    rows = [
        [_btn("👤 پروفایل من", "m:profile", style="primary"),
         _btn("💼 شغل و درآمد", "m:jobs", style="primary")],
        [_btn("🧠 مهارت‌ها", "m:skills", style="primary"),
         _btn("🎓 آموزش و مدرک", "m:school", style="primary")],
        [_btn("🏦 بانک و اعتبار", "m:bank", style="primary"),
         _btn("🛡 بیمه", "m:insurance", style="primary")],
        [_btn("🏠 خانه و دارایی", "m:shop", style="primary"),
         _btn("🛒 بازار آزاد", "m:market", style="primary")],
        [_btn("📈 بورس و سرمایه", "m:stocks", style="primary"),
         _btn("🏢 شرکت من", "m:company", style="primary")],
        [_btn("❤️ زندگی روزمره", "m:life", style="primary"),
         _btn("🎮 تفریح و سرگرمی", "m:fun", style="primary")],
        [_btn("👪 خانواده و روابط", "m:family", style="primary"),
         _btn("👥 دوستان", "m:friends", style="primary")],
        [_btn("🎯 ماموریت‌ها", "m:mission", style="primary"),
         _btn("🌟 ماموریت‌های ویژه", "m:missionshub", style="primary")],
        [_btn("🏆 رتبه‌بندی", "m:top", style="primary"),
         _btn("🌍 وضعیت جهان", "m:world", style="primary")],
        [_btn("🔔 اعلان‌ها", "m:notif", style="primary"),
         _btn("ℹ️ راهنمای بازی", "m:help", style="primary")],
    ]
    if not is_private:
        rows.insert(8, [_btn("🏙️ شهرداری و انتخابات", "m:city", style="success")])
    if user_id is not None:
        role = get_gov_role(user_id)
        if role:
            role_cb = {"police": "m:policepanel", "soldier": "m:soldierpanel",
                       "captain": "m:captainpanel", "judge": "m:judgepanel"}
            rows.append([_btn(f"{ROLE_ICONS[role]} پنل {ROLE_NAMES[role]}", role_cb[role], style="danger")])
    if user_id is not None and is_admin(user_id):
        rows.append([_btn("🛠️ داشبورد مدیریت", "m:adminpanel", style="danger")])
    return InlineKeyboardMarkup(rows)


async def show_main(update_or_query, u=None):
    text = "🌆 *پنل زندگی*\nاز اینجا مسیر زندگی، پول، روابط و شهرت رو مدیریت کن 👇"
    if hasattr(update_or_query, "edit_message_text"):
        query = update_or_query
        is_private = query.message.chat.type == "private" if query.message else True
        kb = main_menu_keyboard(query.from_user.id, is_private)
        await _answer(query, text, kb)
    else:
        update = update_or_query
        is_private = update.effective_chat.type == "private"
        kb = main_menu_keyboard(update.effective_user.id, is_private)
        await update.message.reply_text(text, reply_markup=kb)


# ----------------------------------------------------------------------------
# پروفایل
# ----------------------------------------------------------------------------

async def render_profile(query, user_id):
    u = ensure_user(user_id, query.from_user.username or query.from_user.first_name)
    nw = net_worth(u)
    idx, title = level_for_networth(nw)
    job_name = get_job_label(u)
    text = (
        f"{u['avatar']} *پروفایل*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"📝 بیو: _{md_escape(u['bio'])}_\n"
        f"🏅 رتبه: *{title}* (سطح {idx})\n"
        f"💼 شغل: *{job_name}*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "💰 *دارایی*\n"
        f"▫️ پول نقد: *{fmt_money(u['cash'])}*\n"
        f"▫️ بانک: *{fmt_money(u['bank'])}*\n"
        f"▫️ دارایی خالص: *{fmt_money(nw)}*\n"
    )
    if u["loan_amount"] > 0:
        text += f"▫️ بدهی وام: *{fmt_money(u['loan_amount'])}*\n"
    text += (
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "📊 *وضعیت شخصیت*\n"
        f"⚡ انرژی   {stat_bar(u['energy'])} {u['energy']}%\n"
        f"❤️ سلامت   {stat_bar(u['health'])} {u['health']}%\n"
        f"😊 شادی    {stat_bar(u['happiness'])} {u['happiness']}%\n"
        f"😰 استرس   {stat_bar(u['stress'])} {u['stress']}%\n"
        f"🍔 گرسنگی  {stat_bar(u['hunger'])} {u['hunger']}%\n"
        f"😴 خواب    {stat_bar(u['sleep'])} {u['sleep']}%\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🧠 هوش: *{u['intelligence']}*   ⭐ XP: *{u['xp']}*"
    )
    kb = InlineKeyboardMarkup([
        [_btn("🎒 دارایی‌های من", "m:myassets", style="primary")],
        [_back()],
    ])
    await _answer(query, text, kb, parse_mode="Markdown")


# ----------------------------------------------------------------------------
# شغل و کار
# ----------------------------------------------------------------------------

async def render_jobs(query, user_id):
    u = get_user(user_id)
    current = JOBS.get(u["job"])
    text = (
        "💼 *بازار کار*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"شغل فعلی: *{current['name'] if current else 'بیکار'}*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "برای کار کردن یا تغییر شغل یکی رو انتخاب کن:"
    )
    job_icons = {
        "worker": "🛠", "seller": "🛍", "driver": "🚗", "cook": "🍳",
        "teacher": "🧑‍🏫", "nurse": "🩺", "engineer": "⚙️", "developer": "💻",
        "doctor": "🩺", "manager": "📊", "investor": "💹",
    }
    buttons = []
    for key, j in JOBS.items():
        icon = job_icons.get(key, "💼")
        buttons.append(_btn(f"{icon} {j['name']} ({j['pay']:,})", f"jobapply:{key}", style="success"))
    rows = _rows(buttons, 2)
    if u["job"]:
        rows.insert(0, [_btn("🛠 کار کن (شیفت فعلی)", "dowork", style="success")])
    rows.append([_back()])
    await _answer(query, text, InlineKeyboardMarkup(rows), parse_mode="Markdown")


async def act_apply_job(query, user_id, key):
    job = JOBS.get(key)
    if not job:
        await query.answer("شغل نامعتبر", show_alert=True)
        return
    u = get_user(user_id)
    edu_min = JOB_EDU_MIN.get(key, 0)
    if edu_min > u.get("edu_level", 0):
        await query.answer(
            f"برای این شغل به مدرک «{edu_name(edu_min)}» نیاز داری (فعلی: {edu_name(u.get('edu_level', 0))}). با /study درس بخون.",
            show_alert=True,
        )
        return
    if job["skill"]:
        s = get_skill(user_id, job["skill"])
        if s["level"] < job["min_level"]:
            await query.answer(
                f"برای این شغل به سطح {job['min_level']} مهارت {SKILLS[job['skill']]} نیاز داری (فعلی: {s['level']})",
                show_alert=True,
            )
            return
    update_user(user_id, job=key)
    await query.answer(f"✅ شغل جدید: {job['name']}")
    await render_jobs(query, user_id)


async def act_work(query, user_id):
    u = get_user(user_id)
    if not u["job"]:
        await query.answer("اول باید یک شغل انتخاب کنی.", show_alert=True)
        return
    if is_jailed(u):
        await query.answer("🚔 تو زندانی هستی و نمی‌تونی کار کنی.", show_alert=True)
        return
    job = JOBS[u["job"]]
    now = time.time()
    elapsed_min = (now - u["last_work"]) / 60
    if elapsed_min < WORK_COOLDOWN_MIN:
        remain = int(WORK_COOLDOWN_MIN - elapsed_min)
        await query.answer(f"⏳ {remain} دقیقه دیگه صبر کن.", show_alert=True)
        return
    if u["energy"] < job["energy"]:
        await query.answer("⚡ انرژی کافی نداری.", show_alert=True)
        return

    import random
    skill_level = 1
    if job["skill"]:
        skill_level = get_skill(user_id, job["skill"])["level"]
    performance = random.uniform(0.9, 1.15) * (1 + 0.05 * (skill_level - 1))
    pay = int(job["pay"] * performance)
    new_energy = clamp(u["energy"] - job["energy"], 0, 100)
    new_stress = clamp(u["stress"] + job["stress"], 0, 100)
    new_hunger = clamp(u["hunger"] + 8, 0, 100)
    update_user(
        user_id, cash=u["cash"] + pay, energy=new_energy, stress=new_stress,
        hunger=new_hunger, xp=u["xp"] + job["xp"], last_work=now,
    )
    log_tx(user_id, "salary", pay, job["name"])
    bump_mission(user_id, "work_3")
    bump_periodic_mission(user_id, "w_work_15", period_id_week())
    bump_periodic_mission(user_id, "m_networth_up", period_id_month())
    note = ""
    if job["skill"]:
        new_level, leveled = add_skill_xp(user_id, job["skill"], job["xp"])
        if leveled:
            note = f" 🎉 مهارت به سطح {new_level} رسید!"
    await query.answer(f"💰 +{pay:,} تومان{note}")
    await render_jobs(query, user_id)


# ----------------------------------------------------------------------------
# مهارت‌ها
# ----------------------------------------------------------------------------

async def render_skills(query, user_id):
    lines = ["🧩 *مهارت‌های شما*", "_(برای تمرین رو دکمه‌ش بزن)_", "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"]
    skill_icons = {
        "programming": "💻", "medicine": "🩺", "management": "📊", "business": "💼",
        "driving": "🚗", "cooking": "🍳", "farming": "🌾", "art": "🎨", "investing": "💹",
    }
    buttons = []
    for key, name in SKILLS.items():
        s = get_skill(user_id, key)
        needed = s["level"] * 100
        bar = stat_bar(s["xp"], needed, length=8) if needed else "▰" * 8
        lines.append(f"▫️ {name} — سطح *{s['level']}*\n   {bar} {s['xp']}/{needed}")
        icon = skill_icons.get(key, "📚")
        buttons.append(_btn(f"{icon} {name}", f"train:{key}", style="primary"))
    rows = _rows(buttons, 2)
    rows.append([_back()])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(rows), parse_mode="Markdown")


async def act_train(query, user_id, skill):
    if skill not in SKILLS:
        await query.answer("مهارت نامعتبر", show_alert=True)
        return
    u = get_user(user_id)
    now = time.time()
    elapsed_min = (now - u["last_train"]) / 60
    if elapsed_min < TRAIN_COOLDOWN_MIN:
        remain = int(TRAIN_COOLDOWN_MIN - elapsed_min)
        await query.answer(f"⏳ {remain} دقیقه دیگه صبر کن.", show_alert=True)
        return
    if u["energy"] < 15:
        await query.answer("⚡ انرژی کافی نداری.", show_alert=True)
        return
    import random
    gained_xp = random.randint(8, 20) + u["intelligence"] // 5
    new_level, leveled = add_skill_xp(user_id, skill, gained_xp)
    update_user(user_id, energy=clamp(u["energy"] - 15, 0, 100), last_train=now, intelligence=u["intelligence"] + 1)
    bump_mission(user_id, "train_2")
    bump_periodic_mission(user_id, "w_train_10", period_id_week())
    msg = f"📚 +{gained_xp} XP"
    if leveled:
        msg += f" 🎉 سطح {new_level}!"
    await query.answer(msg)
    await render_skills(query, user_id)


# ----------------------------------------------------------------------------
# بانک
# ----------------------------------------------------------------------------

def credit_tier(score: int):
    if score >= 750:
        return "🥇 طلایی"
    if score >= 550:
        return "🥈 نقره‌ای"
    return "🥉 برنزی"


async def render_bank(query, user_id):
    u = get_user(user_id)
    max_loan = u["credit_score"] * get_loan_max_multiplier()
    frozen = u.get("bank_frozen", 0) == 1
    status_line = "🧊 مسدود" if frozen else "🟢 فعال"
    text = (
        "🏦 *بانک شهروندی*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "💳 *کارت بانکی*\n"
        f"`{format_card_number(u.get('card_number'))}`\n"
        f"وضعیت: {status_line}\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "💰 *موجودی‌ها*\n"
        f"▫️ پول نقد: *{fmt_money(u['cash'])}*\n"
        f"▫️ حساب بانکی: *{fmt_money(u['bank'])}*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "📊 *اعتبار*\n"
        f"{credit_tier(u['credit_score'])} — امتیاز {u['credit_score']}\n"
        f"▫️ بدهی وام: *{fmt_money(u['loan_amount'])}*\n"
        f"▫️ سقف وام: *{fmt_money(max_loan)}*"
    )
    kb = InlineKeyboardMarkup([
        [_btn("⬇️ واریز", "m:dep", style="success"), _btn("⬆️ برداشت", "m:with", style="primary")],
        [_btn("💳 دریافت وام", "m:loan", style="primary"), _btn("✅ بازپرداخت وام", "m:payl", style="success")],
        [_btn("🔄 انتقال با شماره کارت", "banktransfer:", style="success")],
        [_back()],
    ])
    await _answer(query, text, kb, parse_mode="Markdown")


FROZEN_MSG = "🧊 حساب بانکی شما مسدود شده و امکان انجام این عملیات نیست. برای پیگیری با مدیریت تماس بگیر."


async def do_deposit(user_id, amount):
    u = get_user(user_id)
    if u.get("bank_frozen", 0) == 1:
        return FROZEN_MSG
    if amount > u["cash"]:
        return "❌ پول نقد کافی نداری."
    update_user(user_id, cash=u["cash"] - amount, bank=u["bank"] + amount)
    return f"✅ {fmt_money(amount)} واریز شد."


async def do_card_transfer(sender_id, card_number, amount, context):
    if amount <= 0:
        return "مبلغ نامعتبره."
    sender = get_user(sender_id)
    if sender.get("bank_frozen", 0) == 1:
        return FROZEN_MSG
    if amount > sender["bank"]:
        return "❌ موجودی بانکی کافی نیست."
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE card_number=?", (card_number,)).fetchone()
    if not row:
        return "❌ همچین کارتی پیدا نشد."
    recipient = dict(row)
    if recipient["user_id"] == sender_id:
        return "نمی‌تونی به کارت خودت انتقال بدی!"
    if recipient.get("bank_frozen", 0) == 1:
        return "❌ حساب مقصد مسدوده و نمی‌تونه پول دریافت کنه."
    update_user(sender_id, bank=sender["bank"] - amount)
    new_recipient_bank = recipient["bank"] + amount
    update_user(recipient["user_id"], bank=new_recipient_bank)
    log_tx(sender_id, "transfer_out", -amount, f"به کارت {format_card_number(card_number)}")
    log_tx(recipient["user_id"], "transfer_in", amount, f"از کاربر {sender.get('username') or sender_id}")
    sender_name = sender.get("username") or sender_id
    try:
        await context.bot.send_message(
            recipient["user_id"],
            f"💳 مبلغ {fmt_money(amount)} از طرف {sender_name} به حسابتون واریز شد.\n"
            f"💰 موجودی بانکی فعلی: {fmt_money(new_recipient_bank)}",
        )
    except Exception:
        pass
    return f"✅ {fmt_money(amount)} به کارت {format_card_number(card_number)} منتقل شد."


async def do_withdraw(user_id, amount):
    u = get_user(user_id)
    if u.get("bank_frozen", 0) == 1:
        return FROZEN_MSG
    if amount > u["bank"]:
        return "❌ موجودی بانکی کافی نیست."
    update_user(user_id, cash=u["cash"] + amount, bank=u["bank"] - amount)
    return f"✅ {fmt_money(amount)} برداشت شد."


async def do_loan(user_id, amount):
    u = get_user(user_id)
    if u.get("bank_frozen", 0) == 1:
        return FROZEN_MSG
    max_loan = u["credit_score"] * get_loan_max_multiplier()
    if u["loan_amount"] + amount > max_loan:
        return f"❌ سقف وام تو {fmt_money(max_loan)} است."
    total_due = int(amount * (1 + LOAN_INTEREST))
    update_user(user_id, cash=u["cash"] + amount, loan_amount=u["loan_amount"] + total_due,
                      credit_score=max(300, u["credit_score"] - 15))
    return f"💰 وام {fmt_money(amount)} گرفتی. بدهی با سود: {fmt_money(total_due)}"


async def do_payloan(user_id, amount):
    u = get_user(user_id)
    if u.get("bank_frozen", 0) == 1:
        return FROZEN_MSG
    if amount > u["cash"]:
        return "❌ پول نقد کافی نداری."
    pay = min(amount, u["loan_amount"])
    update_user(user_id, cash=u["cash"] - pay, loan_amount=u["loan_amount"] - pay,
                      credit_score=min(900, u["credit_score"] + 10))
    return f"✅ {fmt_money(pay)} بازپرداخت شد."


# ----------------------------------------------------------------------------
# فروشگاه (املاک / وسایل نقلیه)
# ----------------------------------------------------------------------------

async def render_shop(query, user_id):
    kb = InlineKeyboardMarkup([
        [_btn("🏠 املاک", "m:shopprop", style="primary"),
         _btn("🚗 وسایل نقلیه", "m:shopveh", style="primary")],
        [_back()],
    ])
    text = "🏪 *فروشگاه شهر*\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\nیک دسته رو انتخاب کن:"
    await _answer(query, text, kb, parse_mode="Markdown")


async def render_shop_prop(query, user_id):
    prop_icons = {
        "land_small": "🟩", "apartment": "🏢", "house": "🏡", "shop": "🏪",
        "villa": "🏰", "factory": "🏭", "hotel": "🏨",
    }
    buttons = [
        _btn(f"{prop_icons.get(key, '🏠')} {p['name']} ({p['price']:,})", f"buyprop:{key}", style="success")
        for key, p in PROPERTIES.items()
    ]
    rows = _rows(buttons, 1)
    rows.append([_back("m:shop")])
    await _answer(query, "🏠 املاک موجود:", InlineKeyboardMarkup(rows))


async def render_shop_veh(query, user_id):
    veh_icons = {
        "bike": "🚲", "motorcycle": "🏍", "car": "🚗", "luxury_car": "🏎",
        "truck": "🚚", "boat": "🛥", "helicopter": "🚁", "airplane": "✈️",
    }
    buttons = [
        _btn(f"{veh_icons.get(key, '🚗')} {v['name']} ({v['price']:,})", f"buyveh:{key}", style="success")
        for key, v in VEHICLES.items()
    ]
    rows = _rows(buttons, 1)
    rows.append([_back("m:shop")])
    await _answer(query, "🚗 وسایل نقلیه موجود:", InlineKeyboardMarkup(rows))


async def act_buy_prop(query, user_id, key):
    prop = PROPERTIES.get(key)
    if not prop:
        await query.answer("نامعتبر", show_alert=True)
        return
    u = get_user(user_id)
    total = u["cash"] + u["bank"]
    if total < prop["price"]:
        await query.answer(f"❌ دارایی کافی نداری. قیمت: {prop['price']:,}", show_alert=True)
        return
    from_cash = min(u["cash"], prop["price"])
    from_bank = prop["price"] - from_cash
    with db() as conn:
        conn.execute("UPDATE users SET cash=cash-?, bank=bank-? WHERE user_id=?", (from_cash, from_bank, user_id))
        conn.execute("INSERT INTO user_properties (user_id, prop_key) VALUES (?,?)", (user_id, key))
    log_tx(user_id, "buy_property", -prop["price"], prop["name"])
    bump_periodic_mission(user_id, "m_property", period_id_month())
    await query.answer(f"🏠 {prop['name']} خریداری شد!")
    await render_shop_prop(query, user_id)


async def act_buy_veh(query, user_id, key):
    veh = VEHICLES.get(key)
    if not veh:
        await query.answer("نامعتبر", show_alert=True)
        return
    u = get_user(user_id)
    total = u["cash"] + u["bank"]
    if total < veh["price"]:
        await query.answer(f"❌ دارایی کافی نداری. قیمت: {veh['price']:,}", show_alert=True)
        return
    from_cash = min(u["cash"], veh["price"])
    from_bank = veh["price"] - from_cash
    with db() as conn:
        conn.execute(
            "UPDATE users SET cash=cash-?, bank=bank-?, happiness=MIN(100, happiness+?) WHERE user_id=?",
            (from_cash, from_bank, veh["happiness"], user_id),
        )
        conn.execute("INSERT INTO user_vehicles (user_id, veh_key) VALUES (?,?)", (user_id, key))
    log_tx(user_id, "buy_vehicle", -veh["price"], veh["name"])
    bump_periodic_mission(user_id, "m_property", period_id_month())
    await query.answer(f"🚗 {veh['name']} خریداری شد!")
    await render_shop_veh(query, user_id)


async def render_myassets(query, user_id):
    with db() as conn:
        props = conn.execute("SELECT prop_key FROM user_properties WHERE user_id=?", (user_id,)).fetchall()
        vehs = conn.execute("SELECT veh_key FROM user_vehicles WHERE user_id=?", (user_id,)).fetchall()
    lines = ["🏠 املاک شما:"]
    lines += [f"• {PROPERTIES[p['prop_key']]['name']}" for p in props if p["prop_key"] in PROPERTIES] or ["چیزی نداری."]
    lines.append("\n🚗 وسایل نقلیه شما:")
    lines += [f"• {VEHICLES[v['veh_key']]['name']}" for v in vehs if v["veh_key"] in VEHICLES] or ["چیزی نداری."]
    kb = InlineKeyboardMarkup([[_back("m:profile")]])
    await _answer(query, "\n".join(lines), kb)


# ----------------------------------------------------------------------------
# بازار آزاد (فاز ۲)
# ----------------------------------------------------------------------------

async def render_market(query, user_id):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM market_listings WHERE quantity > 0 ORDER BY created_at DESC LIMIT 15"
        ).fetchall()
    lines = ["🛒 آگهی‌های بازار آزاد:\n"]
    buttons = []
    for r in rows:
        lines.append(f"#{r['id']} {r['item_name']} ×{r['quantity']} — {r['price']:,}/عدد")
        buttons.append(_btn(f"🛍 خرید #{r['id']}", f"buyitem:{r['id']}", style="success"))
    if not rows:
        lines.append("بازار خالیه.")
    rows_kb = _rows(buttons, 2)
    rows_kb.append([_btn("📋 آگهی‌های من", "m:mylistings", style="primary")])
    rows_kb.append([_back()])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(rows_kb))


async def render_mylistings(query, user_id):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM market_listings WHERE seller_id=? AND quantity>0", (user_id,)
        ).fetchall()
    lines = ["📋 آگهی‌های شما:\n"]
    buttons = []
    for r in rows:
        lines.append(f"#{r['id']} {r['item_name']} ×{r['quantity']} — {r['price']:,}/عدد")
        buttons.append(_btn(f"❌ لغو #{r['id']}", f"cancellisting:{r['id']}", style="danger"))
    if not rows:
        lines.append("آگهی فعالی نداری.\n(برای ثبت آگهی جدید هنوز باید /sell <کالا> <تعداد> <قیمت> رو تایپ کنی چون نام کالا دلخواهه و دکمه‌پذیر نیست.)")
    rows_kb = _rows(buttons, 1)
    rows_kb.append([_back("m:market")])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(rows_kb))


async def act_buy_item(query, user_id, listing_id):
    with db() as conn:
        listing = conn.execute("SELECT * FROM market_listings WHERE id=?", (listing_id,)).fetchone()
    if not listing or listing["quantity"] <= 0:
        await query.answer("این آگهی موجودی نداره.", show_alert=True)
        return
    if listing["seller_id"] == user_id:
        await query.answer("نمی‌تونی از خودت بخری!", show_alert=True)
        return
    # همیشه ۱ عدد از دکمه سریع خریداری می‌شه؛ برای تعداد بیشتر دکمه‌ی تعداد نمایش داده می‌شه
    await _answer(
        query,
        f"چند عدد از «{listing['item_name']}» (موجودی {listing['quantity']}) می‌خوای بخری؟",
        qty_keyboard("buyitem", str(listing_id), back_cb="m:market"),
    )


async def do_buy_item(user_id, listing_id, qty):
    with db() as conn:
        listing = conn.execute("SELECT * FROM market_listings WHERE id=?", (listing_id,)).fetchone()
        if not listing or listing["quantity"] <= 0:
            return "این آگهی موجودی نداره."
        if listing["seller_id"] == user_id:
            return "نمی‌تونی از خودت بخری!"
        qty = min(qty, listing["quantity"])
        total = qty * listing["price"]
        cash_row = conn.execute("SELECT cash FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not cash_row or total > cash_row["cash"]:
            return f"پول نقد کافی نداری. لازم: {total:,}"
        conn.execute("UPDATE market_listings SET quantity=quantity-? WHERE id=?", (qty, listing_id))
        conn.execute("UPDATE users SET cash=cash-? WHERE user_id=?", (total, user_id))
        conn.execute("UPDATE users SET cash=cash+? WHERE user_id=?", (total, listing["seller_id"]))
    log_tx(user_id, "market_buy", -total, listing["item_name"])
    return f"✅ {qty} عدد {listing['item_name']} خریداری شد — {total:,} تومان."


async def act_cancel_listing(query, user_id, listing_id):
    with db() as conn:
        listing = conn.execute(
            "SELECT * FROM market_listings WHERE id=? AND seller_id=?", (listing_id, user_id)
        ).fetchone()
        if not listing:
            await query.answer("پیدا نشد.", show_alert=True)
            return
        conn.execute("UPDATE market_listings SET quantity=0 WHERE id=?", (listing_id,))
    await query.answer("لغو شد.")
    await render_mylistings(query, user_id)


# ----------------------------------------------------------------------------
# بورس (فاز ۲)
# ----------------------------------------------------------------------------

async def render_stocks(query, user_id):
    with db() as conn:
        rows = conn.execute("SELECT * FROM stocks").fetchall()
    lines = ["📈 بازار بورس:\n"]
    buttons = []
    for r in rows:
        lines.append(f"{r['symbol']} ({r['name']}) — {r['price']:,}")
        buttons.append(_btn(f"📊 {r['symbol']}", f"stocksym:{r['symbol']}", style="primary"))
    rows_kb = _rows(buttons, 3)
    rows_kb.append([_btn("💼 پرتفوی من", "m:mystocks", style="primary")])
    rows_kb.append([_back()])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(rows_kb))


async def render_stock_detail(query, user_id, symbol):
    with db() as conn:
        stock = conn.execute("SELECT * FROM stocks WHERE symbol=?", (symbol,)).fetchone()
        owned = conn.execute(
            "SELECT * FROM user_stocks WHERE user_id=? AND symbol=?", (user_id, symbol)
        ).fetchone()
    if not stock:
        await query.answer("نماد نامعتبر", show_alert=True)
        return
    owned_qty = owned["qty"] if owned else 0
    text = f"📈 {stock['name']} ({symbol})\nقیمت فعلی: {stock['price']:,}\nسهام شما: {owned_qty}"
    kb = InlineKeyboardMarkup([
        [_btn("خرید", f"m:stockbuy:{symbol}", style="success"),
         _btn("فروش", f"m:stocksell:{symbol}", style="danger")],
        [_back("m:stocks")],
    ])
    await _answer(query, text, kb)


async def do_stock_trade(user_id, symbol, qty, side):
    with db() as conn:
        stock = conn.execute("SELECT * FROM stocks WHERE symbol=?", (symbol,)).fetchone()
        if not stock:
            return "نماد نامعتبر."
        if side == "buy":
            total = qty * stock["price"]
            u_row = conn.execute("SELECT cash FROM users WHERE user_id=?", (user_id,)).fetchone()
            if total > u_row["cash"]:
                return f"پول نقد کافی نداری. لازم: {total:,}"
            new_price = int(stock["price"] * (1 + 0.01 * qty))
            conn.execute("UPDATE stocks SET price=? WHERE symbol=?", (new_price, symbol))
            existing = conn.execute(
                "SELECT * FROM user_stocks WHERE user_id=? AND symbol=?", (user_id, symbol)
            ).fetchone()
            if existing:
                conn.execute("UPDATE user_stocks SET qty=qty+? WHERE user_id=? AND symbol=?", (qty, user_id, symbol))
            else:
                conn.execute("INSERT INTO user_stocks (user_id, symbol, qty) VALUES (?,?,?)", (user_id, symbol, qty))
            conn.execute("UPDATE users SET cash=cash-? WHERE user_id=?", (total, user_id))
            result = f"✅ {qty} سهم {symbol} خریداری شد — {total:,} تومان.\n📈 قیمت جدید: {new_price:,}"
        else:
            owned = conn.execute(
                "SELECT * FROM user_stocks WHERE user_id=? AND symbol=?", (user_id, symbol)
            ).fetchone()
            if not owned or owned["qty"] < qty:
                return "این تعداد سهم رو نداری."
            total = qty * stock["price"]
            new_price = max(100, int(stock["price"] * (1 - 0.01 * qty)))
            conn.execute("UPDATE stocks SET price=? WHERE symbol=?", (new_price, symbol))
            conn.execute("UPDATE user_stocks SET qty=qty-? WHERE user_id=? AND symbol=?", (qty, user_id, symbol))
            conn.execute("UPDATE users SET cash=cash+? WHERE user_id=?", (total, user_id))
            result = f"✅ {qty} سهم {symbol} فروخته شد — {total:,} تومان.\n📉 قیمت جدید: {new_price:,}"
    # لاگ تراکنش بعد از بسته‌شدن (کامیت) تراکنش اصلی، تا دیتابیس قفل نگیره
    log_tx(user_id, "buy_stock" if side == "buy" else "sell_stock", -total if side == "buy" else total, symbol)
    return result


async def render_mystocks(query, user_id):
    with db() as conn:
        rows = conn.execute("SELECT * FROM user_stocks WHERE user_id=? AND qty>0", (user_id,)).fetchall()
    lines = ["💼 پرتفوی سهام شما:\n"]
    with db() as conn:
        for r in rows:
            stock = conn.execute("SELECT * FROM stocks WHERE symbol=?", (r["symbol"],)).fetchone()
            value = r["qty"] * stock["price"] if stock else 0
            lines.append(f"• {r['symbol']} × {r['qty']} — ارزش: {value:,}")
    if not rows:
        lines.append("سهامی نداری.")
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup([[_back("m:stocks")]]))


# ----------------------------------------------------------------------------
# شرکت من (فاز ۲) — ساخت شرکت هنوز نیاز به تایپ اسم داره (نام دلخواهه)
# ----------------------------------------------------------------------------

async def render_company(query, user_id):
    with db() as conn:
        c = conn.execute("SELECT * FROM companies WHERE owner_id=?", (user_id,)).fetchone()
    if not c:
        text = (
            "🏢 *شرکت من*\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "شرکتی نداری.\n"
            "برای ساخت شرکت باید نام دلخواهت رو تایپ کنی:\n"
            "`/createcompany <نام>`\n"
            "_(چون اسم شرکت کاملاً دلخواهه و قابل تبدیل به دکمه نیست)_"
        )
        await _answer(query, text, InlineKeyboardMarkup([[_back()]]), parse_mode="Markdown")
        return
    with db() as conn:
        employees = conn.execute("SELECT * FROM company_employees WHERE company_id=?", (c["id"],)).fetchall()
    text = (
        f"🏢 *{md_escape(c['name'])}*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"💰 سرمایه: *{fmt_money(c['capital'])}*\n"
        f"📈 سطح: *{c['level']}*\n"
        f"👥 کارمندان: *{len(employees)}* نفر"
    )
    kb = InlineKeyboardMarkup([
        [_btn("💰 افزایش سرمایه", "m:cinv", style="success")],
        [_btn("💵 پرداخت حقوق", "doact:payroll:", style="primary")],
        [_back()],
    ])
    await _answer(query, text, kb, parse_mode="Markdown")


async def do_companyinvest(user_id, amount):
    u = get_user(user_id)
    with db() as conn:
        c = conn.execute("SELECT * FROM companies WHERE owner_id=?", (user_id,)).fetchone()
        if not c:
            return "شرکتی نداری."
        if amount > u["cash"]:
            return "پول نقد کافی نداری."
        new_capital = c["capital"] + amount
        new_level = 1 + new_capital // 1_000_000
        conn.execute("UPDATE companies SET capital=?, level=? WHERE id=?", (new_capital, new_level, c["id"]))
    update_user(user_id, cash=u["cash"] - amount)
    return f"✅ {amount:,} به سرمایه شرکت اضافه شد."


async def do_payroll(user_id):
    with db() as conn:
        c = conn.execute("SELECT * FROM companies WHERE owner_id=?", (user_id,)).fetchone()
        if not c:
            return "شرکتی نداری."
        employees = conn.execute("SELECT * FROM company_employees WHERE company_id=?", (c["id"],)).fetchall()
        total = sum(e["salary"] for e in employees)
        if total > c["capital"]:
            return f"سرمایه کافی نیست. لازم: {total:,}"
        for e in employees:
            conn.execute("UPDATE users SET cash=cash+? WHERE user_id=?", (e["salary"], e["user_id"]))
        conn.execute("UPDATE companies SET capital=capital-? WHERE id=?", (total, c["id"]))
    return f"✅ حقوق {len(employees)} کارمند پرداخت شد ({total:,} تومان)."


async def do_study(user_id):
    u = get_user(user_id)
    jailed_msg = require_not_jailed(u)
    if jailed_msg:
        return jailed_msg
    if u["energy"] < 15:
        return "انرژی کافی نداری (حداقل ۱۵ لازمه). یکم بخواب."
    gained = random.randint(15, 30) + u.get("intelligence", 10) // 5
    new_xp = u.get("edu_xp", 0) + gained
    old_level = u.get("edu_level", 0)
    new_level = edu_level_for_xp(new_xp)
    update_user(
        user_id,
        edu_xp=new_xp,
        edu_level=new_level,
        energy=clamp(u["energy"] - 15, 0, 100),
        intelligence=u.get("intelligence", 10) + 1,
        xp=u["xp"] + 10,
    )
    bump_periodic_mission(user_id, "w_study_5", period_id_week())
    msg = f"📖 درس خوندی و {gained} امتیاز تحصیلی گرفتی. (مجموع: {new_xp})"
    if new_level > old_level:
        msg += f" 🎓 به مدرک «{edu_name(new_level)}» رسیدی!"
    return msg


async def do_buyinsurance(user_id):
    u = get_user(user_id)
    if u.get("insurance_until", 0) > time.time():
        return "بیمه‌ات همین الان هم فعاله."
    if u["cash"] < INSURANCE_PRICE:
        return f"پول نقد کافی نداری. قیمت بیمه: {fmt_money(INSURANCE_PRICE)}"
    until = time.time() + INSURANCE_DAYS * 86400
    update_user(user_id, cash=u["cash"] - INSURANCE_PRICE, insurance_until=until)
    log_tx(user_id, "insurance", -INSURANCE_PRICE, f"{INSURANCE_DAYS} روز")
    return f"🛡 بیمه‌ی {INSURANCE_DAYS} روزه فعال شد! جریمه و زندان دزدی برات نصف می‌شه."


async def do_court(user_id, report_id):
    u = get_user(user_id)
    with db() as conn:
        report = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
    if not report:
        return "چنین گزارشی وجود نداره."
    if report["target_id"] != u["user_id"]:
        return "این گزارش علیه تو نیست."
    if report["reviewed"]:
        return "این گزارش قبلاً بررسی شده."
    if u["cash"] < COURT_FEE:
        return f"پول نقد کافی برای هزینه‌ی دادخواهی نداری ({fmt_money(COURT_FEE)})."
    update_user(u["user_id"], cash=u["cash"] - COURT_FEE)
    win_chance = clamp(0.3 + (u["credit_score"] - 500) / 1000, 0.1, 0.8)
    won = random.random() < win_chance
    with db() as conn:
        conn.execute("UPDATE reports SET reviewed=1 WHERE id=?", (report_id,))
        conn.execute(
            "INSERT INTO court_cases (report_id, defendant_id, outcome) VALUES (?,?,?)",
            (report_id, u["user_id"], "won" if won else "lost"),
        )
    if won:
        update_user(u["user_id"], credit_score=clamp(u["credit_score"] + 15, 300, 900))
        reporter = get_user(report["reporter_id"])
        if reporter:
            update_user(reporter["user_id"], credit_score=clamp(reporter["credit_score"] - 20, 300, 900))
        return "⚖️ دادگاه به نفعت رأی داد! گزارش رد شد و اعتبارت بالا رفت."
    fine = 4000
    update_user(u["user_id"], cash=max(0, u["cash"] - fine), credit_score=clamp(u["credit_score"] - 25, 300, 900))
    return f"⚖️ دادگاه علیه‌ت رأی داد. {fmt_money(fine)} جریمه شدی."


async def do_unfriend(user_id, friend_id):
    with db() as conn:
        conn.execute("DELETE FROM friendships WHERE user_id=? AND friend_id=?", (user_id, friend_id))
        conn.execute("DELETE FROM friendships WHERE user_id=? AND friend_id=?", (friend_id, user_id))
    return "دوستی حذف شد."


# ----------------------------------------------------------------------------
# زندگی روزمره
# ----------------------------------------------------------------------------

async def render_life(query, user_id):
    kb = InlineKeyboardMarkup([
        [_btn("😴 خواب", "doact:sleep:", style="primary"), _btn("🍔 غذا", "doact:eat:", style="primary")],
        [_btn("🏋️ باشگاه", "doact:gym:", style="primary"), _btn("🍽 رستوران", "doact:restaurant:", style="primary")],
        [_back()],
    ])
    text = "❤️ *زندگی روزمره*\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\nیکی رو انتخاب کن:"
    await _answer(query, text, kb, parse_mode="Markdown")


async def do_sleep(user_id):
    u = get_user(user_id)
    now = time.time()
    elapsed_min = (now - u["last_sleep"]) / 60
    if elapsed_min < SLEEP_COOLDOWN_MIN:
        remain = int(SLEEP_COOLDOWN_MIN - elapsed_min)
        return f"⏳ هنوز خسته نیستی، {remain} دقیقه دیگه صبر کن."
    update_user(user_id, energy=100, sleep=100, stress=clamp(u["stress"] - 30, 0, 100), last_sleep=now)
    bump_mission(user_id, "sleep_1")
    return "😴 خوب خوابیدی! انرژی و خواب کامل شد."


async def do_eat(user_id):
    u = get_user(user_id)
    cost = 500
    if u["cash"] < cost:
        return "💸 پول نقد کافی نداری."
    update_user(user_id, cash=u["cash"] - cost, hunger=clamp(u["hunger"] - 40, 0, 100),
                      happiness=clamp(u["happiness"] + 5, 0, 100))
    log_tx(user_id, "food", -cost, "غذا")
    bump_mission(user_id, "eat_2")
    return "🍔 غذا خوردی."


async def do_gym(user_id):
    u = get_user(user_id)
    cost = 1000
    if u["cash"] < cost:
        return "پول نقد کافی نداری."
    if u["energy"] < 15:
        return "انرژی کافی نداری."
    update_user(user_id, cash=u["cash"] - cost, energy=clamp(u["energy"] - 15, 0, 100),
                      health=clamp(u["health"] + 10, 0, 100), happiness=clamp(u["happiness"] + 5, 0, 100))
    return "🏋️ تمرین کردی! سلامت و شادی بالا رفت."


async def do_restaurant(user_id):
    u = get_user(user_id)
    cost = 3000
    if u["cash"] < cost:
        return f"پول نقد کافی نداری (هزینه: {cost:,})."
    update_user(user_id, cash=u["cash"] - cost, hunger=clamp(u["hunger"] - 60, 0, 100),
                      happiness=clamp(u["happiness"] + 15, 0, 100))
    return "🍽 شام خوبی خوردی!"


# ----------------------------------------------------------------------------
# سرگرمی
# ----------------------------------------------------------------------------

async def render_fun(query, user_id):
    kb = InlineKeyboardMarkup([
        [_btn("🎣 ماهی‌گیری", "doact:fish:", style="primary"), _btn("⛏ معدن", "doact:mine:", style="primary")],
        [_btn("🌾 کشاورزی", "doact:farm:", style="primary"), _btn("🧩 معما", "doact:puzzle:", style="primary")],
        [_back()],
    ])
    text = "🎮 *سرگرمی*\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\nیکی رو انتخاب کن:"
    await _answer(query, text, kb, parse_mode="Markdown")


async def _minigame(user_id, energy_cost, skill, base_reward, label, emoji):
    import random
    u = get_user(user_id)
    if u["energy"] < energy_cost:
        return "انرژی کافی نداری."
    reward = int(base_reward * random.uniform(0.7, 1.4))
    update_user(user_id, energy=clamp(u["energy"] - energy_cost, 0, 100), cash=u["cash"] + reward)
    new_level, leveled = add_skill_xp(user_id, skill, random.randint(5, 12))
    msg = f"{emoji} {label} انجام شد! +{reward:,}"
    if leveled:
        msg += f" 🎉 سطح {new_level}!"
    return msg


async def do_fish(user_id):
    return await _minigame(user_id, 12, "farming", 1500, "ماهی‌گیری", "🎣")


async def do_mine(user_id):
    return await _minigame(user_id, 20, "business", 2500, "معدن", "⛏")


async def do_farm(user_id):
    return await _minigame(user_id, 15, "farming", 1800, "کشاورزی", "🌾")


async def do_puzzle(user_id):
    import random
    u = get_user(user_id)
    reward = random.randint(500, 1500)
    q, _ = random.choice(RIDDLES)
    update_user(user_id, cash=u["cash"] + reward, xp=u["xp"] + 5, intelligence=u["intelligence"] + 1)
    return f"🧩 {q}\n\n+{reward:,} تومان و XP هوش"


# ----------------------------------------------------------------------------
# ماموریت‌ها
# ----------------------------------------------------------------------------

async def render_mission(query, user_id):
    missions = get_missions_today(user_id)
    lines = ["🎯 *ماموریت‌های امروز*", "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"]
    buttons = []
    for m in missions:
        status = "✅ کامل" if m["progress"] >= m["target"] else f"{m['progress']}/{m['target']}"
        claimed = " _(گرفته شد)_" if m["claimed"] else ""
        lines.append(f"▫️ {m['desc']} — *{status}*{claimed}")
        if m["progress"] >= m["target"] and not m["claimed"]:
            buttons.append(_btn(f"🎁 دریافت: {m['desc'][:15]}", f"claim:{m['key']}", style="success"))
    rows = _rows(buttons, 1)
    rows.append([_back()])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(rows), parse_mode="Markdown")


async def act_claim(query, user_id, key):
    mission_def = next((m for m in DAILY_MISSIONS if m["key"] == key), None)
    if not mission_def:
        await query.answer("نامعتبر", show_alert=True)
        return
    day = today_str()
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM daily_missions WHERE user_id=? AND mission_key=? AND day=?", (user_id, key, day)
        ).fetchone()
    progress = row["progress"] if row else 0
    claimed = row["claimed"] if row else 0
    if claimed or progress < mission_def["target"]:
        await query.answer("هنوز آماده نیست.", show_alert=True)
        return
    with db() as conn:
        conn.execute(
            "UPDATE daily_missions SET claimed=1 WHERE user_id=? AND mission_key=? AND day=?", (user_id, key, day)
        )
    u = get_user(user_id)
    update_user(user_id, cash=u["cash"] + mission_def["reward_cash"], xp=u["xp"] + mission_def["reward_xp"])
    await query.answer(f"🎉 +{mission_def['reward_cash']:,} تومان")
    await render_mission(query, user_id)


# ----------------------------------------------------------------------------
# خانواده
# ----------------------------------------------------------------------------

async def render_family(query, user_id):
    with db() as conn:
        fam = conn.execute("SELECT * FROM families WHERE user_id=?", (user_id,)).fetchone()
    if not fam or not fam["spouse_id"]:
        text = (
            "👪 *خانواده*\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "تو الان مجرد هستی.\n"
            "برای خواستگاری باید روی پیام فرد موردنظر توی گروه Reply بزنی و بنویسی `/propose`\n"
            "_(چون انتخاب یک نفر مشخص از بین اعضا با دکمه ممکن نیست)_"
        )
        await _answer(query, text, InlineKeyboardMarkup([[_back()]]), parse_mode="Markdown")
        return
    spouse = get_user(fam["spouse_id"])
    spouse_name = spouse["username"] if spouse else str(fam["spouse_id"])
    text = (
        "👪 *خانواده*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👨‍👩‍👧 همسر: *{md_escape(spouse_name)}*\n"
        f"👶 فرزندان: *{fam['children']}*"
    )
    kb = InlineKeyboardMarkup([
        [_btn("👶 بچه‌دار شوید (۱۰۰,۰۰۰)", "doact:havechild:", style="success")],
        [_btn("💔 طلاق", "confirm:divorce:", style="danger")],
        [_back()],
    ])
    await _answer(query, text, kb, parse_mode="Markdown")


async def do_havechild(user_id):
    with db() as conn:
        fam = conn.execute("SELECT * FROM families WHERE user_id=?", (user_id,)).fetchone()
        if not fam or not fam["spouse_id"]:
            return "اول باید ازدواج کنی."
        u_row = conn.execute("SELECT cash, happiness FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not u_row or u_row["cash"] < CHILD_COST:
            return f"پول نقد کافی نداری (هزینه: {CHILD_COST:,})."
        conn.execute("UPDATE families SET children=children+1 WHERE user_id=?", (user_id,))
        conn.execute("UPDATE families SET children=children+1 WHERE user_id=?", (fam["spouse_id"],))
        new_happiness = clamp(u_row["happiness"] + 15, 0, 100)
        conn.execute(
            "UPDATE users SET cash=cash-?, happiness=? WHERE user_id=?",
            (CHILD_COST, new_happiness, user_id),
        )
    return "👶 تبریک! صاحب فرزند شدید."


async def do_divorce(user_id):
    with db() as conn:
        fam = conn.execute("SELECT * FROM families WHERE user_id=?", (user_id,)).fetchone()
        if not fam or not fam["spouse_id"]:
            return "الان متأهل نیستی."
        spouse_id = fam["spouse_id"]
        conn.execute("UPDATE families SET spouse_id=NULL WHERE user_id=?", (user_id,))
        conn.execute("UPDATE families SET spouse_id=NULL WHERE user_id=?", (spouse_id,))
    u = get_user(user_id)
    update_user(user_id, married_to=None, happiness=clamp(u["happiness"] - 20, 0, 100))
    update_user(spouse_id, married_to=None)
    return "💔 طلاق ثبت شد."


# ----------------------------------------------------------------------------
# رتبه‌بندی / وضعیت جهانی / اعلان‌ها / راهنما
# ----------------------------------------------------------------------------

async def render_top(query, user_id):
    with db() as conn:
        rows = conn.execute("SELECT * FROM users").fetchall()
    users = [dict(r) for r in rows]
    ranked = sorted(users, key=lambda u: net_worth(u), reverse=True)[:10]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = ["🏆 *ثروتمندترین شهروندان*", "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"]
    for i, u in enumerate(ranked, 1):
        name = md_escape(u["username"] or f"کاربر {u['user_id']}")
        rank = medals.get(i, f"{i}.")
        lines.append(f"{rank} {name} — *{fmt_money(net_worth(u))}*")
    kb_rows = [[_back()]]
    kb_rows.insert(0, [_btn("🏢 برترین شرکت‌ها", "m:companiestop", style="primary"),
                       _btn("🏙 برترین شهرها", "m:citytop", style="primary")])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(kb_rows), parse_mode="Markdown")


async def render_companiestop(query, user_id):
    with db() as conn:
        rows = conn.execute("SELECT * FROM companies ORDER BY capital DESC LIMIT 10").fetchall()
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = ["🏆 *بزرگ‌ترین شرکت‌ها*", "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"]
    for i, c in enumerate(rows, 1):
        rank = medals.get(i, f"{i}.")
        lines.append(f"{rank} {md_escape(c['name'])} — *{fmt_money(c['capital'])}*")
    if not rows:
        lines.append("هنوز شرکتی نیست.")
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup([[_back("m:top")]]), parse_mode="Markdown")


async def render_citytop(query, user_id):
    with db() as conn:
        rows = conn.execute("SELECT * FROM cities ORDER BY score DESC LIMIT 10").fetchall()
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = ["🏆 *برترین شهرها*", "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"]
    for i, c in enumerate(rows, 1):
        rank = medals.get(i, f"{i}.")
        lines.append(f"{rank} {md_escape(c['name'])} — امتیاز *{c['score']}*")
    if not rows:
        lines.append("هنوز شهری نیست.")
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup([[_back("m:top")]]), parse_mode="Markdown")


async def render_world(query, user_id):
    with db() as conn:
        state = conn.execute("SELECT * FROM world_state WHERE id=1").fetchone()
    text = (
        "🌍 *وضعیت جهانی*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"{md_escape(state['description'])}\n"
        f"📊 ضریب تاثیر بر حقوق: *×{state['pay_multiplier']}*"
    )
    await _answer(query, text, InlineKeyboardMarkup([[_back()]]), parse_mode="Markdown")


async def render_notif(query, user_id):
    u = get_user(user_id)
    lines = ["🔔 *اعلان‌های شما*", "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"]
    with db() as conn:
        proposals = conn.execute(
            "SELECT * FROM proposals WHERE target_id=? AND status='pending'", (user_id,)
        ).fetchall()
    for p in proposals:
        proposer = get_user(p["proposer_id"])
        name = md_escape(proposer["username"] if proposer else str(p["proposer_id"]))
        lines.append(f"💍 پیشنهاد ازدواج از *{name}* — روی پیامش Reply بزن و بنویس `/accept`")
    if u["loan_amount"] > 0:
        lines.append(f"💳 بدهی وام: *{fmt_money(u['loan_amount'])}*")
    if is_jailed(u):
        lines.append("🚔 الان زندانی هستی.")
    if len(lines) == 2:
        lines.append("چیزی نداری. ✨")
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup([[_back()]]), parse_mode="Markdown")


async def render_school(query, user_id):
    u = get_user(user_id)
    lvl = u.get("edu_level", 0)
    xp = u.get("edu_xp", 0)
    nxt = lvl + 1 if lvl < EDU_LEVELS[-1][0] else None
    lines = [f"🎓 مدرک فعلی: {edu_name(lvl)} ({xp} امتیاز تحصیلی)"]
    if nxt is not None:
        remain = max(0, EDU_LEVELS[nxt][2] - xp)
        lines.append(f"برای رسیدن به «{edu_name(nxt)}» {remain} امتیاز دیگه لازمه.")
    else:
        lines.append("به بالاترین مدرک تحصیلی رسیدی!")
    lines.append("\nمشاغلی که به مدرک نیاز دارن:")
    for k, v in JOB_EDU_MIN.items():
        lines.append(f"• {JOBS[k]['name']} ← {edu_name(v)}")
    kb = InlineKeyboardMarkup([[_btn("📖 درس بخون", "doact:study:", style="success")], [_back()]])
    await _answer(query, "\n".join(lines), kb)


async def render_insurance(query, user_id):
    u = get_user(user_id)
    active = u.get("insurance_until", 0) > time.time()
    if active:
        remain_days = int((u["insurance_until"] - time.time()) / 86400) + 1
        text = f"🛡 بیمه‌ات فعاله و {remain_days} روز دیگه اعتبار داره."
        kb = InlineKeyboardMarkup([[_back()]])
    else:
        text = (
            f"بیمه نداری.\nقیمت: {fmt_money(INSURANCE_PRICE)} برای {INSURANCE_DAYS} روز.\n"
            "با بیمه، جریمه و زندان دزدی برات نصف می‌شه."
        )
        kb = InlineKeyboardMarkup([[_btn("🛡 خرید بیمه", "doact:buyinsurance:", style="success")], [_back()]])
    await _answer(query, text, kb)


async def render_friends(query, user_id):
    with db() as conn:
        rows = conn.execute("SELECT friend_id FROM friendships WHERE user_id=?", (user_id,)).fetchall()
    lines = ["👥 لیست دوستان:\n"]
    buttons = []
    if not rows:
        lines.append("هنوز دوستی نداری.")
    for r in rows:
        fu = get_user(r["friend_id"])
        if fu:
            lines.append(f"• {fu.get('username') or fu['user_id']}")
            buttons.append([_btn(f"❌ حذف {fu.get('username') or fu['user_id']}", f"unfriend:{fu['user_id']}", style="danger")])
    lines.append("\nبرای افزودن دوست، روی پیام فرد ریپلای کن و بنویس: /addfriend")
    buttons.append([_back()])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(buttons))


async def render_court(query, user_id):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM reports WHERE target_id=? AND reviewed=0 ORDER BY id DESC LIMIT 10", (user_id,)
        ).fetchall()
    lines = [f"⚖️ دادگاه (هزینه‌ی هر دادخواهی: {fmt_money(COURT_FEE)})\n"]
    buttons = []
    if not rows:
        lines.append("هیچ گزارش بازی علیه‌ت وجود نداره.")
    for r in rows:
        lines.append(f"#{r['id']} — دلیل: {r['reason']}")
        buttons.append([_btn(f"⚖️ دادخواهی #{r['id']}", f"court:{r['id']}", style="primary")])
    buttons.append([_back()])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(buttons))


async def render_missionshub(query, user_id):
    kb = InlineKeyboardMarkup([
        [_btn("🗓 هفتگی", "m:weeklym", style="primary"), _btn("📅 ماهانه", "m:monthlym", style="primary")],
        [_btn("🕵️ مخفی", "m:secretm", style="primary")],
        [_back()],
    ])
    await _answer(query, "🎯 ماموریت‌های ویژه — یکی رو انتخاب کن:", kb)


async def _render_periodic_missions(query, user_id, title, definitions, period_id, period_key):
    missions = get_periodic_missions(user_id, definitions, period_id)
    lines = [f"{title}\n"]
    buttons = []
    for m in missions:
        progress = min(m["progress"], m["target"])
        if m["claimed"]:
            lines.append(f"• {m['desc']} — {progress}/{m['target']} ✅")
        elif progress >= m["target"]:
            lines.append(f"• {m['desc']} — {progress}/{m['target']} 🎁")
            buttons.append([_btn(f"🎁 دریافت: {m['desc'][:20]}", f"claimp:{period_key}:{m['key']}", style="success")])
        else:
            lines.append(f"• {m['desc']} — {progress}/{m['target']}")
    buttons.append([_back("m:missionshub")])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(buttons))


async def render_weeklym(query, user_id):
    await _render_periodic_missions(query, user_id, "🗓 ماموریت‌های هفتگی:", WEEKLY_MISSIONS, period_id_week(), "weekly")


async def render_monthlym(query, user_id):
    await _render_periodic_missions(query, user_id, "📅 ماموریت‌های ماهانه:", MONTHLY_MISSIONS, period_id_month(), "monthly")


async def render_secretm(query, user_id):
    u = get_user(user_id)
    if net_worth(u) >= 1_000_000:
        current = get_periodic_missions(user_id, SECRET_MISSIONS, period_id_secret())
        s_mission = next((m for m in current if m["key"] == "s_millionaire"), None)
        if s_mission and s_mission["progress"] < s_mission["target"]:
            bump_periodic_mission(user_id, "s_millionaire", period_id_secret(), amount=s_mission["target"])
    await _render_periodic_missions(query, user_id, "🕵️ ماموریت‌های مخفی:", SECRET_MISSIONS, period_id_secret(), "secret")


async def render_help(query, user_id):
    text = (
        "ℹ️ *راهنمای داخل بازی*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "🧭 *از کجا شروع کنم؟*\n"
        "از «شغل و درآمد» یک مسیر کاری انتخاب کن، از «مهارت‌ها» پیشرفت کن و وضعیت\n"
        "انرژی، گرسنگی، خواب و شادی رو در «زندگی روزمره» مدیریت کن.\n\n"
        "🏦 *اقتصاد:* بانک، وام، بورس، بازار، ملک و شرکت روی دارایی خالصت اثر دارن.\n"
        "👥 *اجتماعی:* دوستی، ازدواج و خانواده مسیرهای جداگانه‌ای برای رشد دارن.\n"
        "🏙️ *شهرداری:* داخل گروه، از منوی «شهرداری و انتخابات» شهر رو فعال کن،\n"
        "انتخابات رو شروع کن، نامزد شو و به نامزد موردنظرت رأی بده.\n\n"
        "⌨️ *نکته:* commandهای قدیمی هنوز وجود دارن، ولی برای تجربه‌ی اصلی بازی\n"
        "لازم نیست آن‌ها رو حفظ کنی."
    )
    await _answer(query, text, InlineKeyboardMarkup([[_back()]]), parse_mode="Markdown")

async def render_adminpanel(query, user_id):
    if not is_admin(user_id):
        await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
        return
    with db() as conn:
        users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        cities = conn.execute("SELECT COUNT(*) AS c FROM cities").fetchone()["c"]
        companies = conn.execute("SELECT COUNT(*) AS c FROM companies").fetchone()["c"]
    text = (
        "🛠️ *داشبورد مدیریت*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👥 کاربران: *{users}*   🏙️ شهرها: *{cities}*   🏢 شرکت‌ها: *{companies}*\n\n"
        "این بخش برای کنترل سلامت اقتصاد، امنیت، دسترسی‌ها و تنظیمات بازیه."
    )
    kb = InlineKeyboardMarkup([
        [_btn("📊 آمار کامل", "m:adminstats2", style="primary"), _btn("🚩 گزارش‌ها", "m:adminreports2", style="primary")],
        [_btn("👤 مدیریت کاربران", "m:adminbalance", style="success"), _btn("🚫 امنیت کاربران", "m:adminban", style="danger")],
        [_btn("🏦 مدیریت بانک", "m:adminbank", style="primary"), _btn("👮 مقام‌ها و حقوق", "m:adminroles", style="primary")],
        [_btn("📢 عضویت اجباری", "m:adminforcejoin", style="primary"), _btn("🔧 حالت تعمیر", "m:adminmaintenance", style="danger")],
        [_back()],
    ])
    await _answer(query, text, kb, parse_mode="Markdown")


async def render_adminstats2(query, user_id):
    if not is_admin(user_id):
        await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
        return
    with db() as conn:
        user_count = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        company_count = conn.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"]
        city_count = conn.execute("SELECT COUNT(*) c FROM cities").fetchone()["c"]
        report_count = conn.execute("SELECT COUNT(*) c FROM reports WHERE reviewed=0").fetchone()["c"]
        banned_count = conn.execute("SELECT COUNT(*) c FROM users WHERE banned=1").fetchone()["c"]
    text = (
        f"📊 آمار کلی بازی:\n👥 کاربران: {user_count}\n🏢 شرکت‌ها: {company_count}\n"
        f"🏙 شهرها: {city_count}\n🚩 گزارش‌های بررسی‌نشده: {report_count}\n🚫 کاربران بن‌شده: {banned_count}"
    )
    await _answer(query, text, InlineKeyboardMarkup([[_back("m:adminpanel")]]))


async def render_adminreports2(query, user_id):
    if not is_admin(user_id):
        await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
        return
    with db() as conn:
        rows = conn.execute("SELECT * FROM reports WHERE reviewed=0 ORDER BY id DESC LIMIT 10").fetchall()
    lines = ["🚩 گزارش‌های بررسی‌نشده:\n"]
    buttons = []
    if not rows:
        lines.append("گزارش بررسی‌نشده‌ای نیست.")
    for r in rows:
        lines.append(f"#{r['id']} — گزارش‌دهنده: {r['reporter_id']} | هدف: {r['target_id']} | دلیل: {r['reason']}")
        buttons.append([_btn(f"✅ بررسی‌شده #{r['id']}", f"adminreview:{r['id']}", style="success")])
    buttons.append([_back("m:adminpanel")])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(buttons))


async def render_adminban(query, user_id):
    if not is_admin(user_id):
        await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
        return
    kb = InlineKeyboardMarkup([
        [_btn("🚫 بن کردن کاربر", "adm:ban", style="danger")],
        [_btn("✅ رفع بن کاربر", "adm:unban", style="success")],
        [_back("m:adminpanel")],
    ])
    await _answer(query, "🚫 بن / رفع بن — یک عملیات رو انتخاب کن:", kb)


async def render_adminbalance(query, user_id, page=0):
    if not is_admin(user_id):
        await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
        return
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        rows = conn.execute("SELECT * FROM users ORDER BY user_id LIMIT ? OFFSET ?", (8, page * 8)).fetchall()
    total_pages = max(1, (total + 7) // 8)
    lines = [f"👥 *مدیریت کاربران* — صفحه {page + 1}/{total_pages}", "", "هر دکمه: نام • سطح • بودجه نقدی"]
    buttons = []
    for r in rows:
        rd = dict(r)
        idx, _ = level_for_networth(net_worth(rd))
        name = r["username"] or f"کاربر {r['user_id']}"
        status = "🚫" if r["banned"] else "🟢"
        buttons.append([_btn(f"{status} {name} • L{idx} • 💰{fmt_money(r['cash'])}", f"admuser:{r['user_id']}:{page}", style="primary")])
    nav = []
    if page > 0:
        nav.append(_btn("◀️ قبلی", f"admusers:{page - 1}", style="primary"))
    if page + 1 < total_pages:
        nav.append(_btn("بعدی ▶️", f"admusers:{page + 1}", style="primary"))
    if nav:
        buttons.append(nav)
    buttons.append([_btn("🔎 جستجوی کاربر", "adm:searchuser", style="success")])
    buttons.append([_back("m:adminpanel")])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(buttons), parse_mode="Markdown")


def _admin_user_detail_text(target):
    idx, title = level_for_networth(net_worth(target))
    role = get_gov_role(target["user_id"])
    return (
        f"👤 *{md_escape(target.get('username') or str(target['user_id']))}*\n"
        f"🆔 آیدی: `{target['user_id']}`\n"
        f"🏅 سطح: *{idx}* — {title}\n"
        f"💰 بودجه نقدی: *{fmt_money(target['cash'])}*\n"
        f"🏦 بانک: *{fmt_money(target['bank'])}*\n"
        f"💎 دارایی خالص: *{fmt_money(net_worth(target))}*\n"
        f"💼 شغل: {get_job_label(target)}\n"
        f"👮 مقام: {ROLE_NAMES.get(role, 'بدون مقام') if role else 'بدون مقام'}\n"
        f"{'🚫 بن‌شده' if target.get('banned',0) else '🟢 فعال'}"
    )

async def render_admin_user_detail(query, admin_id, target_id, page=0):
    if not is_admin(admin_id):
        await query.answer("دسترسی نداری.", show_alert=True)
        return
    target = get_user(target_id)
    if not target:
        await query.answer("کاربر پیدا نشد.", show_alert=True)
        return
    banned = target.get("banned", 0) == 1
    kb = InlineKeyboardMarkup([
        [_btn("✅ رفع بن" if banned else "🚫 بن کردن", f"admuser:ban:{target_id}:{page}", style="success" if banned else "danger")],
        [_btn("➕ افزایش موجودی", f"admuser:addcash:{target_id}:{page}", style="success"), _btn("➖ کاهش موجودی", f"admuser:subcash:{target_id}:{page}", style="danger")],
        [_btn("⬆️ افزایش سطح", f"admuser:levelup:{target_id}:{page}", style="success"), _btn("⬇️ کاهش سطح", f"admuser:leveldown:{target_id}:{page}", style="danger")],
        [_btn("👑 افزودن به ادمین‌ها", f"admuser:admin:{target_id}:{page}", style="primary")],
        [_btn("🔄 تازه‌سازی", f"admuser:{target_id}:{page}", style="primary")],
        [_back(f"admusers:{page}")],
    ])
    await _answer(query, _admin_user_detail_text(target), kb, parse_mode="Markdown")

async def render_adminforcejoin(query, user_id):
    if not is_admin(user_id):
        await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
        return
    channels = get_force_join_list()
    lines = ["📢 عضویت اجباری کانال/گروه‌ها:\n"]
    kb_rows = []
    if not channels:
        lines.append("چیزی تنظیم نشده — یعنی هیچ محدودیتی برای کاربرا نیست.")
    else:
        for i, ch in enumerate(channels, start=1):
            lines.append(f"{i}. {ch['title']}")
            kb_rows.append([_btn(f"🗑 حذف #{i}", f"adm:rmchannel:{ch['id']}", style="danger")])
    kb_rows.append([_btn("➕ افزودن کانال/گروه", "adm:addchannel", style="success")])
    kb_rows.append([_back("m:adminpanel")])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(kb_rows))


async def render_adminmaintenance(query, user_id):
    if not is_admin(user_id):
        await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
        return
    on = get_setting(MAINTENANCE_KEY) == "1"
    status = "🔴 روشن (ربات برای کاربران عادی خاموشه)" if on else "🟢 خاموش (ربات فعاله)"
    btn_label = "🟢 روشن کردن ربات" if on else "🔴 خاموش کردن ربات"
    kb = InlineKeyboardMarkup([
        [_btn(btn_label, "adm:togglemaint", style="success" if on else "danger")],
        [_back("m:adminpanel")],
    ])
    await _answer(query, f"🔧 حالت تعمیر و نگهداری\nوضعیت فعلی: {status}", kb)


# ----------------------------------------------------------------------------
# پنل‌های مقام‌ها (پلیس، سرباز، سروان، قاضی)
# ----------------------------------------------------------------------------

def _has_role_or_admin(user_id, role):
    return get_gov_role(user_id) == role or is_admin(user_id)


async def render_policepanel(query, user_id):
    if not _has_role_or_admin(user_id, "police"):
        await query.answer("این بخش فقط برای پلیس است.", show_alert=True)
        return
    kb = InlineKeyboardMarkup([
        [_btn("🚨 گرفتن مجرم", "gov:arrest", style="danger")],
        [_btn("🚔 لیست بازداشتگاه", "m:detentionlist", style="primary")],
        [_back()],
    ])
    await _answer(query, "👮 پنل مدیریت پلیس", kb)


async def render_judgepanel(query, user_id):
    if not _has_role_or_admin(user_id, "judge"):
        await query.answer("این بخش فقط برای قاضی است.", show_alert=True)
        return
    with db() as conn:
        pending_count = conn.execute("SELECT COUNT(*) c FROM court_summons WHERE status='pending'").fetchone()["c"]
    kb = InlineKeyboardMarkup([
        [_btn("📅 احضار به دادگاه", "gov:summon", style="primary")],
        [_btn(f"📋 احضاریه‌های در انتظار ({pending_count})", "m:pendingsummons", style="primary")],
        [_btn("⚖️ صدور حکم مستقیم", "gov:verdict", style="danger")],
        [_btn("🚔 بازداشتگاه", "m:detentionlist", style="primary"),
         _btn("🔒 زندان", "m:prisonlist", style="primary")],
        [_back()],
    ])
    await _answer(query, "⚖️ پنل مدیریت قاضی", kb)


async def render_soldierpanel(query, user_id):
    if not _has_role_or_admin(user_id, "soldier"):
        await query.answer("این بخش فقط برای سرباز است.", show_alert=True)
        return
    salary = get_role_salary("soldier")
    text = f"🪖 پنل سرباز\n💰 حقوق: {fmt_money(salary)}\n\nبرای امنیت شهر تلاش کن!"
    await _answer(query, text, InlineKeyboardMarkup([[_back()]]))


async def render_captainpanel(query, user_id):
    if not _has_role_or_admin(user_id, "captain"):
        await query.answer("این بخش فقط برای سروان است.", show_alert=True)
        return
    salary = get_role_salary("captain")
    kb = InlineKeyboardMarkup([
        [_btn("🚔 لیست بازداشتگاه", "m:detentionlist", style="primary")],
        [_back()],
    ])
    await _answer(query, f"🎖️ پنل سروان\n💰 حقوق: {fmt_money(salary)}", kb)


async def render_detentionlist(query, user_id):
    role = get_gov_role(user_id)
    if not role and not is_admin(user_id):
        await query.answer("دسترسی نداری.", show_alert=True)
        return
    now = time.time()
    with db() as conn:
        rows = conn.execute("SELECT * FROM users WHERE detention_until > ? ORDER BY detention_until", (now,)).fetchall()
    lines = ["🚔 لیست بازداشتگاه:\n"]
    buttons = []
    if not rows:
        lines.append("کسی در بازداشتگاه نیست.")
    can_release = role in ("police", "judge") or is_admin(user_id)
    for r in rows:
        remain = int((r["detention_until"] - now) / 60) + 1
        label = r["username"] or r["user_id"]
        lines.append(f"• {label} — {remain} دقیقه مونده")
        if can_release:
            buttons.append([_btn(f"🔓 آزاد کردن {label}", f"gov:release:detention:{r['user_id']}", style="success")])
    buttons.append([_back()])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(buttons))


async def render_prisonlist(query, user_id):
    role = get_gov_role(user_id)
    if not role and not is_admin(user_id):
        await query.answer("دسترسی نداری.", show_alert=True)
        return
    now = time.time()
    with db() as conn:
        rows = conn.execute("SELECT * FROM users WHERE prison_until > ? ORDER BY prison_until", (now,)).fetchall()
    lines = ["🔒 لیست زندان:\n"]
    buttons = []
    if not rows:
        lines.append("کسی در زندان نیست.")
    can_release = role == "judge" or is_admin(user_id)
    for r in rows:
        remain = int((r["prison_until"] - now) / 60) + 1
        label = r["username"] or r["user_id"]
        lines.append(f"• {label} — {remain} دقیقه مونده")
        if can_release:
            buttons.append([_btn(f"🔓 آزاد کردن {label}", f"gov:release:prison:{r['user_id']}", style="success")])
    buttons.append([_back()])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(buttons))


async def render_pendingsummons(query, user_id):
    if not _has_role_or_admin(user_id, "judge"):
        await query.answer("این بخش فقط برای قاضی است.", show_alert=True)
        return
    with db() as conn:
        rows = conn.execute("SELECT * FROM court_summons WHERE status='pending' ORDER BY id DESC LIMIT 15").fetchall()
    lines = ["📋 احضاریه‌های در انتظار حکم:\n"]
    buttons = []
    if not rows:
        lines.append("چیزی در انتظار نیست.")
    for r in rows:
        u = get_user(r["user_id"])
        label = (u.get("username") or r["user_id"]) if u else r["user_id"]
        lines.append(f"#{r['id']} — {label} — {r['scheduled_at']} — دلیل: {r['reason']}")
        buttons.append([_btn(f"⚖️ صدور حکم برای {label}", f"gov:verdictfor:{r['user_id']}", style="danger")])
    buttons.append([_back("m:judgepanel")])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(buttons))


USER_PICK_PAGE_SIZE = 8

USER_PICK_TITLES = {
    "assignrole": "👮 یک کاربر رو برای تعیین مقام انتخاب کن:",
    "removerole": "➖ یک کاربر رو برای عزل از مقام انتخاب کن:",
    "arrest": "🚨 مظنون رو انتخاب کن:",
    "summon": "📅 فردی که می‌خوای احضار کنی رو انتخاب کن:",
    "verdict": "⚖️ فردی که می‌خوای براش حکم صادر کنی رو انتخاب کن:",
    "lookuprecord": "🔍 کاربر مورد نظر رو برای دیدن سوابق انتخاب کن:",
}

USER_PICK_PERMISSION = {
    "assignrole": lambda uid: is_admin(uid),
    "removerole": lambda uid: is_admin(uid),
    "arrest": lambda uid: _has_role_or_admin(uid, "police"),
    "summon": lambda uid: _has_role_or_admin(uid, "judge"),
    "verdict": lambda uid: _has_role_or_admin(uid, "judge"),
    "lookuprecord": lambda uid: _has_role_or_admin(uid, "judge") or is_admin(uid),
}

USER_PICK_BACK = {
    "assignrole": "m:adminroles",
    "removerole": "m:adminroles",
    "arrest": "m:policepanel",
    "summon": "m:judgepanel",
    "verdict": "m:judgepanel",
    "lookuprecord": "m:adminroles",
}


SELF_EXCLUDED_PICK_PURPOSES = {"arrest"}


async def render_pick_mode(query, purpose, title):
    """قبل از انتخاب کاربر، می‌پرسه از لیست انتخاب کنه یا با آیدی/یوزرنیم جستجو کنه."""
    text = f"{title}\nچطور می‌خوای کاربر رو انتخاب کنی؟"
    kb = InlineKeyboardMarkup([
        [_btn("📋 نمایش لیست کاربران", f"pickuser:{purpose}:0", style="primary")],
        [_btn("🔍 جستجو با آیدی/یوزرنیم", f"gov:searchpurpose:{purpose}", style="success")],
        [_back(USER_PICK_BACK.get(purpose, "m:main"))],
    ])
    await _answer(query, text, kb)


async def render_user_picker(query, viewer_id, purpose, page=0):
    check = USER_PICK_PERMISSION.get(purpose)
    if not check or not check(viewer_id):
        await query.answer("دسترسی نداری.", show_alert=True)
        return
    exclude_self = purpose in SELF_EXCLUDED_PICK_PURPOSES
    with db() as conn:
        if exclude_self:
            total = conn.execute(
                "SELECT COUNT(*) c FROM users WHERE user_id != ?", (viewer_id,)
            ).fetchone()["c"]
            rows = conn.execute(
                "SELECT * FROM users WHERE user_id != ? ORDER BY user_id LIMIT ? OFFSET ?",
                (viewer_id, USER_PICK_PAGE_SIZE, page * USER_PICK_PAGE_SIZE),
            ).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
            rows = conn.execute(
                "SELECT * FROM users ORDER BY user_id LIMIT ? OFFSET ?",
                (USER_PICK_PAGE_SIZE, page * USER_PICK_PAGE_SIZE),
            ).fetchall()
    total_pages = max(1, (total + USER_PICK_PAGE_SIZE - 1) // USER_PICK_PAGE_SIZE)
    lines = [f"{USER_PICK_TITLES.get(purpose, 'انتخاب کاربر')}\n(صفحه {page + 1} از {total_pages})"]
    buttons = []
    for r in rows:
        label = r["username"] or str(r["user_id"])
        role = get_gov_role(r["user_id"])
        role_tag = f" {ROLE_ICONS[role]}" if role else ""
        buttons.append([_btn(f"{label}{role_tag}", f"pickeduser:{purpose}:{r['user_id']}:{page}", style="primary")])
    nav_row = []
    if page > 0:
        nav_row.append(_btn("◀️ قبلی", f"pickuser:{purpose}:{page - 1}", style="primary"))
    if (page + 1) < total_pages:
        nav_row.append(_btn("بعدی ▶️", f"pickuser:{purpose}:{page + 1}", style="primary"))
    if nav_row:
        buttons.append(nav_row)
    buttons.append([_back(USER_PICK_BACK.get(purpose, "m:main"))])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(buttons))


async def render_adminroles(query, user_id):
    if not is_admin(user_id):
        await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
        return
    roles = list_gov_roles()
    lines = ["👮 مدیریت مقام‌ها\n"]
    if not roles:
        lines.append("هیچ مقامی تعیین نشده.")
    else:
        for r in roles:
            u = get_user(r["user_id"])
            label = (u.get("username") or r["user_id"]) if u else r["user_id"]
            lines.append(f"{ROLE_ICONS.get(r['role'], '')} {label} — {ROLE_NAMES.get(r['role'], r['role'])}")
    kb = InlineKeyboardMarkup([
        [_btn("➕ تعیین مقام", "gov:assignrole", style="success")],
        [_btn("➖ عزل از مقام", "gov:removerole", style="danger")],
        [_btn("💰 حقوق مقام‌ها", "m:adminsalaries", style="primary")],
        [_btn("🔍 مشاهده سوابق قضایی", "gov:lookuprecord", style="primary")],
        [_btn("🚔 بازداشتگاه", "m:detentionlist", style="primary"),
         _btn("🔒 زندان", "m:prisonlist", style="primary")],
        [_back("m:adminpanel")],
    ])
    await _answer(query, "\n".join(lines), kb)


async def render_adminsalaries(query, user_id):
    if not is_admin(user_id):
        await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
        return
    lines = ["💰 حقوق مقام‌ها:\n"]
    buttons = []
    for role in GOV_ROLES:
        salary = get_role_salary(role)
        lines.append(f"{ROLE_ICONS[role]} {ROLE_NAMES[role]}: {fmt_money(salary)}")
        buttons.append([_btn(f"✏️ تغییر حقوق {ROLE_NAMES[role]}", f"gov:editsalary:{role}", style="primary")])
    buttons.append([_btn("💵 پرداخت حقوق همه (الان)", "gov:payallsalaries", style="success")])
    buttons.append([_back("m:adminroles")])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(buttons))


# ----------------------------------------------------------------------------
# مدیریت بانک (پنل ادمین)
# ----------------------------------------------------------------------------

BANK_PAGE_SIZE = 8


async def render_adminbank(query, user_id):
    if not is_admin(user_id):
        await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
        return
    max_mult = get_loan_max_multiplier()
    with db() as conn:
        total_users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        frozen_count = conn.execute("SELECT COUNT(*) c FROM users WHERE bank_frozen=1").fetchone()["c"]
        total_bank = conn.execute("SELECT COALESCE(SUM(bank),0) s FROM users").fetchone()["s"]
    text = (
        "🏦 *مدیریت بانک*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👥 کل حساب‌ها: *{total_users}*\n"
        f"🧊 حساب‌های مسدود: *{frozen_count}*\n"
        f"💰 مجموع موجودی بانکی شهر: *{fmt_money(total_bank)}*\n"
        f"📈 ضریب سقف وام: *{max_mult}×* امتیاز اعتبار\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "برای مدیریت حساب هر کاربر، از لیست پایین استفاده کن — نیازی به آیدی نیست."
    )
    kb = InlineKeyboardMarkup([
        [_btn("🔍 جستجوی کاربر (آیدی/یوزرنیم)", "gov:searchuser", style="success")],
        [_btn("📋 لیست کاربران بانک", "bankpage:0", style="primary")],
        [_btn("💳 واریز سریع با شماره کارت", "gov:bankdepositcard", style="success")],
        [_btn("📈 تعیین سقف وام", "gov:setloancap", style="primary")],
        [_back("m:adminpanel")],
    ])
    await _answer(query, text, kb, parse_mode="Markdown")


async def render_bank_user_list(query, admin_id, page=0):
    if not is_admin(admin_id):
        await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
        return
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        rows = conn.execute(
            "SELECT * FROM users ORDER BY user_id LIMIT ? OFFSET ?", (BANK_PAGE_SIZE, page * BANK_PAGE_SIZE)
        ).fetchall()
    total_pages = max(1, (total + BANK_PAGE_SIZE - 1) // BANK_PAGE_SIZE)
    lines = [f"📋 *لیست کاربران بانک* (صفحه {page + 1} از {total_pages})\n"]
    buttons = []
    for r in rows:
        label = r["username"] or str(r["user_id"])
        frozen_dot = "🧊" if r["bank_frozen"] else "🟢"
        buttons.append([
            _btn(
                f"{frozen_dot} {label} — 💰{fmt_money(r['bank'])}",
                f"bankuser:{r['user_id']}:{page}",
                style="primary",
            )
        ])
    nav_row = []
    if page > 0:
        nav_row.append(_btn("◀️ قبلی", f"bankpage:{page - 1}", style="primary"))
    if (page + 1) < total_pages:
        nav_row.append(_btn("بعدی ▶️", f"bankpage:{page + 1}", style="primary"))
    if nav_row:
        buttons.append(nav_row)
    buttons.append([_back("m:adminbank")])
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def render_bank_user_detail(query, admin_id, target_id, back_page=0):
    if not is_admin(admin_id):
        await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
        return
    target = get_user(target_id)
    if not target:
        await query.answer("کاربر پیدا نشد.", show_alert=True)
        return
    frozen = target.get("bank_frozen", 0) == 1
    status_line = "🧊 مسدود" if frozen else "🟢 فعال"
    text = (
        f"👤 *{md_escape(target.get('username') or target_id)}*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "💳 *کارت بانکی*\n"
        f"`{format_card_number(target.get('card_number'))}`\n"
        f"وضعیت: {status_line}\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "💰 *موجودی‌ها*\n"
        f"▫️ پول نقد: *{fmt_money(target['cash'])}*\n"
        f"▫️ حساب بانکی: *{fmt_money(target['bank'])}*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "📊 *اعتبار*\n"
        f"{credit_tier(target['credit_score'])} — امتیاز {target['credit_score']}\n"
        f"▫️ بدهی وام: *{fmt_money(target['loan_amount'])}*"
    )
    freeze_btn = (
        _btn("🔓 رفع مسدودی", f"bankfreeze:{target_id}:{back_page}", style="success")
        if frozen else
        _btn("🧊 مسدود کردن حساب", f"bankfreeze:{target_id}:{back_page}", style="danger")
    )
    kb = InlineKeyboardMarkup([
        [freeze_btn],
        [_btn("➕ شارژ حساب", f"bankcharge:{target_id}:{back_page}", style="success"),
         _btn("➖ کسر از حساب", f"bankdeduct:{target_id}:{back_page}", style="danger")],
        [_back(f"bankpage:{back_page}")],
    ])
    await _answer(query, text, kb, parse_mode="Markdown")


def build_user_search_panel(target_id):
    """متن و کیبورد پنل ترکیبی «جستجوی کاربر» رو می‌سازه: هم مدیریت بانک هم مدیریت مقام."""
    target = get_user(target_id)
    if not target:
        return None
    frozen = target.get("bank_frozen", 0) == 1
    status_line = "🧊 مسدود" if frozen else "🟢 فعال"
    role = get_gov_role(target_id)
    role_line = f"{ROLE_ICONS.get(role, '')} {ROLE_NAMES.get(role, role)}" if role else "بدون مقام"
    text = (
        f"👤 *{md_escape(target.get('username') or target_id)}*\n"
        f"🆔 آیدی: `{target_id}`\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "💳 *کارت بانکی*\n"
        f"`{format_card_number(target.get('card_number'))}`\n"
        f"وضعیت حساب: {status_line}\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "💰 *موجودی‌ها*\n"
        f"▫️ پول نقد: *{fmt_money(target['cash'])}*\n"
        f"▫️ حساب بانکی: *{fmt_money(target['bank'])}*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "📊 *اعتبار*\n"
        f"{credit_tier(target['credit_score'])} — امتیاز {target['credit_score']}\n"
        f"▫️ بدهی وام: *{fmt_money(target['loan_amount'])}*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👮 *مقام فعلی:* {role_line}"
    )
    freeze_btn = (
        _btn("🔓 رفع مسدودی", f"usearchfreeze:{target_id}", style="success")
        if frozen else
        _btn("🧊 مسدود کردن حساب", f"usearchfreeze:{target_id}", style="danger")
    )
    role_row = (
        [_btn("🔁 تغییر مقام", f"usearchrole:{target_id}", style="primary"),
         _btn("➖ عزل از مقام", f"usearchrolerm:{target_id}", style="danger")]
        if role else
        [_btn("👮 تعیین مقام", f"usearchrole:{target_id}", style="success")]
    )
    kb = InlineKeyboardMarkup([
        [freeze_btn],
        [_btn("➕ شارژ حساب", f"usearchcharge:{target_id}", style="success"),
         _btn("➖ کسر از حساب", f"usearchdeduct:{target_id}", style="danger")],
        role_row,
        [_btn("🔍 جستجوی کاربر دیگر", "gov:searchuser", style="primary")],
        [_back("m:adminbank")],
    ])
    return text, kb


async def render_user_search_panel(query, admin_id, target_id):
    if not is_admin(admin_id):
        await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
        return
    built = build_user_search_panel(target_id)
    if not built:
        await query.answer("کاربر پیدا نشد.", show_alert=True)
        return
    text, kb = built
    await _answer(query, text, kb, parse_mode="Markdown")




# ----------------------------------------------------------------------------
# 🏙️ رابط دکمه‌ای شهرداری و انتخابات
# ----------------------------------------------------------------------------

def city_is_active(chat_id: int) -> bool:
    with db() as conn:
        row = conn.execute("SELECT active FROM cities WHERE chat_id=?", (chat_id,)).fetchone()
    return bool(row and row["active"] == 1)


def _city_admin_required(user_id: int) -> bool:
    return is_admin(user_id)


def _next_election_timestamp() -> float:
    return time.time() + CITY_ELECTION_INTERVAL


async def _auto_start_due_elections(context: ContextTypes.DEFAULT_TYPE):
    """هر ۱۰ روز یک انتخابات باز می‌شود؛ مهلت رأی‌گیری ۲۴ ساعت است و نتیجه خودکار اعلام می‌شود."""
    now = time.time()
    finished = []
    started = []
    with db() as conn:
        open_rows = conn.execute("SELECT * FROM elections WHERE status='open'").fetchall()
        for election in open_rows:
            if election["started_at"] and now - election["started_at"] >= CITY_ELECTION_DURATION:
                votes = conn.execute(
                    "SELECT candidate_id, COUNT(*) AS c FROM election_votes WHERE election_id=? GROUP BY candidate_id ORDER BY c DESC, candidate_id ASC",
                    (election["id"],),
                ).fetchall()
                winner_id = votes[0]["candidate_id"] if votes else None
                conn.execute("UPDATE elections SET status='closed', finished_at=? WHERE id=?", (now, election["id"]))
                conn.execute("UPDATE cities SET mayor_id=?, next_election_at=? WHERE chat_id=?", (winner_id, now + CITY_ELECTION_INTERVAL, election["chat_id"]))
                finished.append((election["chat_id"], winner_id))
        cities = conn.execute("SELECT * FROM cities WHERE active=1").fetchall()
        for city in cities:
            next_at = city["next_election_at"] or 0
            open_election = conn.execute("SELECT 1 FROM elections WHERE chat_id=? AND status='open' LIMIT 1", (city["chat_id"],)).fetchone()
            if open_election or (next_at and next_at > now):
                continue
            conn.execute("INSERT INTO elections (chat_id,status,started_at,automatic) VALUES (?, 'open', ?, 1)", (city["chat_id"], now))
            conn.execute("UPDATE cities SET next_election_at=? WHERE chat_id=?", (now + CITY_ELECTION_INTERVAL, city["chat_id"]))
            started.append((city["chat_id"], city["name"]))
    for chat_id, winner_id in finished:
        try:
            if winner_id:
                winner=get_user(winner_id); name=(winner or {}).get("username") or str(winner_id)
                await context.bot.send_message(chat_id, f"👑 *نتیجه انتخابات:* {md_escape(name)} شهردار جدید شهر شد!", parse_mode="Markdown")
            else:
                await context.bot.send_message(chat_id, "🗳️ دوره انتخابات تمام شد اما رأیی ثبت نشده بود؛ فعلاً شهردار نداریم.")
        except Exception:
            pass
    for chat_id, city_name in started:
        try:
            await context.bot.send_message(chat_id, f"🗳️ *انتخابات شهرداری {md_escape(city_name)} آغاز شد!*\n\n⏳ ۲۴ ساعت فرصت رأی‌گیری داری.\nاز منوی «🏙️ شهرداری و انتخابات» نامزد شو یا رأی بده.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[_btn("🏙️ ورود به انتخابات", "m:city", style="success")]]))
        except Exception:
            pass

def _city_for_query(query):
    """شهر مربوط به گروهی که همین منو داخل آن باز شده است."""
    if not query.message or query.message.chat.type == "private":
        return None
    with db() as conn:
        row = conn.execute("SELECT * FROM cities WHERE chat_id=?", (query.message.chat.id,)).fetchone()
    return dict(row) if row else None


def _open_election(chat_id):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM elections WHERE chat_id=? AND status='open' ORDER BY id DESC LIMIT 1",
            (chat_id,),
        ).fetchone()
    return dict(row) if row else None


def _city_candidate_rows(election_id):
    with db() as conn:
        return conn.execute(
            """SELECT ec.user_id, u.username, u.avatar, COUNT(ev.voter_id) AS votes
               FROM election_candidates ec
               JOIN users u ON u.user_id=ec.user_id
               LEFT JOIN election_votes ev
                 ON ev.election_id=ec.election_id AND ev.candidate_id=ec.user_id
               WHERE ec.election_id=?
               GROUP BY ec.user_id
               ORDER BY votes DESC, ec.user_id ASC""",
            (election_id,),
        ).fetchall()


def _city_mayor_label(city):
    if not city or not city.get("mayor_id"):
        return "بدون شهردار"
    mayor = get_user(city["mayor_id"])
    return md_escape((mayor or {}).get("username") or str(city["mayor_id"]))


async def render_city(query, user_id):
    """داشبورد شهری: ثبت شهر، انتخابات، نامزدی، رأی‌گیری و بودجه."""
    if not query.message or query.message.chat.type == "private":
        await query.answer("🏙️ شهرداری فقط داخل گروه‌ها در دسترسه.", show_alert=True)
        return
    chat_id = query.message.chat.id
    city = _city_for_query(query)
    if not city:
        text = (
            "🏙️ *شهرداری*\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "این گروه هنوز یک شهر بازی نیست.\n\n"
            "با فعال‌کردن شهر، اعضا می‌تونن انتخابات برگزار کنن،\n"
            "شهردار انتخاب کنن و برای توسعه شهر بودجه جمع کنن."
        )
        kb = InlineKeyboardMarkup([
            [_btn("🏙️ فعال‌سازی این شهر", "city:register", style="success")],
            [_back()],
        ])
        await _answer(query, text, kb, parse_mode="Markdown")
        return

    election = _open_election(chat_id)
    lines = [
        "🏙️ *شهرداری و مدیریت شهر*",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        f"📍 شهر: *{md_escape(city['name'])}*",
        f"👑 شهردار: *{_city_mayor_label(city)}*",
        f"💰 بودجه شهر: *{fmt_money(city['budget'])}*",
        f"🏆 امتیاز شهر: *{city['score']}*",
    ]
    buttons = []
    if election:
        lines += ["", "🗳️ *انتخابات در حال برگزاری است*"]
        candidates = _city_candidate_rows(election["id"])
        if candidates:
            for i, c in enumerate(candidates, 1):
                label = c["username"] or f"کاربر {c['user_id']}"
                lines.append(f"{i}. {c['avatar'] or '🙂'} {md_escape(label)} — *{c['votes']} رأی*")
                if c["user_id"] != user_id:
                    buttons.append([_btn(f"🗳️ رأی به {label}", f"city:vote:{c['user_id']}", style="success")])
        else:
            lines.append("هنوز کسی نامزد نشده؛ تو می‌تونی اولین نفر باشی.")
        buttons.append([_btn("🙋‍♂️ نامزد شهرداری می‌شوم", "city:candidate", style="primary")])
        buttons.append([_btn("📊 تازه‌سازی نتایج", "m:city", style="primary")])
        if is_admin(user_id):
            buttons.append([_btn("🔒 پایان انتخابات (مالک)", "city:finish", style="danger")])
    else:
        lines += ["", "✨ *انتخابات فعالی وجود ندارد.*", "دوره‌های انتخابات هر ۱۰ روز یک‌بار به‌صورت خودکار آغاز می‌شوند."]
        if is_admin(user_id):
            buttons.append([_btn("🗳️ آغاز دستی انتخابات (مالک)", "city:start", style="success")])
    if city.get("mayor_id") == user_id:
        buttons.append([_btn("👑 دفتر شهردار", "city:mayor", style="success")])
    buttons += [
        [_btn("💰 کمک به بودجه شهر", "city:fund", style="primary"),
         _btn("ℹ️ اطلاعات کامل شهر", "city:info", style="primary")],
        [_btn("🏆 رتبه‌بندی شهرها", "m:citytop", style="primary")],
        [_back()],
    ]
    await _answer(query, "\n".join(lines), InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def _city_register_ui(query, user_id):
    if not query.message or query.message.chat.type == "private":
        await query.answer("این گزینه فقط داخل گروه کار می‌کنه.", show_alert=True)
        return
    if not is_admin(user_id):
        await query.answer("فقط مالک ربات می‌تواند یک شهر جدید را فعال کند.", show_alert=True)
        return
    chat_id = query.message.chat.id
    title = query.message.chat.title or "شهر جدید"
    with db() as conn:
        existing = conn.execute("SELECT 1 FROM cities WHERE chat_id=?", (chat_id,)).fetchone()
        if existing:
            await query.answer("این گروه قبلاً شهر شده.", show_alert=True)
            await render_city(query, user_id)
            return
        conn.execute("INSERT INTO cities (chat_id, name, budget, election_interval_hours, next_election_at, active) VALUES (?,?,0,240,?,1)", (chat_id, title[:100], time.time() + CITY_ELECTION_INTERVAL))
    await query.answer("🏙️ شهر با موفقیت فعال شد!", show_alert=True)
    await render_city(query, user_id)


async def _city_start_election_ui(query, user_id):
    if not is_admin(user_id):
        await query.answer("انتخابات طبق دوره‌ی ۱۰ روزه به‌صورت خودکار برگزار می‌شود. فقط مالک ربات می‌تواند دستی آن را شروع کند.", show_alert=True)
        return
    city = _city_for_query(query)
    if not city:
        await query.answer("اول این گروه رو به شهر تبدیل کن.", show_alert=True)
        return
    if _open_election(query.message.chat.id):
        await query.answer("یک انتخابات از قبل در حال برگزاریه.", show_alert=True)
        return
    with db() as conn:
        now = time.time()
        conn.execute("INSERT INTO elections (chat_id, status, started_at, automatic) VALUES (?, 'open', ?, 0)", (query.message.chat.id, now))
        conn.execute("UPDATE cities SET next_election_at=? WHERE chat_id=?", (now + CITY_ELECTION_INTERVAL, query.message.chat.id))
    await query.answer("🗳️ انتخابات شروع شد!", show_alert=True)
    await render_city(query, user_id)


async def _city_candidate_ui(query, user_id):
    city = _city_for_query(query)
    election = _open_election(query.message.chat.id) if city else None
    if not election:
        await query.answer("انتخابات فعالی نیست.", show_alert=True)
        return
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO election_candidates (election_id, user_id) VALUES (?,?)",
                     (election["id"], user_id))
    await query.answer("✅ نامزدی شما ثبت شد.", show_alert=True)
    await render_city(query, user_id)


async def _city_vote_ui(query, user_id, candidate_id):
    city = _city_for_query(query)
    election = _open_election(query.message.chat.id) if city else None
    if not election:
        await query.answer("انتخابات فعالی وجود نداره.", show_alert=True)
        return
    if candidate_id == user_id:
        await query.answer("❌ نمی‌تونی به خودت رأی بدی.", show_alert=True)
        return
    with db() as conn:
        candidate = conn.execute(
            "SELECT 1 FROM election_candidates WHERE election_id=? AND user_id=?",
            (election["id"], candidate_id),
        ).fetchone()
        if not candidate:
            await query.answer("این فرد نامزد این انتخابات نیست.", show_alert=True)
            return
        conn.execute(
            "INSERT OR REPLACE INTO election_votes (election_id, voter_id, candidate_id) VALUES (?,?,?)",
            (election["id"], user_id, candidate_id),
        )
    name = ((get_user(candidate_id) or {}).get("username") or str(candidate_id))
    await query.answer(f"🗳️ رأی شما برای {name} ثبت شد.", show_alert=True)
    await render_city(query, user_id)


async def _city_finish_ui(query, user_id):
    if not is_admin(user_id):
        await query.answer("فقط مالک ربات می‌تواند انتخابات را دستی ببندد.", show_alert=True)
        return
    city = _city_for_query(query)
    election = _open_election(query.message.chat.id) if city else None
    if not election:
        await query.answer("انتخابات فعالی نیست.", show_alert=True)
        return
    with db() as conn:
        votes = conn.execute(
            "SELECT candidate_id, COUNT(*) AS c FROM election_votes WHERE election_id=? GROUP BY candidate_id ORDER BY c DESC, candidate_id ASC",
            (election["id"],),
        ).fetchall()
        conn.execute("UPDATE elections SET status='closed', finished_at=? WHERE id=?", (time.time(), election["id"]))
        winner_id = votes[0]["candidate_id"] if votes else None
        conn.execute("UPDATE cities SET next_election_at=? WHERE chat_id=?", (time.time() + CITY_ELECTION_INTERVAL, query.message.chat.id))
        if winner_id:
            conn.execute("UPDATE cities SET mayor_id=? WHERE chat_id=?", (winner_id, query.message.chat.id))
    if winner_id:
        name = ((get_user(winner_id) or {}).get("username") or str(winner_id))
        await query.answer(f"👑 {name} شهردار شد!", show_alert=True)
    else:
        await query.answer("انتخابات بدون رأی بسته شد.", show_alert=True)
    await render_city(query, user_id)


async def _city_info_ui(query, user_id):
    city = _city_for_query(query)
    if not city:
        await query.answer("این گروه هنوز شهر نیست.", show_alert=True)
        return
    with db() as conn:
        closed_count = conn.execute(
            "SELECT COUNT(*) AS c FROM elections WHERE chat_id=? AND status='closed'",
            (query.message.chat.id,),
        ).fetchone()["c"]
        open_election = conn.execute(
            "SELECT 1 FROM elections WHERE chat_id=? AND status='open' ORDER BY id DESC LIMIT 1",
            (query.message.chat.id,),
        ).fetchone()
    text = (
        f"🏙️ *پرونده شهر — {md_escape(city['name'])}*\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👑 شهردار: *{_city_mayor_label(city)}*\n"
        f"💰 بودجه: *{fmt_money(city['budget'])}*\n"
        f"🏆 امتیاز توسعه: *{city['score']}*\n"
        f"🗳️ انتخابات فعال: *{'بله' if open_election else 'خیر'}*\n"
        f"📚 انتخابات برگزارشده: *{closed_count}*\n\n"
        "💡 بودجه از مشارکت شهروندها جمع می‌شه و برای توسعه شهر خرج می‌شه."
    )
    await _answer(query, text, InlineKeyboardMarkup([[_back("m:city")]]), parse_mode="Markdown")


async def render_mayor_panel(query, user_id):
    city = _city_for_query(query)
    if not city or city.get("mayor_id") != user_id:
        await query.answer("این پنل فقط برای شهردار همین شهره.", show_alert=True)
        return
    text = (f"👑 *دفتر شهردار — {md_escape(city['name'])}*\n\n"
            f"💰 بودجه شهر: *{fmt_money(city['budget'])}*\n"
            f"🏆 امتیاز توسعه: *{city['score']}*\n\n"
            "شهردار می‌تواند بودجه را برای پروژه‌های شهری خرج کند.")
    kb = InlineKeyboardMarkup([
        [_btn("🏗️ اجرای پروژه شهری", "mayor:project", style="success")],
        [_btn("📊 وضعیت شهر", "m:city", style="primary")],
        [_back("m:city")],
    ])
    await _answer(query, text, kb, parse_mode="Markdown")


SIMPLE_ACTIONS = {
    "sleep": do_sleep, "eat": do_eat, "gym": do_gym, "restaurant": do_restaurant,
    "fish": do_fish, "mine": do_mine, "farm": do_farm, "puzzle": do_puzzle,
    "havechild": do_havechild, "payroll": do_payroll,
    "study": do_study, "buyinsurance": do_buyinsurance,
}

MENU_RENDERERS = {
    "main": None,  # جدا هندل می‌شه
    "city": render_city,
    "mayor": render_mayor_panel,
    "mayor": render_mayor_panel,
    "profile": render_profile,
    "jobs": render_jobs,
    "skills": render_skills,
    "bank": render_bank,
    "shop": render_shop,
    "shopprop": render_shop_prop,
    "shopveh": render_shop_veh,
    "myassets": render_myassets,
    "market": render_market,
    "mylistings": render_mylistings,
    "stocks": render_stocks,
    "mystocks": render_mystocks,
    "company": render_company,
    "life": render_life,
    "fun": render_fun,
    "mission": render_mission,
    "family": render_family,
    "top": render_top,
    "companiestop": render_companiestop,
    "citytop": render_citytop,
    "world": render_world,
    "notif": render_notif,
    "help": render_help,
    "school": render_school,
    "insurance": render_insurance,
    "friends": render_friends,
    "court": render_court,
    "missionshub": render_missionshub,
    "weeklym": render_weeklym,
    "monthlym": render_monthlym,
    "secretm": render_secretm,
    "adminpanel": render_adminpanel,
    "adminstats2": render_adminstats2,
    "adminreports2": render_adminreports2,
    "adminban": render_adminban,
    "adminbalance": render_adminbalance,
    "adminforcejoin": render_adminforcejoin,
    "adminmaintenance": render_adminmaintenance,
    "policepanel": render_policepanel,
    "judgepanel": render_judgepanel,
    "soldierpanel": render_soldierpanel,
    "captainpanel": render_captainpanel,
    "detentionlist": render_detentionlist,
    "prisonlist": render_prisonlist,
    "pendingsummons": render_pendingsummons,
    "adminroles": render_adminroles,
    "adminbank": render_adminbank,
    "adminsalaries": render_adminsalaries,
}


class _SafeCallbackQuery:
    __slots__ = ("_q", "_answered")

    def __init__(self, query):
        self._q = query
        self._answered = False

    async def answer(self, *args, **kwargs):
        if self._answered:
            return None
        self._answered = True
        try:
            return await self._q.answer(*args, **kwargs)
        except Exception as e:
            logger.warning("callback answer failed (ignored): %s", e)
            return None

    def __getattr__(self, name):
        return getattr(self._q, name)


async def inactive_group_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """در گروهی که شهر فعال نشده، ربات هیچ بازی/اقتصادی اجرا نمی‌کند."""
    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type not in GROUP_TYPES or not user:
        return
    # /menu تنها مسیر مشاهده‌ی صفحه فعال‌سازی است.
    if update.message and update.message.text and update.message.text.split()[0].lower().startswith("/menu"):
        return
    if city_is_active(chat.id):
        return
    if update.callback_query and (update.callback_query.data or "") in ("city:register", "m:city") and is_admin(user.id):
        return
    if update.message and update.message.text and update.message.text.split()[0].lower().startswith("/registercity") and is_admin(user.id):
        return
    if update.message:
        await update.message.reply_text("🏙️ *این ربات هنوز در این شهر فعال نشده.*\nیکی از مدیران ربات باید از /menu گزینه‌ی «افزودن شهر» را بزند.", parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.answer("🏙️ این شهر هنوز فعال نشده.", show_alert=True)
    raise ApplicationHandlerStop


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = _SafeCallbackQuery(update.callback_query)
    user_id = query.from_user.id
    ensure_user(user_id, query.from_user.username or query.from_user.first_name)
    data = query.data or ""

    if query.message and query.message.chat.type != "private":
        owner_id = get_menu_owner(query.message.chat.id, query.message.message_id)
        if owner_id is not None and owner_id != user_id:
            await query.answer("این منو مال شما نیست! برای داشتن منوی خودت /menu رو بزن.", show_alert=True)
            return

    if not await enforce_maintenance(update, context):
        await query.answer()
        return

    if data != "checkjoin" and not await enforce_force_join(update, context):
        await query.answer()
        return

    try:
        if data.startswith("lr:"):
            await _handle_leader_callback(query, context, user_id, data)
            return
        if data.startswith("mr:"):
            await _handle_mayor_callback(query, user_id, data)
            return
        if data == "ui:leader":
            await _render_leader_panel(query, user_id)
            return
        if data == "city:mayor":
            await _render_city_mayor_combined(query, user_id)
            return
        await _dispatch_callback(query, context, user_id, data)
    finally:
        await query.answer()


async def _dispatch_callback(query, context, user_id, data):
    nav_prefixes = ("m:", "bankpage:", "bankuser:", "bankfreeze:")
    if any(data.startswith(p) for p in nav_prefixes):
        # با هر پیمایش توی منو (از جمله دکمه‌ی بازگشت)، هر فرایند چندمرحله‌ای نیمه‌کاره
        # (مثل انتقال با شماره کارت، فرم‌های پنل مدیریت و مقام‌ها) لغو می‌شه تا پیام بعدیِ
        # کاربر با یه فرم قدیمیِ رهاشده قاطی نشه.
        context.user_data.pop("pending_transfer", None)
        context.user_data.pop("pending_amount", None)
        context.user_data.pop("pending_qty", None)
        context.user_data.pop("pending_admin", None)
        context.user_data.pop("pending_gov", None)
        context.user_data.pop("pending_bank", None)

    if data == "m:main":
        await query.answer()
        await show_main(query)
        return

    if data == "city:register":
        await _city_register_ui(query, user_id)
        return
    if data == "city:start":
        await _city_start_election_ui(query, user_id)
        return
    if data == "city:candidate":
        await _city_candidate_ui(query, user_id)
        return
    if data.startswith("city:vote:"):
        await _city_vote_ui(query, user_id, int(data.split(":")[2]))
        return
    if data == "city:finish":
        await _city_finish_ui(query, user_id)
        return
    if data == "city:info":
        await _city_info_ui(query, user_id)
        return
    if data == "city:mayor":
        await render_mayor_panel(query, user_id)
        return
    if data == "city:fund":
        await query.answer()
        await _answer(query, "💰 *کمک به بودجه شهر*\n\nمبلغ موردنظرت رو انتخاب کن:", amount_keyboard("cityfund", back_cb="m:city"), parse_mode="Markdown")
        return

    if data.startswith("m:"):
        key = data[2:].split(":")[0]
        renderer = MENU_RENDERERS.get(key)
        if renderer:
            await query.answer()
            await renderer(query, user_id)
            return
        if key in ("dep", "with", "loan", "payl", "cinv"):
            await query.answer()
            action_map = {"dep": "واریز", "with": "برداشت", "loan": "دریافت وام", "payl": "بازپرداخت وام", "cinv": "افزایش سرمایه شرکت"}
            back = "m:bank" if key != "cinv" else "m:company"
            await _answer(query, f"مبلغ {action_map[key]} رو انتخاب کن:", amount_keyboard(key, back_cb=back))
            return
        if key == "stockbuy" or key == "stocksell":
            await query.answer()
            symbol = data.split(":")[2]
            side = "buy" if key == "stockbuy" else "sell"
            await _answer(
                query, f"چند سهم {symbol} می‌خوای {'بخری' if side=='buy' else 'بفروشی'}؟",
                qty_keyboard(f"stock{side}", symbol, back_cb=f"stocksym:{symbol}"),
            )
            return

    if data == "mayor:project":
        city = _city_for_query(query)
        if not city or city.get("mayor_id") != user_id:
            await query.answer("فقط شهردار می‌تواند پروژه اجرا کند.", show_alert=True); return
        context.user_data["pending_mayor_project"] = True
        await query.answer()
        await _answer(query, "🏗️ نام پروژه و هزینه را در یک پیام بفرست. مثال: پارک مرکزی 50000", InlineKeyboardMarkup([[_back("m:mayor")]]))
        return
    if data.startswith("jobapply:"):
        await act_apply_job(query, user_id, data.split(":", 1)[1])
        return
    if data == "dowork":
        await act_work(query, user_id)
        return
    if data.startswith("train:"):
        await act_train(query, user_id, data.split(":", 1)[1])
        return
    if data.startswith("buyprop:"):
        await act_buy_prop(query, user_id, data.split(":", 1)[1])
        return
    if data.startswith("buyveh:"):
        await act_buy_veh(query, user_id, data.split(":", 1)[1])
        return
    if data.startswith("stocksym:"):
        await render_stock_detail(query, user_id, data.split(":", 1)[1])
        return
    if data.startswith("buyitem:"):
        await act_buy_item(query, user_id, int(data.split(":", 1)[1]))
        return
    if data.startswith("cancellisting:"):
        await act_cancel_listing(query, user_id, int(data.split(":", 1)[1]))
        return
    if data.startswith("claim:"):
        await act_claim(query, user_id, data.split(":", 1)[1])
        return
    if data.startswith("confirm:divorce"):
        msg = await do_divorce(user_id)
        await query.answer(msg, show_alert=True)
        await render_family(query, user_id)
        return
    if data.startswith("court:"):
        report_id = int(data.split(":", 1)[1])
        msg = await do_court(user_id, report_id)
        await query.answer(msg[:200], show_alert=True)
        await render_court(query, user_id)
        return
    if data.startswith("unfriend:"):
        friend_id = int(data.split(":", 1)[1])
        msg = await do_unfriend(user_id, friend_id)
        await query.answer(msg[:200], show_alert=True)
        await render_friends(query, user_id)
        return
    if data.startswith("claimp:"):
        _, period_key, mission_key = data.split(":")
        period_map = {
            "weekly": (WEEKLY_MISSIONS, period_id_week(), render_weeklym),
            "monthly": (MONTHLY_MISSIONS, period_id_month(), render_monthlym),
            "secret": (SECRET_MISSIONS, period_id_secret(), render_secretm),
        }
        definitions, period_id, renderer = period_map[period_key]
        m, err = claim_periodic_mission(user_id, mission_key, period_id, definitions)
        if err:
            await query.answer(err, show_alert=True)
        else:
            await query.answer(f"🎉 گرفتی: {fmt_money(m['reward_cash'])} و {m['reward_xp']} XP", show_alert=True)
        await renderer(query, user_id)
        return

    if data == "checkjoin":
        channels = get_force_join_list()
        missing = [ch for ch in channels if not await is_member_of_channel(context, ch["chat_id"], user_id)]
        if not missing:
            await query.answer("✅ عضویت تایید شد!", show_alert=True)
            await show_main(query)
        else:
            await query.answer("هنوز عضو همه‌ی کانال/گروه‌ها نشدی: " + "، ".join(ch["title"] for ch in missing), show_alert=True)
        return

    if data.startswith("adminreview:"):
        if not is_admin(user_id):
            await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
            return
        report_id = int(data.split(":", 1)[1])
        with db() as conn:
            conn.execute("UPDATE reports SET reviewed=1 WHERE id=?", (report_id,))
        await query.answer("✅ گزارش بررسی‌شده علامت خورد.")
        await render_adminreports2(query, user_id)
        return

    if data == "banktransfer:":
        context.user_data["pending_transfer"] = {"stage": "card"}
        await query.answer()
        await _answer(
            query,
            "💳 شماره کارت ۱۶ رقمی گیرنده رو بفرست (با خط تیره یا بدون خط تیره):",
            InlineKeyboardMarkup([[_back("m:bank")]]),
        )
        return

    if data.startswith("adm:rmchannel:"):
        if not is_admin(user_id):
            await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
            return
        row_id = int(data.split(":")[2])
        row = get_force_join_row(row_id)
        if not row:
            await query.answer("پیدا نشد.", show_alert=True)
            await render_adminforcejoin(query, user_id)
            return
        kb = InlineKeyboardMarkup([
            [_btn("✅ بله، حذف کن", f"adm:rmchannelconfirm:{row_id}", style="danger")],
            [_back("m:adminforcejoin")],
        ])
        await query.answer()
        await _answer(query, f"مطمئنی می‌خوای «{row['title']}» رو از لیست عضویت اجباری حذف کنی؟", kb)
        return

    if data.startswith("adm:rmchannelconfirm:"):
        if not is_admin(user_id):
            await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
            return
        row_id = int(data.split(":")[2])
        remove_force_join_channel(row_id)
        await query.answer("✅ حذف شد.", show_alert=True)
        await render_adminforcejoin(query, user_id)
        return

    if data == "adm:confirmaddchannel":
        if not is_admin(user_id):
            await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
            return
        pending = context.user_data.get("pending_admin")
        if not pending or pending.get("action") != "addchannel" or pending.get("stage") != "confirm":
            await query.answer("چیزی برای تایید نیست.", show_alert=True)
            return
        add_force_join_channel(pending["chat_id"], pending["title"], pending["username"], pending["invite_link"])
        context.user_data.pop("pending_admin", None)
        await query.answer("✅ اضافه شد.", show_alert=True)
        await render_adminforcejoin(query, user_id)
        return

    if data.startswith("adm:"):
        if not is_admin(user_id):
            await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
            return
        action = data.split(":", 1)[1]
        prompts = {
            "ban": "🚫 آیدی عددی یا یوزرنیم (بدون @) کاربری که می‌خوای بن کنی رو بفرست:",
            "unban": "✅ آیدی عددی یا یوزرنیم (بدون @) کاربری که می‌خوای رفع بن کنی رو بفرست:",
            "addbal": "➕ آیدی عددی یا یوزرنیم (بدون @) کاربر مورد نظر رو بفرست:",
            "subbal": "➖ آیدی عددی یا یوزرنیم (بدون @) کاربر مورد نظر رو بفرست:",
            "addchannel": "✏️ آیدی عددی، یوزرنیم (@channel) یا آیدی گروه رو بفرست.\nربات باید از قبل عضو و ادمین اون کانال/گروه باشه:",
        }
        if action == "togglemaint":
            on = get_setting(MAINTENANCE_KEY) == "1"
            set_setting(MAINTENANCE_KEY, "0" if on else "1")
            await query.answer("✅ وضعیت ربات تغییر کرد.", show_alert=True)
            await render_adminmaintenance(query, user_id)
            return
        context.user_data["pending_admin"] = {"action": action, "stage": "target"}
        await query.answer()
        await _answer(query, prompts[action], InlineKeyboardMarkup([[_back("m:adminpanel")]]))
        return

    if data.startswith("pickuser:"):
        _, purpose, page_str = data.split(":")
        await query.answer()
        await render_user_picker(query, user_id, purpose, int(page_str))
        return

    if data.startswith("pickeduser:"):
        _, purpose, target_str, page_str = data.split(":")
        target_id = int(target_str)
        check = USER_PICK_PERMISSION.get(purpose)
        if not check or not check(user_id):
            await query.answer("دسترسی نداری.", show_alert=True)
            return
        target = get_user(target_id)
        if not target:
            await query.answer("کاربر پیدا نشد.", show_alert=True)
            return
        target_label = target.get("username") or target_id

        if purpose == "assignrole":
            kb_rows = [
                [_btn(f"{ROLE_ICONS[r]} {ROLE_NAMES[r]}", f"gov:setrole:{target_id}:{r}", style="primary")]
                for r in GOV_ROLES
            ]
            kb_rows.append([_back("m:adminroles")])
            await query.answer()
            await _answer(query, f"مقام مورد نظر برای {target_label} رو انتخاب کن:", InlineKeyboardMarkup(kb_rows))
            return

        if purpose == "removerole":
            old_role = get_gov_role(target_id)
            if not old_role:
                await query.answer("این کاربر اصلاً مقامی نداره.", show_alert=True)
                return
            remove_gov_role(target_id)
            await query.answer(f"✅ مقام {ROLE_NAMES.get(old_role, old_role)} از {target_label} گرفته شد.", show_alert=True)
            try:
                await context.bot.send_message(target_id, f"⚠️ شما از مقام {ROLE_NAMES.get(old_role, old_role)} عزل شدید.")
            except Exception:
                pass
            await render_adminroles(query, user_id)
            return

        if purpose == "arrest":
            if target_id == user_id:
                await query.answer("نمی‌تونی خودتو دستگیر کنی!", show_alert=True)
                return
            context.user_data["pending_gov"] = {"flow": "arrest", "stage": "reason", "target_id": target_id}
            await query.answer()
            await _answer(
                query, f"📄 دلیل دستگیری {target_label} رو بنویس:",
                InlineKeyboardMarkup([[_back("m:policepanel")]]),
            )
            return

        if purpose == "summon":
            context.user_data["pending_gov"] = {"flow": "summon", "stage": "datetime", "target_id": target_id}
            await query.answer()
            await _answer(
                query, f"📅 تاریخ و ساعت دادگاه برای {target_label} رو بنویس (مثلاً 1404/06/01 ساعت 16:00):",
                InlineKeyboardMarkup([[_back("m:judgepanel")]]),
            )
            return

        if purpose == "verdict":
            kb_rows = [
                [_btn(label, f"gov:vtype:{target_id}:{vt}", style="success" if vt == "acquit" else "danger")]
                for vt, label in VERDICT_TYPES.items()
            ]
            kb_rows.append([_back("m:judgepanel")])
            await query.answer()
            await _answer(query, f"⚖️ نوع حکم برای {target_label} رو انتخاب کن:", InlineKeyboardMarkup(kb_rows))
            return

        if purpose == "lookuprecord":
            await query.answer()
            records = get_judicial_records(target_id)
            if not records:
                lines = [f"📋 هیچ سابقه‌ای برای {target_label} ثبت نشده."]
            else:
                lines = [f"📋 سوابق قضایی {target_label}:\n"]
                for r in records:
                    issuer = get_user(r["issuer_id"]) if r["issuer_id"] else None
                    issuer_label = (issuer.get("username") or r["issuer_id"]) if issuer else "سیستم"
                    detail = f" ({r['detail']})" if r["detail"] else ""
                    lines.append(
                        f"{JUDICIAL_KIND_LABELS.get(r['kind'], r['kind'])} — {r['reason']}{detail} — "
                        f"صادرکننده: {issuer_label} — {r['created_at']}"
                    )
            await _answer(query, "\n".join(lines)[:4000], InlineKeyboardMarkup([[_back("m:adminroles")]]))
            return
        return

    if data.startswith("admusers:"):
        if not is_admin(user_id):
            await query.answer("دسترسی نداری.", show_alert=True); return
        await render_adminbalance(query, user_id, int(data.split(":")[1])); return

    if data.startswith("admuser:"):
        parts = data.split(":")
        if len(parts) >= 3 and parts[1] in ("ban", "addcash", "subcash", "levelup", "leveldown", "admin"):
            if not is_admin(user_id):
                await query.answer("دسترسی نداری.", show_alert=True); return
            action, target_id = parts[1], int(parts[2]); page = int(parts[3]) if len(parts) > 3 else 0
            target = get_user(target_id)
            if not target:
                await query.answer("کاربر پیدا نشد.", show_alert=True); return
            if action == "ban":
                new = 0 if target.get("banned", 0) else 1
                update_user(target_id, banned=new)
                await query.answer("✅ رفع بن شد." if new == 0 else "🚫 کاربر بن شد.", show_alert=True)
                await render_admin_user_detail(query, user_id, target_id, page); return
            if action in ("addcash", "subcash"):
                context.user_data["pending_admin"] = {"action": action, "stage": "amount", "target_id": target_id, "page": page}
                await query.answer()
                await _answer(query, "💰 مبلغ را به تومان بفرست:", InlineKeyboardMarkup([[_back(f"admuser:{target_id}:{page}")]]))
                return
            if action in ("levelup", "leveldown"):
                idx, _ = level_for_networth(net_worth(target))
                next_idx = idx + (1 if action == "levelup" else -1)
                if next_idx < 0 or next_idx >= len(LEVEL_THRESHOLDS):
                    await query.answer("سطح از محدوده مجاز خارج می‌شود.", show_alert=True); return
                delta = LEVEL_THRESHOLDS[next_idx][0] - net_worth(target)
                update_user(target_id, cash=max(0, target["cash"] + delta))
                await query.answer("⬆️ سطح افزایش یافت." if action == "levelup" else "⬇️ سطح کاهش یافت.", show_alert=True)
                await render_admin_user_detail(query, user_id, target_id, page); return
            if action == "admin":
                with db() as conn:
                    exists = conn.execute("SELECT 1 FROM bot_admins WHERE user_id=?", (target_id,)).fetchone()
                    if exists or target_id in ADMIN_IDS:
                        msg = "این کاربر از قبل ادمین است."
                    else:
                        conn.execute("INSERT INTO bot_admins (user_id, added_by) VALUES (?,?)", (target_id, user_id))
                        msg = "👑 کاربر به ادمین‌های ربات اضافه شد."
                await query.answer(msg, show_alert=True)
                await render_admin_user_detail(query, user_id, target_id, page); return
        target_id = int(parts[1]); page = int(parts[2]) if len(parts) > 2 else 0
        await render_admin_user_detail(query, user_id, target_id, page); return

    if data.startswith("bankpage:"):
        if not is_admin(user_id):
            await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
            return
        page = int(data.split(":")[1])
        await query.answer()
        await render_bank_user_list(query, user_id, page)
        return

    if data.startswith("bankuser:"):
        if not is_admin(user_id):
            await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
            return
        _, target_str, page_str = data.split(":")
        await query.answer()
        await render_bank_user_detail(query, user_id, int(target_str), int(page_str))
        return

    if data.startswith("bankfreeze:"):
        if not is_admin(user_id):
            await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
            return
        _, target_str, page_str = data.split(":")
        target_id = int(target_str)
        target = get_user(target_id)
        if not target:
            await query.answer("کاربر پیدا نشد.", show_alert=True)
            return
        new_state = 0 if target.get("bank_frozen", 0) == 1 else 1
        update_user(target_id, bank_frozen=new_state)
        if new_state == 1:
            await query.answer("🧊 حساب مسدود شد.", show_alert=True)
            note = "🧊 حساب بانکی شما از طرف مدیریت مسدود شد."
        else:
            await query.answer("🔓 حساب رفع مسدودی شد.", show_alert=True)
            note = "🔓 حساب بانکی شما از طرف مدیریت از حالت مسدودی خارج شد."
        try:
            await context.bot.send_message(target_id, note)
        except Exception:
            pass
        await render_bank_user_detail(query, user_id, target_id, int(page_str))
        return

    if data.startswith("bankcharge:") or data.startswith("bankdeduct:"):
        if not is_admin(user_id):
            await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
            return
        kind, target_str, page_str = data.split(":")
        context.user_data["pending_bank"] = {
            "flow": "chargeaccount" if kind == "bankcharge" else "deductaccount",
            "stage": "amount", "target_id": int(target_str), "back_page": int(page_str),
        }
        await query.answer()
        verb = "شارژ" if kind == "bankcharge" else "کسر"
        await _answer(
            query, f"مبلغ مورد نظر برای {verb} حساب رو بفرست (فقط رقم):",
            InlineKeyboardMarkup([[_back(f"bankuser:{target_str}:{page_str}")]]),
        )
        return

    if data.startswith("gov:release:"):
        _, _, which, target_str = data.split(":")
        role = get_gov_role(user_id)
        if which == "detention" and role not in ("police", "judge") and not is_admin(user_id):
            await query.answer("دسترسی نداری.", show_alert=True)
            return
        if which == "prison" and role != "judge" and not is_admin(user_id):
            await query.answer("دسترسی نداری.", show_alert=True)
            return
        msg = await do_release(int(target_str), which, user_id, context)
        await query.answer(msg, show_alert=True)
        await (render_detentionlist if which == "detention" else render_prisonlist)(query, user_id)
        return

    if data.startswith("gov:vtype:"):
        _, _, target_str, vtype = data.split(":")
        if not _has_role_or_admin(user_id, "judge"):
            await query.answer("این بخش فقط برای قاضی است.", show_alert=True)
            return
        pending = {"flow": "verdict", "target_id": int(target_str), "vtype": vtype}
        needs_fine = vtype in ("fine", "detention_fine", "prison_fine")
        needs_duration = vtype in ("detention", "prison", "detention_fine", "prison_fine")
        if needs_fine:
            pending["stage"] = "fine"
            prompt = "💸 مبلغ جریمه رو به تومان بفرست (فقط رقم):"
        elif needs_duration:
            pending["stage"] = "duration"
            prompt = "⏱ مدت زمان رو به دقیقه بفرست (فقط رقم):"
        else:
            pending["stage"] = "reason"
            prompt = "📄 دلیل حکم رو بنویس:"
        context.user_data["pending_gov"] = pending
        await query.answer()
        await _answer(query, prompt, InlineKeyboardMarkup([[_back("m:judgepanel")]]))
        return

    if data.startswith("gov:verdictfor:"):
        target_id = int(data.split(":")[2])
        if not _has_role_or_admin(user_id, "judge"):
            await query.answer("این بخش فقط برای قاضی است.", show_alert=True)
            return
        kb_rows = [
            [_btn(label, f"gov:vtype:{target_id}:{vt}", style="success" if vt == "acquit" else "danger")]
            for vt, label in VERDICT_TYPES.items()
        ]
        kb_rows.append([_back("m:pendingsummons")])
        await query.answer()
        await _answer(query, "⚖️ نوع حکم رو انتخاب کن:", InlineKeyboardMarkup(kb_rows))
        return

    if data.startswith("gov:setrole:"):
        if not is_admin(user_id):
            await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
            return
        _, _, target_str, role = data.split(":")
        target_id = int(target_str)
        set_gov_role(target_id, role, user_id)
        context.user_data.pop("pending_gov", None)
        await query.answer(f"✅ مقام {ROLE_NAMES[role]} تعیین شد.", show_alert=True)
        try:
            await context.bot.send_message(
                target_id, f"{ROLE_ICONS[role]} تبریک! شما به مقام {ROLE_NAMES[role]} منصوب شدید."
            )
        except Exception:
            pass
        await render_adminroles(query, user_id)
        return

    if data.startswith("gov:"):
        role = get_gov_role(user_id)
        action = data.split(":", 1)[1]

        if action == "arrest":
            if role != "police" and not is_admin(user_id):
                await query.answer("این بخش فقط برای پلیس است.", show_alert=True)
                return
            await query.answer()
            await render_user_picker(query, user_id, "arrest", 0)
            return

        if action == "summon":
            if role != "judge" and not is_admin(user_id):
                await query.answer("این بخش فقط برای قاضی است.", show_alert=True)
                return
            await query.answer()
            await render_user_picker(query, user_id, "summon", 0)
            return

        if action == "verdict":
            if role != "judge" and not is_admin(user_id):
                await query.answer("این بخش فقط برای قاضی است.", show_alert=True)
                return
            await query.answer()
            await render_user_picker(query, user_id, "verdict", 0)
            return

        if action == "assignrole":
            if not is_admin(user_id):
                await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
                return
            await query.answer()
            await render_pick_mode(query, "assignrole", USER_PICK_TITLES["assignrole"])
            return

        if action == "removerole":
            if not is_admin(user_id):
                await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
                return
            await query.answer()
            await render_pick_mode(query, "removerole", USER_PICK_TITLES["removerole"])
            return

        if action.startswith("editsalary:"):
            if not is_admin(user_id):
                await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
                return
            role_key = action.split(":")[1]
            context.user_data["pending_gov"] = {"flow": "editsalary", "stage": "amount", "role": role_key}
            await query.answer()
            await _answer(
                query, f"مبلغ حقوق جدید برای {ROLE_NAMES.get(role_key, role_key)} رو بفرست (فقط رقم):",
                InlineKeyboardMarkup([[_back("m:adminsalaries")]]),
            )
            return

        if action == "payallsalaries":
            if not is_admin(user_id):
                await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
                return
            paid = await pay_role_salaries(context)
            await query.answer(f"✅ حقوق {len(paid)} نفر پرداخت شد.", show_alert=True)
            await render_adminsalaries(query, user_id)
            return

        if action == "lookuprecord":
            if role != "judge" and not is_admin(user_id):
                await query.answer("این بخش فقط برای قاضی یا مدیر است.", show_alert=True)
                return
            await query.answer()
            await render_pick_mode(query, "lookuprecord", USER_PICK_TITLES["lookuprecord"])
            return

        if action.startswith("searchpurpose:"):
            purpose = action.split(":", 1)[1]
            check = USER_PICK_PERMISSION.get(purpose)
            if not check or not check(user_id):
                await query.answer("دسترسی نداری.", show_alert=True)
                return
            context.user_data["pending_gov"] = {"flow": "searchpurpose", "purpose": purpose, "stage": "identifier"}
            await query.answer()
            await _answer(
                query, "🔍 آیدی عددی یا یوزرنیم (بدون @) کاربر مورد نظر رو بفرست:",
                InlineKeyboardMarkup([[_back(USER_PICK_BACK.get(purpose, "m:adminroles"))]]),
            )
            return

        if action == "searchuser":
            if not is_admin(user_id):
                await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
                return
            context.user_data["pending_bank"] = {"flow": "searchuser", "stage": "identifier"}
            await query.answer()
            await _answer(
                query, "🔍 آیدی عددی یا یوزرنیم (بدون @) کاربر مورد نظر رو بفرست:",
                InlineKeyboardMarkup([[_back("m:adminbank")]]),
            )
            return

        if action == "bankdepositcard":
            if not is_admin(user_id):
                await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
                return
            context.user_data["pending_bank"] = {"flow": "depositcard", "stage": "card"}
            await query.answer()
            await _answer(
                query, "💳 شماره کارت ۱۶ رقمی مقصد رو بفرست:",
                InlineKeyboardMarkup([[_back("m:adminbank")]]),
            )
            return

        if action == "setloancap":
            if not is_admin(user_id):
                await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
                return
            context.user_data["pending_bank"] = {"flow": "setloancap", "stage": "amount"}
            await query.answer()
            await _answer(
                query,
                f"ضریب سقف وام فعلی: {get_loan_max_multiplier()}×\n"
                "عدد جدید رو بفرست (مثلاً 3 یعنی سقف وام = ۳ برابر امتیاز اعتباری):",
                InlineKeyboardMarkup([[_back("m:adminbank")]]),
            )
            return

    if data.startswith("usearch:"):
        if not is_admin(user_id):
            await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
            return
        target_id = int(data.split(":")[1])
        await query.answer()
        await render_user_search_panel(query, user_id, target_id)
        return

    if data.startswith("usearchfreeze:"):
        if not is_admin(user_id):
            await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
            return
        target_id = int(data.split(":")[1])
        target = get_user(target_id)
        if not target:
            await query.answer("کاربر پیدا نشد.", show_alert=True)
            return
        new_state = 0 if target.get("bank_frozen", 0) == 1 else 1
        update_user(target_id, bank_frozen=new_state)
        if new_state == 1:
            await query.answer("🧊 حساب مسدود شد.", show_alert=True)
            note = "🧊 حساب بانکی شما از طرف مدیریت مسدود شد."
        else:
            await query.answer("🔓 حساب رفع مسدودی شد.", show_alert=True)
            note = "🔓 حساب بانکی شما از طرف مدیریت از حالت مسدودی خارج شد."
        try:
            await context.bot.send_message(target_id, note)
        except Exception:
            pass
        await render_user_search_panel(query, user_id, target_id)
        return

    if data.startswith("usearchcharge:") or data.startswith("usearchdeduct:"):
        if not is_admin(user_id):
            await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
            return
        kind, target_str = data.split(":")
        context.user_data["pending_bank"] = {
            "flow": "searchcharge" if kind == "usearchcharge" else "searchdeduct",
            "stage": "amount", "target_id": int(target_str),
        }
        await query.answer()
        verb = "شارژ" if kind == "usearchcharge" else "کسر"
        await _answer(
            query, f"مبلغ مورد نظر برای {verb} حساب رو بفرست (فقط رقم):",
            InlineKeyboardMarkup([[_back(f"usearch:{target_str}")]]),
        )
        return

    if data.startswith("usearchrole:"):
        if not is_admin(user_id):
            await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
            return
        target_id = int(data.split(":")[1])
        target = get_user(target_id)
        if not target:
            await query.answer("کاربر پیدا نشد.", show_alert=True)
            return
        target_label = target.get("username") or target_id
        kb_rows = [
            [_btn(f"{ROLE_ICONS[r]} {ROLE_NAMES[r]}", f"usearchsetrole:{target_id}:{r}", style="primary")]
            for r in GOV_ROLES
        ]
        kb_rows.append([_back(f"usearch:{target_id}")])
        await query.answer()
        await _answer(query, f"مقام مورد نظر برای {target_label} رو انتخاب کن:", InlineKeyboardMarkup(kb_rows))
        return

    if data.startswith("usearchsetrole:"):
        if not is_admin(user_id):
            await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
            return
        _, target_str, role = data.split(":")
        target_id = int(target_str)
        set_gov_role(target_id, role, user_id)
        await query.answer(f"✅ مقام {ROLE_NAMES[role]} تعیین شد.", show_alert=True)
        try:
            await context.bot.send_message(
                target_id, f"{ROLE_ICONS[role]} تبریک! شما به مقام {ROLE_NAMES[role]} منصوب شدید."
            )
        except Exception:
            pass
        await render_user_search_panel(query, user_id, target_id)
        return

    if data.startswith("usearchrolerm:"):
        if not is_admin(user_id):
            await query.answer("این بخش فقط برای مدیران است.", show_alert=True)
            return
        target_id = int(data.split(":")[1])
        old_role = get_gov_role(target_id)
        if not old_role:
            await query.answer("این کاربر اصلاً مقامی نداره.", show_alert=True)
            return
        remove_gov_role(target_id)
        target = get_user(target_id)
        target_label = (target.get("username") or target_id) if target else target_id
        await query.answer(f"✅ مقام {ROLE_NAMES.get(old_role, old_role)} از {target_label} گرفته شد.", show_alert=True)
        try:
            await context.bot.send_message(target_id, f"⚠️ شما از مقام {ROLE_NAMES.get(old_role, old_role)} عزل شدید.")
        except Exception:
            pass
        await render_user_search_panel(query, user_id, target_id)
        return

    if data.startswith("doact:"):
        _, action, _ = data.split(":")
        fn = SIMPLE_ACTIONS.get(action)
        if fn:
            msg = await fn(user_id)
            await query.answer(msg[:200], show_alert=True)
            # صفحه‌ی مربوطه رو دوباره رسم کن تا وضعیت بروز بشه
            back_map = {
                "sleep": render_life, "eat": render_life, "gym": render_life, "restaurant": render_life,
                "fish": render_fun, "mine": render_fun, "farm": render_fun, "puzzle": render_fun,
                "havechild": render_family, "payroll": render_company,
                "study": render_school, "buyinsurance": render_insurance,
            }
            renderer = back_map.get(action)
            if renderer:
                await renderer(query, user_id)
        return

    if data.startswith("amt:"):
        _, action, extra, value = data.split(":")
        await _handle_amount(query, user_id, action, extra, int(value))
        return
    if data.startswith("amtcustom:"):
        await query.answer()
        _, action, extra = data.split(":")
        context.user_data["pending_amount"] = {"action": action, "extra": extra}
        await _answer(query, "✏️ یک عدد بفرست (فقط رقم، بدون کاما):", InlineKeyboardMarkup([[_back()]]))
        return
    if data.startswith("qty:"):
        _, action, extra, value = data.split(":")
        await _handle_qty(query, user_id, action, extra, int(value))
        return
    if data.startswith("qtycustom:"):
        await query.answer()
        _, action, extra = data.split(":")
        context.user_data["pending_qty"] = {"action": action, "extra": extra}
        await _answer(query, "✏️ یک عدد بفرست (فقط رقم):", InlineKeyboardMarkup([[_back()]]))
        return


async def _handle_amount(query, user_id, action, extra, value):
    if action == "dep":
        msg = await do_deposit(user_id, value)
        await query.answer(msg[:200], show_alert=True)
        await render_bank(query, user_id)
    elif action == "with":
        msg = await do_withdraw(user_id, value)
        await query.answer(msg[:200], show_alert=True)
        await render_bank(query, user_id)
    elif action == "loan":
        msg = await do_loan(user_id, value)
        await query.answer(msg[:200], show_alert=True)
        await render_bank(query, user_id)
    elif action == "payl":
        msg = await do_payloan(user_id, value)
        await query.answer(msg[:200], show_alert=True)
        await render_bank(query, user_id)
    elif action == "cinv":
        msg = await do_companyinvest(user_id, value)
        await query.answer(msg[:200], show_alert=True)
        await render_company(query, user_id)
    elif action == "cityfund":
        if not query.message or query.message.chat.type == "private":
            await query.answer("🏙️ این عملیات فقط داخل گروه انجام می‌شه.", show_alert=True)
            return
        u = get_user(user_id)
        city = _city_for_query(query)
        if value <= 0:
            await query.answer("مبلغ نامعتبره.", show_alert=True)
            return
        if not city:
            await query.answer("این گروه هنوز شهر نیست.", show_alert=True)
            return
        if value > u["cash"]:
            await query.answer("پول نقد کافی نداری.", show_alert=True)
            return
        with db() as conn:
            conn.execute("UPDATE cities SET budget=budget+? WHERE chat_id=?", (value, query.message.chat.id))
        update_user(user_id, cash=u["cash"] - value)
        log_tx(user_id, "city_fund", -value, city["name"])
        await query.answer(f"✅ {fmt_money(value)} به بودجه شهر اضافه شد.", show_alert=True)
        await render_city(query, user_id)


async def _handle_qty(query, user_id, action, extra, value):
    if action == "buyitem":
        msg = await do_buy_item(user_id, int(extra), value)
        await query.answer(msg[:200], show_alert=True)
        await render_market(query, user_id)
    elif action == "stockbuy":
        msg = await do_stock_trade(user_id, extra, value, "buy")
        await query.answer(msg[:200], show_alert=True)
        await render_stock_detail(query, user_id, extra)
    elif action == "stocksell":
        msg = await do_stock_trade(user_id, extra, value, "sell")
        await query.answer(msg[:200], show_alert=True)
        await render_stock_detail(query, user_id, extra)


async def on_bank_pending_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = context.user_data.get("pending_bank")
    if not pending:
        return
    user_id = update.effective_user.id
    if not is_admin(user_id):
        context.user_data.pop("pending_bank", None)
        return
    text = (update.message.text or "").strip()
    flow = pending["flow"]

    if flow in ("chargeaccount", "deductaccount"):
        amount_text = text.replace(",", "")
        if not amount_text.isdigit():
            await update.message.reply_text("فقط عدد بفرست.")
            return
        amount = int(amount_text)
        target_id = pending["target_id"]
        target = get_user(target_id)
        context.user_data.pop("pending_bank", None)
        if not target:
            await update.message.reply_text("کاربر پیدا نشد.")
            return
        if flow == "chargeaccount":
            new_bank = target["bank"] + amount
            update_user(target_id, bank=new_bank)
            msg = f"✅ {fmt_money(amount)} به حساب {target.get('username') or target_id} شارژ شد."
            notify = f"💰 حساب بانکی شما از طرف مدیریت شارژ شد: {fmt_money(amount)}\nموجودی بانکی فعلی: {fmt_money(new_bank)}"
        else:
            new_bank = max(0, target["bank"] - amount)
            update_user(target_id, bank=new_bank)
            msg = f"✅ {fmt_money(amount)} از حساب {target.get('username') or target_id} کسر شد."
            notify = f"💸 از حساب بانکی شما از طرف مدیریت مبلغی کسر شد: {fmt_money(amount)}\nموجودی بانکی فعلی: {fmt_money(new_bank)}"
        log_tx(target_id, "admin_bank_adjust", amount if flow == "chargeaccount" else -amount, "توسط مدیریت")
        await update.message.reply_text(msg)
        try:
            await context.bot.send_message(target_id, notify)
        except Exception:
            pass
        return

    if flow == "depositcard":
        if pending["stage"] == "card":
            card = text.replace("-", "").replace(" ", "")
            if not card.isdigit() or len(card) != 16:
                await update.message.reply_text("شماره کارت نامعتبره. یه شماره کارت ۱۶ رقمی بفرست.")
                return
            with db() as conn:
                row = conn.execute("SELECT * FROM users WHERE card_number=?", (card,)).fetchone()
            if not row:
                await update.message.reply_text("همچین کارتی پیدا نشد.")
                return
            pending.update({"stage": "amount", "card": card})
            await update.message.reply_text("مبلغ واریزی رو بفرست (فقط رقم):")
            return
        if pending["stage"] == "amount":
            amount_text = text.replace(",", "")
            if not amount_text.isdigit():
                await update.message.reply_text("فقط عدد بفرست.")
                return
            amount = int(amount_text)
            with db() as conn:
                row = conn.execute("SELECT * FROM users WHERE card_number=?", (pending["card"],)).fetchone()
            context.user_data.pop("pending_bank", None)
            if not row:
                await update.message.reply_text("کارت دیگه معتبر نیست.")
                return
            target = dict(row)
            new_bank = target["bank"] + amount
            update_user(target["user_id"], bank=new_bank)
            log_tx(target["user_id"], "admin_bank_adjust", amount, "واریز مستقیم مدیریت با شماره کارت")
            await update.message.reply_text(
                f"✅ {fmt_money(amount)} به کارت {format_card_number(pending['card'])} واریز شد."
            )
            try:
                await context.bot.send_message(
                    target["user_id"],
                    f"💰 حساب بانکی شما از طرف مدیریت شارژ شد: {fmt_money(amount)}\n"
                    f"موجودی بانکی فعلی: {fmt_money(new_bank)}",
                )
            except Exception:
                pass
            return
        return

    if flow == "setloancap":
        if not text.isdigit() or int(text) <= 0:
            await update.message.reply_text("یه عدد مثبت بفرست.")
            return
        set_setting("loan_max_multiplier", text)
        context.user_data.pop("pending_bank", None)
        await update.message.reply_text(f"✅ ضریب سقف وام روی {text}× تنظیم شد.")
        return

    if flow == "searchuser":
        target = resolve_user_by_identifier(text)
        if not target:
            await update.message.reply_text("چنین کاربری پیدا نشد. دوباره امتحان کن.")
            return
        context.user_data.pop("pending_bank", None)
        built = build_user_search_panel(target["user_id"])
        if not built:
            await update.message.reply_text("کاربر پیدا نشد.")
            return
        text_out, kb = built
        await update.message.reply_text(text_out, reply_markup=kb, parse_mode="Markdown")
        return

    if flow in ("searchcharge", "searchdeduct"):
        amount_text = text.replace(",", "")
        if not amount_text.isdigit():
            await update.message.reply_text("فقط عدد بفرست.")
            return
        amount = int(amount_text)
        target_id = pending["target_id"]
        target = get_user(target_id)
        context.user_data.pop("pending_bank", None)
        if not target:
            await update.message.reply_text("کاربر پیدا نشد.")
            return
        if flow == "searchcharge":
            new_bank = target["bank"] + amount
            update_user(target_id, bank=new_bank)
            msg = f"✅ {fmt_money(amount)} به حساب {target.get('username') or target_id} شارژ شد."
            notify = f"💰 حساب بانکی شما از طرف مدیریت شارژ شد: {fmt_money(amount)}\nموجودی بانکی فعلی: {fmt_money(new_bank)}"
            tx_amount = amount
        else:
            new_bank = max(0, target["bank"] - amount)
            update_user(target_id, bank=new_bank)
            msg = f"✅ {fmt_money(amount)} از حساب {target.get('username') or target_id} کسر شد."
            notify = f"💸 از حساب بانکی شما از طرف مدیریت مبلغی کسر شد: {fmt_money(amount)}\nموجودی بانکی فعلی: {fmt_money(new_bank)}"
            tx_amount = -amount
        log_tx(target_id, "admin_bank_adjust", tx_amount, "توسط مدیریت (جستجوی کاربر)")
        await update.message.reply_text(msg)
        built = build_user_search_panel(target_id)
        if built:
            text_out, kb = built
            await update.message.reply_text(text_out, reply_markup=kb, parse_mode="Markdown")
        try:
            await context.bot.send_message(target_id, notify)
        except Exception:
            pass
        return


async def on_gov_pending_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = context.user_data.get("pending_gov")
    if not pending:
        return
    user_id = update.effective_user.id
    role = get_gov_role(user_id)
    text = (update.message.text or "").strip()
    flow = pending["flow"]

    if flow == "arrest":
        if role != "police" and not is_admin(user_id):
            context.user_data.pop("pending_gov", None)
            return
        if pending["stage"] == "reason":
            pending.update({"stage": "duration", "reason": text})
            await update.message.reply_text("\u23f1 مدت بازداشت رو به دقیقه بفرست (فقط رقم):")
            return
        if pending["stage"] == "duration":
            if not text.isdigit():
                await update.message.reply_text("فقط عدد بفرست.")
                return
            duration = int(text)
            context.user_data.pop("pending_gov", None)
            msg = await do_arrest(user_id, pending["target_id"], pending["reason"], duration, context)
            await update.message.reply_text(msg)
            return
        return

    if flow == "summon":
        if role != "judge" and not is_admin(user_id):
            context.user_data.pop("pending_gov", None)
            return
        if pending["stage"] == "datetime":
            pending.update({"stage": "reason", "scheduled_at": text})
            await update.message.reply_text("\U0001f4c4 دلیل احضار رو بنویس:")
            return
        if pending["stage"] == "reason":
            context.user_data.pop("pending_gov", None)
            msg = await do_court_summon(user_id, pending["target_id"], pending["scheduled_at"], text, context)
            await update.message.reply_text(msg)
            return
        return

    if flow == "verdict":
        if role != "judge" and not is_admin(user_id):
            context.user_data.pop("pending_gov", None)
            return
        if pending["stage"] == "fine":
            amount_text = text.replace(",", "")
            if not amount_text.isdigit():
                await update.message.reply_text("فقط عدد بفرست.")
                return
            pending["fine"] = int(amount_text)
            needs_duration = pending["vtype"] in ("detention_fine", "prison_fine")
            pending["stage"] = "duration" if needs_duration else "reason"
            await update.message.reply_text("\u23f1 مدت زمان رو به دقیقه بفرست:" if needs_duration else "\U0001f4c4 دلیل حکم رو بنویس:")
            return
        if pending["stage"] == "duration":
            if not text.isdigit():
                await update.message.reply_text("فقط عدد بفرست.")
                return
            pending["duration"] = int(text)
            pending["stage"] = "reason"
            await update.message.reply_text("\U0001f4c4 دلیل حکم رو بنویس:")
            return
        if pending["stage"] == "reason":
            fine = pending.get("fine")
            duration = pending.get("duration")
            target_id = pending["target_id"]
            vtype = pending["vtype"]
            context.user_data.pop("pending_gov", None)
            msg = await do_verdict(user_id, target_id, vtype, fine, duration, text, context)
            await update.message.reply_text(msg)
            return
        return

    if flow == "editsalary":
        if not is_admin(user_id):
            context.user_data.pop("pending_gov", None)
            return
        if not text.isdigit():
            await update.message.reply_text("فقط عدد بفرست.")
            return
        role_key = pending["role"]
        set_role_salary(role_key, int(text))
        context.user_data.pop("pending_gov", None)
        await update.message.reply_text(f"\u2705 حقوق {ROLE_NAMES.get(role_key, role_key)} روی {fmt_money(int(text))} تنظیم شد.")
        return

    if flow == "searchpurpose":
        purpose = pending["purpose"]
        check = USER_PICK_PERMISSION.get(purpose)
        if not check or not check(user_id):
            context.user_data.pop("pending_gov", None)
            return
        target = resolve_user_by_identifier(text)
        if not target:
            await update.message.reply_text("چنین کاربری پیدا نشد. دوباره امتحان کن.")
            return
        context.user_data.pop("pending_gov", None)
        target_id = target["user_id"]
        target_label = target.get("username") or target_id

        if purpose == "assignrole":
            kb_rows = [
                [_btn(f"{ROLE_ICONS[r]} {ROLE_NAMES[r]}", f"gov:setrole:{target_id}:{r}", style="primary")]
                for r in GOV_ROLES
            ]
            kb_rows.append([_back("m:adminroles")])
            await update.message.reply_text(
                f"مقام مورد نظر برای {target_label} رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(kb_rows)
            )
            return

        if purpose == "removerole":
            old_role = get_gov_role(target_id)
            if not old_role:
                await update.message.reply_text("این کاربر اصلاً مقامی نداره.")
                return
            remove_gov_role(target_id)
            await update.message.reply_text(f"✅ مقام {ROLE_NAMES.get(old_role, old_role)} از {target_label} گرفته شد.")
            try:
                await context.bot.send_message(target_id, f"⚠️ شما از مقام {ROLE_NAMES.get(old_role, old_role)} عزل شدید.")
            except Exception:
                pass
            return

        if purpose == "lookuprecord":
            records = get_judicial_records(target_id)
            if not records:
                lines = [f"📋 هیچ سابقه‌ای برای {target_label} ثبت نشده."]
            else:
                lines = [f"📋 سوابق قضایی {target_label}:\n"]
                for r in records:
                    issuer = get_user(r["issuer_id"]) if r["issuer_id"] else None
                    issuer_label = (issuer.get("username") or r["issuer_id"]) if issuer else "سیستم"
                    detail = f" ({r['detail']})" if r["detail"] else ""
                    lines.append(
                        f"{JUDICIAL_KIND_LABELS.get(r['kind'], r['kind'])} — {r['reason']}{detail} — "
                        f"صادرکننده: {issuer_label} — {r['created_at']}"
                    )
            await update.message.reply_text("\n".join(lines)[:4000])
            return

        if purpose == "arrest":
            if target_id == user_id:
                await update.message.reply_text("نمی‌تونی خودتو دستگیر کنی!")
                return
            context.user_data["pending_gov"] = {"flow": "arrest", "stage": "reason", "target_id": target_id}
            await update.message.reply_text(f"📄 دلیل دستگیری {target_label} رو بنویس:")
            return

        if purpose == "summon":
            context.user_data["pending_gov"] = {"flow": "summon", "stage": "datetime", "target_id": target_id}
            await update.message.reply_text(
                f"📅 تاریخ و ساعت دادگاه برای {target_label} رو بنویس (مثلاً 1404/06/01 ساعت 16:00):"
            )
            return

        if purpose == "verdict":
            kb_rows = [
                [_btn(label, f"gov:vtype:{target_id}:{vt}", style="success" if vt == "acquit" else "danger")]
                for vt, label in VERDICT_TYPES.items()
            ]
            kb_rows.append([_back("m:judgepanel")])
            await update.message.reply_text(
                f"⚖️ نوع حکم برای {target_label} رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(kb_rows)
            )
            return
        return


async def on_admin_pending_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = context.user_data.get("pending_admin")
    if not pending:
        return
    if not is_admin(update.effective_user.id):
        context.user_data.pop("pending_admin", None)
        return
    text = (update.message.text or "").strip()
    action = pending["action"]

    if action == "addchannel":
        resolved, err = await resolve_and_validate_channel(context, text)
        if err:
            await update.message.reply_text(f"❌ {err}")
            return
        context.user_data["pending_admin"] = {"action": "addchannel", "stage": "confirm", **resolved}
        kb = InlineKeyboardMarkup([
            [_btn("✅ تایید و افزودن", "adm:confirmaddchannel", style="success")],
            [_back("m:adminforcejoin")],
        ])
        await update.message.reply_text(
            f"شناسایی شد: {resolved['title']}\nبرای افزودنش به لیست عضویت اجباری تایید کن:", reply_markup=kb
        )
        return

    if pending.get("stage") == "amount" and pending.get("action") in ("addcash", "subcash"):
        amount_text = text.replace(",", "")
        if not amount_text.isdigit():
            await update.message.reply_text("فقط عدد بفرست.")
            return
        amount = int(amount_text)
        target_id = pending["target_id"]
        target = get_user(target_id)
        context.user_data.pop("pending_admin", None)
        if not target:
            await update.message.reply_text("کاربر پیدا نشد.")
            return
        if pending["action"] == "addcash":
            update_user(target_id, cash=target["cash"] + amount)
            msg = f"➕ {fmt_money(amount)} به موجودی اضافه شد."
        else:
            update_user(target_id, cash=max(0, target["cash"] - amount))
            msg = f"➖ {fmt_money(amount)} از موجودی کم شد."
        await update.message.reply_text("✅ عملیات انجام شد: " + msg)
        try:
            await context.bot.send_message(target_id, "🛠️ مدیریت ربات یک تغییر موجودی روی حساب شما اعمال کرد.")
        except Exception:
            pass
        return

    if pending["stage"] == "target":
        target = resolve_user_by_identifier(text)
        if not target:
            await update.message.reply_text("چنین کاربری پیدا نشد. دوباره امتحان کن.")
            return
        if action == "ban":
            update_user(target["user_id"], banned=1)
            context.user_data.pop("pending_admin", None)
            await update.message.reply_text(f"✅ کاربر {target.get('username') or target['user_id']} بن شد.")
            try:
                await context.bot.send_message(target["user_id"], "🚫 حساب شما از طرف مدیریت بن شد.")
            except Exception:
                pass
            return
        if action == "unban":
            update_user(target["user_id"], banned=0)
            context.user_data.pop("pending_admin", None)
            await update.message.reply_text(f"✅ کاربر {target.get('username') or target['user_id']} رفع بن شد.")
            try:
                await context.bot.send_message(target["user_id"], "✅ حساب شما از طرف مدیریت از بن خارج شد.")
            except Exception:
                pass
            return
        if action in ("addbal", "subbal"):
            context.user_data["pending_admin"] = {"action": action, "stage": "amount", "target_id": target["user_id"]}
            label = target.get("username") or target["user_id"]
            verb = "افزایش" if action == "addbal" else "کاهش"
            await update.message.reply_text(f"مبلغ مورد نظر برای {verb} موجودی {label} رو بفرست (فقط رقم):")
            return
        return

    if pending["stage"] == "amount":
        amount_text = text.replace(",", "")
        if not amount_text.isdigit():
            await update.message.reply_text("فقط عدد بفرست.")
            return
        amount = int(amount_text)
        target_id = pending["target_id"]
        target = get_user(target_id)
        context.user_data.pop("pending_admin", None)
        if not target:
            await update.message.reply_text("کاربر پیدا نشد.")
            return
        if action == "addbal":
            new_cash = target["cash"] + amount
            update_user(target_id, cash=new_cash)
            msg = f"✅ {fmt_money(amount)} به موجودی {target.get('username') or target_id} اضافه شد."
            notify = f"💰 از طرف مدیریت {fmt_money(amount)} برای شما واریز شد.\nموجودی فعلی: {fmt_money(new_cash)}"
        else:
            new_cash = max(0, target["cash"] - amount)
            update_user(target_id, cash=new_cash)
            msg = f"✅ {fmt_money(amount)} از موجودی {target.get('username') or target_id} کم شد."
            notify = f"💸 از طرف مدیریت {fmt_money(amount)} از موجودی بازی شما کم شد.\nموجودی فعلی: {fmt_money(new_cash)}"
        await update.message.reply_text(msg)
        try:
            await context.bot.send_message(target_id, notify)
        except Exception:
            pass
        return


async def on_pending_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتی کاربر بعد از انتخاب «مبلغ دلخواه»/«تعداد دلخواه» یک عدد ساده تایپ می‌کنه."""
    user_id = update.effective_user.id
    ensure_user(user_id, update.effective_user.username)
    is_private = update.effective_chat.type == "private"

    pending_transfer = context.user_data.get("pending_transfer")
    if pending_transfer:
        text_raw = (update.message.text or "").strip()
        if pending_transfer["stage"] == "card":
            card = text_raw.replace("-", "").replace(" ", "")
            if not card.isdigit() or len(card) != 16:
                await update.message.reply_text("شماره کارت نامعتبره. یه شماره کارت ۱۶ رقمی بفرست.")
                return
            with db() as conn:
                row = conn.execute("SELECT * FROM users WHERE card_number=?", (card,)).fetchone()
            if not row:
                await update.message.reply_text("همچین کارتی پیدا نشد. دوباره امتحان کن.")
                return
            if row["user_id"] == user_id:
                await update.message.reply_text("نمی‌تونی به کارت خودت انتقال بدی!")
                return
            context.user_data["pending_transfer"] = {"stage": "amount", "card": card}
            await update.message.reply_text("مبلغ انتقال رو بفرست (فقط رقم):")
            return
        if pending_transfer["stage"] == "amount":
            amount_text = text_raw.replace(",", "")
            if not amount_text.isdigit():
                await update.message.reply_text("فقط عدد بفرست.")
                return
            amount = int(amount_text)
            context.user_data.pop("pending_transfer", None)
            msg = await do_card_transfer(user_id, pending_transfer["card"], amount, context)
            await update.message.reply_text(msg, reply_markup=main_menu_keyboard(user_id, is_private))
            return

    text = (update.message.text or "").strip().replace(",", "")
    if not text.isdigit():
        return  # به پیام‌های غیرعددی کاری نداریم؛ ممکنه دستور دیگه‌ای باشه
    value = int(text)

    pending_amt = context.user_data.pop("pending_amount", None)
    if pending_amt:
        action, extra = pending_amt["action"], pending_amt["extra"]
        fn_map = {"dep": do_deposit, "with": do_withdraw, "loan": do_loan, "payl": do_payloan}
        if action in fn_map:
            msg = await fn_map[action](user_id, value)
        elif action == "cinv":
            msg = await do_companyinvest(user_id, value)
        else:
            msg = "عملیات نامعتبر."
        await update.message.reply_text(msg, reply_markup=main_menu_keyboard(user_id, is_private))
        return

    pending_qty = context.user_data.pop("pending_qty", None)
    if pending_qty:
        action, extra = pending_qty["action"], pending_qty["extra"]
        if action == "buyitem":
            msg = await do_buy_item(user_id, int(extra), value)
        elif action == "stockbuy":
            msg = await do_stock_trade(user_id, extra, value, "buy")
        elif action == "stocksell":
            msg = await do_stock_trade(user_id, extra, value, "sell")
        else:
            msg = "عملیات نامعتبر."
        await update.message.reply_text(msg, reply_markup=main_menu_keyboard(user_id, is_private))
        return


# ----------------------------------------------------------------------------
# دستور /menu و ثبت هندلرها
# ----------------------------------------------------------------------------

async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user.id, update.effective_user.username)
    if not await enforce_maintenance(update, context):
        return
    if not await enforce_force_join(update, context):
        return
    is_private = update.effective_chat.type == "private"
    if not is_private and not city_is_active(update.effective_chat.id):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("🏙️ این ربات هنوز در این شهر فعال نشده. یکی از مدیران ربات باید اول «افزودن شهر» را انجام دهد.")
            return
        kb = InlineKeyboardMarkup([
            [_btn("🏙️ افزودن شهر و فعال‌سازی", "city:register", style="success")],
            [_btn("ℹ️ راهنمای فعال‌سازی", "m:help", style="primary")],
        ])
        sent = await update.message.reply_text("🏙️ *این گروه هنوز شهر بازی نیست.*\n\nبه‌عنوان مالک/مدیر ربات، می‌توانی این گروه را به یک شهر فعال تبدیل کنی.", reply_markup=kb, parse_mode="Markdown")
        set_menu_owner(update.effective_chat.id, sent.message_id, update.effective_user.id)
        return
    kb = main_menu_keyboard(update.effective_user.id, is_private)
    sent = await update.message.reply_text("🎮 *پنل زندگی*\nاز همین پنل، مسیر زندگی و شهر را مدیریت کن 👇", reply_markup=kb, parse_mode="Markdown")
    if not is_private:
        set_menu_owner(update.effective_chat.id, sent.message_id, update.effective_user.id)


MENU_KEYWORDS = {"منو", "منو باز کن", "منوی اصلی", "menu"}

_INVISIBLE_CHARS_RE = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\ufeff]")


def _normalize_text(text: str) -> str:
    """حذف کاراکترهای نامرئی (RTL/LRM/ZWNJ و...) که بعضی کیبوردهای فارسی موبایل اضافه می‌کنن."""
    text = _INVISIBLE_CHARS_RE.sub("", text or "")
    return text.strip()


async def on_mayor_project_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("pending_mayor_project"):
        return
    user_id = update.effective_user.id
    city = None
    if update.effective_chat and update.effective_chat.type in GROUP_TYPES:
        with db() as conn:
            row = conn.execute("SELECT * FROM cities WHERE chat_id=? AND active=1", (update.effective_chat.id,)).fetchone()
            city = dict(row) if row else None
    if not city or city.get("mayor_id") != user_id:
        context.user_data.pop("pending_mayor_project", None)
        await update.message.reply_text("فقط شهردار همین شهر می‌تواند پروژه ثبت کند.")
        return
    parts=(update.message.text or "").strip().rsplit(" ",1)
    if len(parts)!=2 or not parts[1].replace(",","").isdigit():
        await update.message.reply_text("فرمت درست: نام پروژه + فاصله + هزینه. مثال: پارک مرکزی 50000")
        return
    name,cost_s=parts; cost=int(cost_s.replace(",",""))
    if cost<=0 or cost>city["budget"]:
        await update.message.reply_text(f"❌ بودجه شهر کافی نیست. بودجه فعلی: {fmt_money(city['budget'])}")
        return
    with db() as conn:
        score=city["score"]+cost//10000
        conn.execute("UPDATE cities SET budget=budget-?, score=? WHERE chat_id=?",(cost,score,update.effective_chat.id))
    context.user_data.pop("pending_mayor_project",None)
    await update.message.reply_text(f"🏗️ پروژه «{name}» اجرا شد!\n💰 هزینه: {fmt_money(cost)}\n🏆 امتیاز شهر: {score}")


async def on_menu_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = _normalize_text(update.message.text or "")
    if text.lower() not in MENU_KEYWORDS:
        return
    context.user_data.pop("pending_admin", None)
    context.user_data.pop("pending_transfer", None)
    context.user_data.pop("pending_amount", None)
    context.user_data.pop("pending_qty", None)
    context.user_data.pop("pending_gov", None)
    context.user_data.pop("pending_bank", None)
    await cmd_menu(update, context)


def register_menu(app):
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_mayor_project_text), group=3)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_menu_keyword), group=3)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_admin_pending_text),
        group=4,
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_gov_pending_text),
        group=5,
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_bank_pending_text),
        group=6,
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_pending_number), group=7)
    logger.info("Menu (inline keyboard) handlers registered.")


# ----------------------------------------------------------------------------
# اجرای بات
# ----------------------------------------------------------------------------


BOT_COMMANDS = [
    ("start", "شروع بازی"),
    ("help", "راهنمای بازی"),
    ("profile", "پروفایل و وضعیت من"),
    ("setbio", "تغییر بیو"),
    ("jobs", "مشاغل موجود"),
    ("apply", "درخواست شغل"),
    ("work", "کار کردن"),
    ("skills", "مهارت‌ها"),
    ("train", "تمرین مهارت"),
    ("sleep", "خواب و استراحت"),
    ("eat", "غذا خوردن"),
    ("bank", "بانک و اعتبار"),
    ("deposit", "واریز به بانک"),
    ("withdraw", "برداشت از بانک"),
    ("loan", "دریافت وام"),
    ("payloan", "بازپرداخت وام"),
    ("shop", "فروشگاه"),
    ("buyprop", "خرید ملک"),
    ("buyveh", "خرید وسیله نقلیه"),
    ("myassets", "دارایی‌های من"),
    ("mission", "ماموریت‌های روزانه"),
    ("claim", "دریافت جایزه"),
    ("top", "رتبه‌بندی"),
    ("give", "هدیه دادن"),
    ("menu", "باز کردن منوی بازی"),
    ("createcompany", "ساخت شرکت"),
    ("mycompany", "شرکت من"),
    ("companyinvest", "سرمایه‌گذاری در شرکت"),
    ("hire", "استخدام"),
    ("payroll", "پرداخت حقوق"),
    ("companiestop", "برترین شرکت‌ها"),
    ("sell", "فروش در بازار"),
    ("market", "بازار آزاد"),
    ("buyitem", "خرید از بازار"),
    ("mylistings", "آگهی‌های من"),
    ("cancellisting", "لغو آگهی"),
    ("stocks", "بورس"),
    ("buystock", "خرید سهام"),
    ("sellstock", "فروش سهام"),
    ("mystocks", "پرتفوی سهام"),
    ("propose", "خواستگاری"),
    ("accept", "پذیرش پیشنهاد"),
    ("divorce", "طلاق"),
    ("family", "خانواده"),
    ("havechild", "فرزندآوری"),
    ("registercity", "فعال‌سازی شهر"),
    ("cityinfo", "اطلاعات شهر"),
    ("cityfund", "بودجه شهر"),
    ("runformayor", "شروع دستی انتخابات"),
    ("vote", "رأی دادن"),
    ("endelection", "پایان دستی انتخابات"),
    ("cityproject", "پروژه شهری"),
    ("citytop", "رتبه‌بندی شهرها"),
    ("crime", "جرم"),
    ("reportcrime", "گزارش جرم"),
    ("bail", "وثیقه"),
    ("worldstatus", "وضعیت جهان"),
    ("setevent", "تنظیم رویداد جهان"),
    ("gym", "باشگاه"),
    ("fish", "ماهیگیری"),
    ("mine", "معدن"),
    ("farm", "کشاورزی"),
    ("restaurant", "رستوران"),
    ("puzzle", "معما"),
    ("advisor", "مشاور هوش مصنوعی"),
    ("vip", "وی‌آی‌پی"),
    ("buyavatar", "خرید آواتار"),
    ("notifications", "اعلان‌ها"),
    ("addfriend", "افزودن دوست"),
]


async def setup_bot_commands(app):
    from telegram import BotCommand
    commands=[BotCommand(c,d) for c,d in BOT_COMMANDS]
    try:
        await app.bot.set_my_commands(commands)
        logger.info("Bot command list registered: %d commands", len(commands))
    except Exception as e:
        logger.warning("Could not register bot commands: %s", e)



# ==============================================================================
# LIFE RP COMBINED — لایه‌ی دولت ملی + امنیت پنل‌ها
# ترکیب: هسته‌ی LifeBot برای زندگی شخصی + ایده‌های مدیریت HAPO برای شهر/دولت
# ==============================================================================

COMBINED_SCHEMA_VERSION = 1
PANEL_TTL_SECONDS = 15 * 60


def init_combined_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS panel_sessions (
            session_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            panel_type TEXT NOT NULL,
            entity_id INTEGER,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_panel_sessions_user_chat
            ON panel_sessions(user_id, chat_id, panel_type);

        CREATE TABLE IF NOT EXISTS national_state (
            id INTEGER PRIMARY KEY CHECK(id=1),
            name TEXT DEFAULT 'جمهوری Life RP',
            leader_id INTEGER,
            treasury INTEGER DEFAULT 10000000,
            tax_rate INTEGER DEFAULT 10,
            inflation REAL DEFAULT 1.0,
            approval INTEGER DEFAULT 60,
            stability INTEGER DEFAULT 70,
            education INTEGER DEFAULT 50,
            health INTEGER DEFAULT 50,
            security INTEGER DEFAULT 50,
            infrastructure INTEGER DEFAULT 50,
            next_election_at REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS national_elections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT DEFAULT 'open',
            started_at REAL DEFAULT 0,
            finished_at REAL DEFAULT 0,
            winner_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS national_candidates (
            election_id INTEGER,
            user_id INTEGER,
            PRIMARY KEY(election_id,user_id)
        );
        CREATE TABLE IF NOT EXISTS national_votes (
            election_id INTEGER,
            voter_id INTEGER PRIMARY KEY,
            candidate_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS national_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER,
            action TEXT,
            detail TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS city_governance (
            chat_id INTEGER PRIMARY KEY,
            mayor_id INTEGER,
            tax_rate INTEGER DEFAULT 5,
            police INTEGER DEFAULT 50,
            hospital INTEGER DEFAULT 50,
            transit INTEGER DEFAULT 50,
            education INTEGER DEFAULT 50,
            security INTEGER DEFAULT 50,
            development INTEGER DEFAULT 0,
            laws TEXT DEFAULT 'قوانین عمومی شهر'
        );
        """)
        conn.execute("INSERT OR IGNORE INTO national_state(id) VALUES(1)")
        conn.execute("""INSERT OR IGNORE INTO city_governance(chat_id, mayor_id)
                        SELECT chat_id, mayor_id FROM cities WHERE active=1""")


def _new_panel_session(user_id, chat_id, panel_type, entity_id=None):
    import secrets
    sid = secrets.token_urlsafe(18)
    now = time.time()
    with db() as conn:
        conn.execute("DELETE FROM panel_sessions WHERE expires_at < ?", (now,))
        conn.execute(
            "INSERT INTO panel_sessions(session_id,user_id,chat_id,panel_type,entity_id,created_at,expires_at) VALUES(?,?,?,?,?,?,?)",
            (sid, user_id, chat_id, panel_type, entity_id, now, now + PANEL_TTL_SECONDS),
        )
    return sid


def _valid_panel_session(session_id, user_id, chat_id, panel_type, entity_id=None):
    if not session_id:
        return False
    with db() as conn:
        row = conn.execute("SELECT * FROM panel_sessions WHERE session_id=?", (session_id,)).fetchone()
    if not row or row["expires_at"] < time.time():
        return False
    return (row["user_id"] == user_id and row["chat_id"] == chat_id and
            row["panel_type"] == panel_type and row["entity_id"] == entity_id)


def _leader_id():
    with db() as conn:
        row = conn.execute("SELECT leader_id FROM national_state WHERE id=1").fetchone()
    return row["leader_id"] if row else None


def _is_leader(user_id):
    return is_admin(user_id) or _leader_id() == user_id


def _national_state():
    with db() as conn:
        row = conn.execute("SELECT * FROM national_state WHERE id=1").fetchone()
    return dict(row) if row else None


def _national_open_election():
    with db() as conn:
        row = conn.execute("SELECT * FROM national_elections WHERE status='open' ORDER BY id DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def _national_candidates(election_id):
    with db() as conn:
        return conn.execute("""SELECT nc.user_id,u.username,u.avatar,COUNT(nv.voter_id) votes
            FROM national_candidates nc JOIN users u ON u.user_id=nc.user_id
            LEFT JOIN national_votes nv ON nv.election_id=nc.election_id AND nv.candidate_id=nc.user_id
            WHERE nc.election_id=? GROUP BY nc.user_id ORDER BY votes DESC,nc.user_id""", (election_id,)).fetchall()


async def _render_leader_panel(query, user_id):
    if not _is_leader(user_id):
        await query.answer("⛔ این پنل فقط برای رئیس‌جمهور کشور است.", show_alert=True)
        return
    chat_id = query.message.chat.id if query.message else user_id
    sid = _new_panel_session(user_id, chat_id, "leader", None)
    s = _national_state()
    leader = get_user(s["leader_id"]) if s.get("leader_id") else None
    name = (leader or {}).get("username") or "بدون رئیس‌جمهور"
    text = (
        "👑 *دولت کشور — Life RP*\n━━━━━━━━━━━━\n"
        f"👤 رئیس‌جمهور: *{md_escape(str(name))}*\n"
        f"💰 خزانه: *{fmt_money(s['treasury'])}*\n"
        f"💵 مالیات: *{s['tax_rate']}٪*\n"
        f"📈 تورم: *{s['inflation']:.2f}*\n"
        f"⭐ محبوبیت: *{s['approval']}٪*\n"
        f"🛡 امنیت: *{s['security']}٪*\n"
        f"🏥 سلامت: *{s['health']}٪*\n"
        f"🎓 آموزش: *{s['education']}٪*\n"
        f"🛣 زیرساخت: *{s['infrastructure']}٪*\n"
    )
    kb = InlineKeyboardMarkup([
        [_btn("🏛 کابینه", f"lr:{sid}:cabinet", style="primary"), _btn("💰 اقتصاد", f"lr:{sid}:economy", style="primary")],
        [_btn("📜 قوانین", f"lr:{sid}:laws", style="primary"), _btn("🏙 شهرها", f"lr:{sid}:cities", style="primary")],
        [_btn("🛡 امنیت", f"lr:{sid}:security", style="primary"), _btn("🏥 سلامت", f"lr:{sid}:health", style="primary")],
        [_btn("🎓 آموزش", f"lr:{sid}:education", style="primary"), _btn("🛣 زیرساخت", f"lr:{sid}:infra", style="primary")],
        [_btn("🗳 انتخابات", f"lr:{sid}:election", style="success"), _btn("📊 گزارش کشور", f"lr:{sid}:report", style="primary")],
        [_btn("⬅️ بازگشت", "m:main")],
    ])
    await _answer(query, text, kb, parse_mode="Markdown")


async def _handle_leader_callback(query, context, user_id, data):
    parts = data.split(":")
    if len(parts) < 3:
        return False
    sid, action = parts[1], parts[2]
    chat_id = query.message.chat.id if query.message else user_id
    if not _valid_panel_session(sid, user_id, chat_id, "leader", None):
        await query.answer("🔒 این پنل منقضی شده یا متعلق به شما نیست. /menu را باز کنید.", show_alert=True)
        return True
    if not _is_leader(user_id):
        await query.answer("⛔ دسترسی نداری.", show_alert=True)
        return True
    s = _national_state()
    if action == "election":
        e = _national_open_election()
        if not e:
            with db() as conn:
                now = time.time()
                conn.execute("INSERT INTO national_elections(status,started_at) VALUES('open',?)", (now,))
            await query.answer("🗳️ انتخابات ملی آغاز شد.", show_alert=True)
        else:
            await query.answer("یک انتخابات ملی در حال برگزاری است.", show_alert=True)
        await _render_leader_panel(query, user_id); return True
    labels = {
        "cabinet":"🏛 کابینه: وزارتخانه‌های اقتصاد، سلامت، آموزش، امنیت و زیرساخت فعال‌اند.",
        "economy":f"💰 اقتصاد: خزانه {fmt_money(s['treasury'])} — مالیات {s['tax_rate']}٪ — تورم {s['inflation']:.2f}",
        "laws":"📜 قوانین: قوانین ملی از همین پنل مدیریت می‌شوند و روی اقتصاد و شهرها اثر می‌گذارند.",
        "cities":"🏙 شهرها: شهرداران از انتخابات شهری انتخاب می‌شوند و بودجه شهر را مدیریت می‌کنند.",
        "security":f"🛡 امنیت ملی: {s['security']}٪",
        "health":f"🏥 سلامت ملی: {s['health']}٪",
        "education":f"🎓 آموزش ملی: {s['education']}٪",
        "infra":f"🛣 زیرساخت ملی: {s['infrastructure']}٪",
        "report":f"📊 گزارش کشور\n\nمحبوبیت: {s['approval']}٪\nثبات: {s['stability']}٪\nتورم: {s['inflation']:.2f}\nامنیت: {s['security']}٪",
    }
    await query.answer(labels.get(action, "بخش نامعتبر است."), show_alert=True)
    return True


async def _render_city_mayor_combined(query, user_id):
    city = _city_for_query(query)
    if not city or city.get("mayor_id") != user_id:
        await query.answer("⛔ این دفتر فقط برای شهردار همین شهر است.", show_alert=True); return
    gid = query.message.chat.id
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO city_governance(chat_id,mayor_id) VALUES(?,?)", (gid,user_id))
        row = conn.execute("SELECT * FROM city_governance WHERE chat_id=?", (gid,)).fetchone()
    g = dict(row)
    sid = _new_panel_session(user_id, gid, "mayor", gid)
    text = (f"🏛️ *شهرداری {md_escape(city['name'])}*\n━━━━━━━━━━━━\n"
            f"👑 شهردار: شما\n💰 خزانه: *{fmt_money(city['budget'])}*\n"
            f"📈 توسعه: *{g['development']}*\n💸 مالیات: *{g['tax_rate']}٪*\n"
            f"👮 پلیس: *{g['police']}٪* | 🏥 درمان: *{g['hospital']}٪*\n"
            f"🚇 حمل‌ونقل: *{g['transit']}٪* | 🎓 آموزش: *{g['education']}٪*")
    kb=InlineKeyboardMarkup([
        [_btn("💰 بودجه",f"mr:{sid}:budget",style="primary"),_btn("💸 مالیات",f"mr:{sid}:tax",style="primary")],
        [_btn("👮 پلیس",f"mr:{sid}:police",style="primary"),_btn("🏥 درمان",f"mr:{sid}:hospital",style="primary")],
        [_btn("🚇 حمل‌ونقل",f"mr:{sid}:transit",style="primary"),_btn("🎓 آموزش",f"mr:{sid}:education",style="primary")],
        [_btn("📜 قوانین",f"mr:{sid}:laws",style="primary"),_btn("🏗 پروژه", "mayor:project",style="success")],
        [_btn("🗳 انتخابات", "m:city",style="primary"),_btn("⬅️ بازگشت", "m:city")],
    ])
    await _answer(query,text,kb,parse_mode="Markdown")


async def _handle_mayor_callback(query, user_id, data):
    parts=data.split(":")
    if len(parts)<3: return False
    sid,action=parts[1],parts[2]
    gid=query.message.chat.id if query.message else 0
    city=_city_for_query(query)
    if not city or city.get("mayor_id") != user_id or not _valid_panel_session(sid,user_id,gid,"mayor",gid):
        await query.answer("🔒 دسترسی این پنل معتبر نیست.",show_alert=True); return True
    with db() as conn:
        row=conn.execute("SELECT * FROM city_governance WHERE chat_id=?",(gid,)).fetchone()
        g=dict(row) if row else None
        if action in ("police","hospital","transit","education"):
            col=action
            val=min(100,g[col]+5)
            conn.execute(f"UPDATE city_governance SET {col}=? WHERE chat_id=?",(val,gid))
            conn.execute("UPDATE cities SET budget=MAX(0,budget-10000),score=score+1 WHERE chat_id=?",(gid,))
            await query.answer(f"✅ سطح {action} افزایش یافت و هزینه از بودجه شهر پرداخت شد.",show_alert=True)
        elif action=="tax":
            new=min(30,g["tax_rate"]+1)
            conn.execute("UPDATE city_governance SET tax_rate=? WHERE chat_id=?",(new,gid))
            await query.answer(f"💸 مالیات شهر روی {new}٪ قرار گرفت.",show_alert=True)
        elif action=="budget":
            await query.answer(f"💰 بودجه فعلی شهر: {fmt_money(city['budget'])}",show_alert=True)
        elif action=="laws":
            await query.answer(g["laws"] or "قوانین عمومی شهر",show_alert=True)
        else:
            await query.answer("بخش نامعتبر است.",show_alert=True)
    await _render_city_mayor_combined(query,user_id)
    return True



# ==============================================================================
# LIFE RP V2 — لایه تجربه زندگی واقعی + پنل‌های عملیاتی
# این لایه روی تمام سیستم‌های قبلی سوار می‌شود و آن‌ها را به یک جهان قابل بازی
# تبدیل می‌کند. تمام callbackهای V2 دارای session و بررسی مالکیت/نقش هستند.
# ==============================================================================

RP_SESSION_TTL = 20 * 60
RP_DAILY_EVENT_COOLDOWN = 45 * 60


def init_liferp_v2_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS rp_sessions(
            sid TEXT PRIMARY KEY, user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
            kind TEXT NOT NULL, entity_id INTEGER, expires_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_rp_sessions ON rp_sessions(user_id,chat_id,kind);

        CREATE TABLE IF NOT EXISTS rp_city_members(
            chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP, reputation INTEGER DEFAULT 50,
            PRIMARY KEY(chat_id,user_id)
        );
        CREATE TABLE IF NOT EXISTS rp_city_projects(
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL,
            name TEXT NOT NULL, cost INTEGER NOT NULL, effect TEXT NOT NULL,
            progress INTEGER DEFAULT 0, status TEXT DEFAULT 'active', created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rp_city_laws(
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL,
            title TEXT NOT NULL, effect TEXT DEFAULT '', active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rp_national_laws(
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            effect TEXT DEFAULT '', active INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rp_cabinet(
            role TEXT PRIMARY KEY, user_id INTEGER NOT NULL, appointed_by INTEGER NOT NULL,
            appointed_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rp_relationships(
            user_id INTEGER NOT NULL, target_id INTEGER NOT NULL,
            kind TEXT NOT NULL, score INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id,target_id,kind)
        );
        CREATE TABLE IF NOT EXISTS rp_jobs_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            job TEXT, income INTEGER, result TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rp_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            event_key TEXT, title TEXT, body TEXT, reward INTEGER DEFAULT 0,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rp_inventory(
            user_id INTEGER NOT NULL, item_key TEXT NOT NULL, qty INTEGER DEFAULT 0,
            PRIMARY KEY(user_id,item_key)
        );
        CREATE TABLE IF NOT EXISTS rp_needs_log(
            user_id INTEGER PRIMARY KEY, last_tick REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rp_election_meta(
            election_id INTEGER PRIMARY KEY, type TEXT NOT NULL DEFAULT 'national'
        );
        """)


def rp_session(user_id, chat_id, kind, entity_id=None):
    import secrets
    sid = secrets.token_urlsafe(18)
    now=time.time()
    with db() as conn:
        conn.execute('DELETE FROM rp_sessions WHERE expires_at < ?', (now,))
        conn.execute('INSERT INTO rp_sessions VALUES(?,?,?,?,?,?)',
                     (sid,user_id,chat_id,kind,entity_id,now+RP_SESSION_TTL))
    return sid


def rp_session_ok(sid,user_id,chat_id,kind,entity_id=None):
    if not sid: return False
    with db() as conn:
        r=conn.execute('SELECT * FROM rp_sessions WHERE sid=?',(sid,)).fetchone()
    return bool(r and r['expires_at']>=time.time() and r['user_id']==user_id and
                r['chat_id']==chat_id and r['kind']==kind and r['entity_id']==entity_id)


def rp_city(chat_id):
    with db() as conn:
        r=conn.execute('SELECT * FROM cities WHERE chat_id=? AND active=1',(chat_id,)).fetchone()
    return dict(r) if r else None


def rp_join_city(chat_id,user_id):
    if not rp_city(chat_id): return False
    with db() as conn:
        conn.execute('INSERT OR IGNORE INTO rp_city_members(chat_id,user_id) VALUES(?,?)',(chat_id,user_id))
    return True


def rp_apply_needs(user_id):
    now=time.time()
    with db() as conn:
        row=conn.execute('SELECT * FROM users WHERE user_id=?',(user_id,)).fetchone()
        if not row: return
        last=conn.execute('SELECT last_tick FROM rp_needs_log WHERE user_id=?',(user_id,)).fetchone()
        last_t=float(last['last_tick']) if last else now
        hours=max(0,min(24,(now-last_t)/3600))
        if hours < .25: return
        hunger=min(HUNGER_MAX,int(row['hunger']+hours*8))
        energy=max(0,int(row['energy']-hours*4))
        sleep=max(0,int(row['sleep']-hours*5))
        stress=min(STRESS_MAX,int(row['stress']+hours*2))
        happiness=max(0,int(row['happiness']-hours*1.5))
        health=max(1,int(row['health']-(1 if hunger>80 else 0)-(1 if sleep<20 else 0)))
        conn.execute('UPDATE users SET hunger=?,energy=?,sleep=?,stress=?,happiness=?,health=? WHERE user_id=?',
                     (hunger,energy,sleep,stress,happiness,health,user_id))
        conn.execute('INSERT INTO rp_needs_log(user_id,last_tick) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET last_tick=excluded.last_tick', (user_id,now))


def rp_level_xp(xp):
    return max(1, int(xp//100)+1)


def rp_add_item(user_id,key,qty=1):
    with db() as conn:
        conn.execute('INSERT INTO rp_inventory(user_id,item_key,qty) VALUES(?,?,?) ON CONFLICT(user_id,item_key) DO UPDATE SET qty=qty+excluded.qty',(user_id,key,qty))


def rp_get_items(user_id):
    with db() as conn:
        return conn.execute('SELECT * FROM rp_inventory WHERE user_id=? AND qty>0 ORDER BY item_key',(user_id,)).fetchall()


def rp_change_stat(user_id, **fields):
    allowed={'energy','health','happiness','stress','hunger','sleep','intelligence','cash','bank','xp'}
    clean={k:v for k,v in fields.items() if k in allowed}
    if not clean: return
    with db() as conn:
        sets=[]; vals=[]
        for k,v in clean.items():
            if k in {'energy','health','happiness','stress','hunger','sleep'}: v=clamp(int(v),0,100)
            sets.append(f'{k}=?'); vals.append(v)
        vals.append(user_id)
        conn.execute(f'UPDATE users SET {",".join(sets)} WHERE user_id=?',vals)


def rp_add_cash(user_id, amount, note='Life RP'):
    with db() as conn:
        conn.execute('UPDATE users SET cash=cash+? WHERE user_id=?',(int(amount),user_id))
    log_tx(user_id,'rp',int(amount),note)


def rp_city_stats(chat_id):
    c=rp_city(chat_id)
    if not c: return None
    with db() as conn:
        pop=conn.execute('SELECT COUNT(*) c FROM rp_city_members WHERE chat_id=?',(chat_id,)).fetchone()['c']
        active_projects=conn.execute("SELECT COUNT(*) c FROM rp_city_projects WHERE chat_id=? AND status='active'",(chat_id,)).fetchone()['c']
    g=conn.execute('SELECT * FROM city_governance WHERE chat_id=?',(chat_id,)).fetchone() if False else None
    return c,pop,active_projects


def rp_fmt_event(e):
    return f"{e['title']}\n\n{e['body']}"


# ------------------------------ منوی شخصی V2 ------------------------------

def rp_personal_menu(user_id):
    return InlineKeyboardMarkup([
        [_btn('👤 شناسنامه زندگی','v2:p:profile'),_btn('💼 کار و حرفه','v2:p:career')],
        [_btn('🏠 خانه و وسایل','v2:p:home'),_btn('💳 پول و بانک','m:bank')],
        [_btn('🍔 نیازهای روزانه','v2:p:needs'),_btn('🛍 خرید روزانه','v2:p:shop')],
        [_btn('❤️ روابط اجتماعی','v2:p:social'),_btn('🎓 تحصیل و رشد','m:school')],
        [_btn('🎒 کوله و وسایل','v2:p:inventory'),_btn('🎲 اتفاق امروز','v2:p:event')],
        [_btn('🏙 شهر من','v2:city:open'),_btn('🌍 کشور','v2:nation:open')],
        [_btn('🎯 زندگی من','v2:p:actions'),_btn('🏆 رتبه‌بندی','m:top')],
        [_btn('⬅️ منوی اصلی','m:main')]
    ])


async def rp_render_personal(query,user_id):
    rp_apply_needs(user_id); u=ensure_user(user_id,query.from_user.username or query.from_user.first_name)
    nw=net_worth(u); lvl=rp_level_xp(u['xp'])
    text=(f"🌆 *زندگی من — Life RP*\n━━━━━━━━━━━━\n"
          f"👤 {md_escape(u['username'] or str(user_id))}\n🏅 سطح زندگی: *{lvl}*\n"
          f"💰 نقد: *{fmt_money(u['cash'])}* | 🏦 بانک: *{fmt_money(u['bank'])}*\n"
          f"💼 شغل: *{md_escape(get_job_label(u))}*\n🏠 دارایی خالص: *{fmt_money(nw)}*\n\n"
          f"❤️ سلامت {u['health']}٪  ⚡ انرژی {u['energy']}٪\n"
          f"🍗 گرسنگی {u['hunger']}٪  😴 خواب {u['sleep']}٪\n"
          f"😊 شادی {u['happiness']}٪  😰 استرس {u['stress']}٪")
    await _answer(query,text,rp_personal_menu(user_id),parse_mode='Markdown')


async def rp_render_profile(query,user_id):
    u=ensure_user(user_id,query.from_user.username or query.from_user.first_name)
    with db() as conn:
        friends=conn.execute('SELECT COUNT(*) c FROM friendships WHERE user_id=?',(user_id,)).fetchone()['c']
        props=conn.execute('SELECT COUNT(*) c FROM user_properties WHERE user_id=?',(user_id,)).fetchone()['c']
        vehs=conn.execute('SELECT COUNT(*) c FROM user_vehicles WHERE user_id=?',(user_id,)).fetchone()['c']
    text=(f"🪪 *شناسنامه زندگی*\n━━━━━━━━━━━━\nنام: *{md_escape(u['username'] or str(user_id))}*\n"
          f"سن: {u['age']} سال\n💼 {md_escape(get_job_label(u))}\n👥 دوستان: {friends}\n"
          f"🏠 ملک: {props} | 🚗 وسیله: {vehs}\n🧠 هوش: {u['intelligence']}\nXP: {u['xp']}")
    await _answer(query,text,InlineKeyboardMarkup([[_btn('✏️ تغییر بیو','v2:p:bio')],[_back('v2:p:open')]]),parse_mode='Markdown')


async def rp_render_needs(query,user_id):
    rp_apply_needs(user_id); u=get_user(user_id)
    text=(f"❤️ *نیازهای شخصیت*\n\n🏥 سلامت: {stat_bar(u['health'])}\n⚡ انرژی: {stat_bar(u['energy'])}\n"
          f"🍗 گرسنگی: {stat_bar(u['hunger'])}\n😴 خواب: {stat_bar(u['sleep'])}\n"
          f"😊 شادی: {stat_bar(u['happiness'])}\n😰 استرس: {stat_bar(u['stress'])}\n\n"
          "اگر نیازها را نادیده بگیری، کار و روابطت ضعیف می‌شود.")
    kb=InlineKeyboardMarkup([[_btn('🍔 غذا','v2:act:eat'),_btn('😴 خواب','v2:act:sleep')],[_btn('🏋️ ورزش','v2:act:gym'),_btn('🍽 رستوران','v2:act:restaurant')],[_back('v2:p:open')]])
    await _answer(query,text,kb)


async def rp_render_career(query,user_id):
    u=get_user(user_id); rp_apply_needs(user_id)
    lines=['💼 *مسیر شغلی*','']
    for k,j in JOBS.items():
        req=j.get('min_level',0); skill=j.get('skill'); sl=get_skill(user_id,skill)['level'] if skill else 0
        ok=rp_level_xp(u['xp'])>=req and (not skill or sl>=req)
        mark='✅' if ok else '🔒'
        lines.append(f"{mark} *{j['name']}* — 💰 {fmt_money(j['pay'])} / شیفت | نیاز سطح {req}")
    buttons=[]
    for k,j in list(JOBS.items()): buttons.append(_btn(j['name'],f'v2:job:{k}'))
    buttons.append(_btn('🔨 کار کردن','v2:act:work'))
    buttons.append(_btn('⬅️ زندگی من','v2:p:open'))
    await _answer(query,'\n'.join(lines),InlineKeyboardMarkup(_rows(buttons,2)),parse_mode='Markdown')


async def rp_render_home(query,user_id):
    u=get_user(user_id)
    with db() as conn:
        props=conn.execute('SELECT prop_key,COUNT(*) c FROM user_properties WHERE user_id=? GROUP BY prop_key',(user_id,)).fetchall()
        vehs=conn.execute('SELECT veh_key,COUNT(*) c FROM user_vehicles WHERE user_id=? GROUP BY veh_key',(user_id,)).fetchall()
    lines=['🏠 *خانه و وسایل*','']
    if props:
        lines.append('🏠 املاک:')
        for r in props: lines.append(f"• {PROPERTIES.get(r['prop_key'],{}).get('name',r['prop_key'])} ×{r['c']}")
    else: lines.append('🏠 هنوز خانه‌ای نداری.')
    if vehs:
        lines.append('🚗 وسایل نقلیه:')
        for r in vehs: lines.append(f"• {VEHICLES.get(r['veh_key'],{}).get('name',r['veh_key'])} ×{r['c']}")
    kb=InlineKeyboardMarkup([[_btn('🛒 خرید ملک','m:shopprop'),_btn('🚗 خرید وسیله','m:shopveh')],[_btn('🧾 همه دارایی‌ها','m:myassets')],[_back('v2:p:open')]])
    await _answer(query,'\n'.join(lines),kb)


async def rp_render_inventory(query,user_id):
    rows=rp_get_items(user_id)
    lines=['🎒 *کوله و وسایل*','']
    if not rows: lines.append('کوله‌ات خالی است.')
    else:
        for r in rows: lines.append(f"• {r['item_key']} × {r['qty']}")
    await _answer(query,'\n'.join(lines),InlineKeyboardMarkup([[_back('v2:p:open')]]))


async def rp_render_shop(query,user_id):
    kb=InlineKeyboardMarkup([
        [_btn('🥪 ساندویچ — 300','v2:buy:food:300'),_btn('☕ قهوه — 500','v2:buy:coffee:500')],
        [_btn('💊 دارو — 1200','v2:buy:medicine:1200'),_btn('👕 لباس — 2500','v2:buy:clothes:2500')],
        [_btn('📱 موبایل — 12000','v2:buy:phone:12000'),_btn('💻 لپ‌تاپ — 35000','v2:buy:laptop:35000')],
        [_back('v2:p:open')]
    ])
    await _answer(query,'🛍 *فروشگاه زندگی*\n\nخریدهای کوچک روی شادی، انرژی و سبک زندگی اثر می‌گذارند.',kb,parse_mode='Markdown')


async def rp_render_social(query,user_id):
    with db() as conn:
        friends=conn.execute('SELECT f.friend_id,u.username FROM friendships f JOIN users u ON u.user_id=f.friend_id WHERE f.user_id=? ORDER BY u.username LIMIT 20',(user_id,)).fetchall()
    lines=['❤️ *روابط اجتماعی*','']
    lines.append(f'👥 دوستان: {len(friends)}')
    for r in friends: lines.append(f"• {r['username'] or r['friend_id']}")
    kb=InlineKeyboardMarkup([[_btn('➕ افزودن دوست','v2:social:add'),_btn('💌 تعامل با دوست','v2:social:interact')],[_btn('❤️ خواستگاری','v2:social:propose')],[_back('v2:p:open')]])
    await _answer(query,'\n'.join(lines),kb)


async def rp_render_actions(query,user_id):
    kb=InlineKeyboardMarkup([
        [_btn('🚶 رفتن به کار','v2:act:work'),_btn('🛒 خرید','v2:p:shop')],
        [_btn('🏋️ باشگاه','v2:act:gym'),_btn('🎣 تفریح','m:fun')],
        [_btn('💬 تعامل اجتماعی','v2:social:interact'),_btn('🎲 اتفاق تصادفی','v2:p:event')],
        [_back('v2:p:open')]
    ])
    await _answer(query,'🎯 *کارهای امروز*\n\nهر تصمیم روی پول، انرژی، شادی، استرس و روابطت اثر می‌گذارد.',kb,parse_mode='Markdown')


# ------------------------------ رویدادهای زندگی ------------------------------

RP_EVENTS=[
 ('bonus','🎁 پاداش ناگهانی','رئیس از عملکردت راضی شده و یک پاداش کوچک گرفتی.',2500),
 ('traffic','🚗 ترافیک سنگین','رفت‌وآمدت طول کشید و کمی خسته شدی.',0),
 ('friend','🤝 دیدار اتفاقی','در مسیر یک دوست قدیمی را دیدی و حال روحی‌ات بهتر شد.',0),
 ('bill','🧾 قبض غیرمنتظره','یک هزینه پیش‌بینی‌نشده برایت ایجاد شد.',-1800),
 ('idea','💡 ایده درخشان','ایده‌ای به ذهنت رسید؛ هوش و تجربه‌ات بیشتر شد.',0),
]

async def rp_daily_event(query,user_id):
    now=time.time()
    with db() as conn:
        last=conn.execute('SELECT created_at FROM rp_events WHERE user_id=? ORDER BY id DESC LIMIT 1',(user_id,)).fetchone()
    if last and now-float(last['created_at'])<RP_DAILY_EVENT_COOLDOWN:
        remain=int((RP_DAILY_EVENT_COOLDOWN-(now-float(last['created_at'])))/60)+1
        await query.answer(f'⏳ رویداد بعدی حدود {remain} دقیقه دیگر.',show_alert=True); return
    key,title,body,reward=random.choice(RP_EVENTS)
    rp_add_cash(user_id,reward,'رویداد زندگی')
    effects=''
    if key=='traffic': rp_change_stat(user_id,energy=get_user(user_id)['energy']-8,stress=get_user(user_id)['stress']+5); effects='⚡ -8 انرژی | 😰 +5 استرس'
    elif key=='friend': rp_change_stat(user_id,happiness=get_user(user_id)['happiness']+10); effects='😊 +10 شادی'
    elif key=='idea': rp_change_stat(user_id,intelligence=get_user(user_id)['intelligence']+2,xp=get_user(user_id)['xp']+15); effects='🧠 +2 هوش | ⭐ +15 XP'
    elif key=='bill': effects='💸 -1,800 پول'
    elif key=='bonus': effects='💰 +2,500 پول'
    with db() as conn: conn.execute('INSERT INTO rp_events(user_id,event_key,title,body,reward,created_at) VALUES(?,?,?,?,?,?)',(user_id,key,title,body,reward,now))
    await query.answer('🎲 رویداد زندگی اتفاق افتاد!',show_alert=True)
    await _answer(query,f"{title}\n\n{body}\n\n{effects}",InlineKeyboardMarkup([[_btn('🎯 ادامه زندگی','v2:p:open')]]))


# ------------------------------ اعمال شخصی ------------------------------

async def rp_action(query,user_id,action):
    u=get_user(user_id); rp_apply_needs(user_id); u=get_user(user_id)
    if action=='eat':
        if u['cash']<300: msg='💸 پول کافی نداری.'
        else:
            rp_add_cash(user_id,-300,'غذا'); rp_change_stat(user_id,hunger=u['hunger']-35,energy=u['energy']+8,happiness=u['happiness']+3); rp_add_item(user_id,'غذا',1); msg='🍔 غذا خوردی. گرسنگی کم شد و انرژی گرفتی.'
    elif action=='sleep':
        rp_change_stat(user_id,energy=100,sleep=100,stress=u['stress']-20,hunger=u['hunger']+8); msg='😴 یک خواب کامل داشتی؛ انرژی و خواب بهبود یافت.'
    elif action=='gym':
        if u['energy']<15: msg='⚡ انرژی کافی برای باشگاه نداری.'
        else:
            rp_change_stat(user_id,energy=u['energy']-15,health=u['health']+5,happiness=u['happiness']+4,stress=u['stress']-5,xp=u['xp']+10); msg='🏋️ تمرین خوبی داشتی. سلامت و XP بالا رفت.'
    elif action=='restaurant':
        if u['cash']<1500: msg='💸 برای رستوران پول کافی نداری.'
        else:
            rp_add_cash(user_id,-1500,'رستوران'); rp_change_stat(user_id,hunger=u['hunger']-45,happiness=u['happiness']+15,stress=u['stress']-8); msg='🍽️ یک وعده خوب خوردی و حال روحی‌ات بهتر شد.'
    elif action=='work':
        # از منطق موجود استفاده می‌کنیم تا اقتصاد قبلی خراب نشود.
        await act_work(query,user_id); return
    else: msg='عملیات ناشناخته است.'
    await query.answer(msg,show_alert=True); await rp_render_needs(query,user_id)


async def rp_buy(query,user_id,key,price):
    u=get_user(user_id)
    if u['cash']<price: await query.answer('💸 پول کافی نداری.',show_alert=True); return
    rp_add_cash(user_id,-price,'خرید روزمره '+key); rp_add_item(user_id,key,1)
    if key=='food': rp_change_stat(user_id,hunger=u['hunger']-30,energy=u['energy']+5)
    elif key=='coffee': rp_change_stat(user_id,energy=u['energy']+10,stress=u['stress']+3)
    elif key=='medicine': rp_change_stat(user_id,health=u['health']+20)
    elif key=='clothes': rp_change_stat(user_id,happiness=u['happiness']+6)
    elif key=='phone': rp_change_stat(user_id,happiness=u['happiness']+10,intelligence=u['intelligence']+1)
    elif key=='laptop': rp_change_stat(user_id,intelligence=u['intelligence']+3,xp=u['xp']+10)
    await query.answer('✅ خرید انجام شد.',show_alert=True); await rp_render_shop(query,user_id)


async def rp_choose_job(query,user_id,key):
    if key not in JOBS: return
    u=get_user(user_id); j=JOBS[key]
    if rp_level_xp(u['xp'])<j.get('min_level',0): await query.answer('🔒 هنوز سطح لازم را نداری.',show_alert=True); return
    if j.get('skill') and get_skill(user_id,j['skill'])['level']<j.get('min_level',0): await query.answer('🧠 مهارت لازم را نداری.',show_alert=True); return
    update_user(user_id,job=key); await query.answer(f"✅ شغل «{j['name']}» برایت ثبت شد.",show_alert=True); await rp_render_career(query,user_id)


# ------------------------------ شهر / شهرداری V2 ------------------------------

async def rp_city_open(query,user_id):
    if not query.message or query.message.chat.type not in GROUP_TYPES:
        await query.answer('🏙️ پنل شهر را داخل گروه شهری باز کن.',show_alert=True); return
    gid=query.message.chat.id; city=rp_city(gid)
    if not city:
        await query.answer('🏙️ این گروه هنوز شهر فعال ندارد.',show_alert=True); return
    rp_join_city(gid,user_id)
    c,pop,projects=rp_city_stats(gid)
    with db() as conn:
        g=conn.execute('SELECT * FROM city_governance WHERE chat_id=?',(gid,)).fetchone()
        g=dict(g) if g else {'tax_rate':5,'police':50,'hospital':50,'transit':50,'education':50,'development':0}
    mayor=get_user(c.get('mayor_id')) if c.get('mayor_id') else None
    mname=(mayor or {}).get('username') or 'انتخاب نشده'
    text=(f"🏙️ *{md_escape(c['name'])}*\n━━━━━━━━━━━━\n👑 شهردار: {md_escape(str(mname))}\n"
          f"👥 شهروندان ثبت‌شده: *{pop}*\n💰 خزانه: *{fmt_money(c['budget'])}*\n🏗 پروژه فعال: *{projects}*\n"
          f"💸 مالیات {g['tax_rate']}٪ | 👮 {g['police']}٪ | 🏥 {g['hospital']}٪ | 🚇 {g['transit']}٪ | 🎓 {g['education']}٪")
    kb=InlineKeyboardMarkup([[_btn('🗳 انتخابات','m:city'),_btn('📊 آمار شهر','v2:city:stats')],[_btn('🏛 دفتر شهردار','city:mayor')],[_btn('👥 شهروندان','v2:city:citizens')],[_back('v2:p:open')]])
    await _answer(query,text,kb,parse_mode='Markdown')


async def rp_city_stats_view(query,user_id):
    if not query.message or query.message.chat.type not in GROUP_TYPES: return
    c=rp_city(query.message.chat.id)
    if not c: return
    with db() as conn:
        members=conn.execute('SELECT COUNT(*) c FROM rp_city_members WHERE chat_id=?',(query.message.chat.id,)).fetchone()['c']
        laws=conn.execute('SELECT COUNT(*) c FROM rp_city_laws WHERE chat_id=? AND active=1',(query.message.chat.id,)).fetchone()['c']
        projects=conn.execute("SELECT COUNT(*) c FROM rp_city_projects WHERE chat_id=? AND status='active'",(query.message.chat.id,)).fetchone()['c']
    await _answer(query,f"📊 *گزارش شهر {md_escape(c['name'])}*\n\n👥 شهروندان: {members}\n📜 قوانین فعال: {laws}\n🏗 پروژه‌ها: {projects}\n💰 خزانه: {fmt_money(c['budget'])}\n⭐ امتیاز شهر: {c['score']}",InlineKeyboardMarkup([[_back('v2:city:open')]]),parse_mode='Markdown')


async def rp_city_citizens(query,user_id):
    if not query.message or query.message.chat.type not in GROUP_TYPES: return
    with db() as conn:
        rows=conn.execute('SELECT u.user_id,u.username,u.age,u.job,m.reputation FROM rp_city_members m JOIN users u ON u.user_id=m.user_id WHERE m.chat_id=? ORDER BY m.reputation DESC LIMIT 20',(query.message.chat.id,)).fetchall()
    lines=['👥 *شهروندان*','']
    for i,r in enumerate(rows,1): lines.append(f"{i}. {r['username'] or r['user_id']} — {r['age']} سال — {get_job_label(r)} — ⭐{r['reputation']}")
    await _answer(query,'\n'.join(lines) if rows else 'هنوز شهروندی ثبت نشده.',InlineKeyboardMarkup([[_back('v2:city:open')]]),parse_mode='Markdown')


async def rp_mayor_open(query,user_id):
    if not query.message or query.message.chat.type not in GROUP_TYPES: return
    gid=query.message.chat.id; c=rp_city(gid)
    if not c or c.get('mayor_id')!=user_id:
        await query.answer('⛔ فقط شهردار همین شهر دسترسی دارد.',show_alert=True); return
    with db() as conn:
        conn.execute('INSERT OR IGNORE INTO city_governance(chat_id,mayor_id) VALUES(?,?)',(gid,user_id))
        g=dict(conn.execute('SELECT * FROM city_governance WHERE chat_id=?',(gid,)).fetchone())
        proj=conn.execute("SELECT * FROM rp_city_projects WHERE chat_id=? AND status='active' ORDER BY id DESC LIMIT 5",(gid,)).fetchall()
        laws=conn.execute("SELECT * FROM rp_city_laws WHERE chat_id=? AND active=1 ORDER BY id DESC LIMIT 5",(gid,)).fetchall()
    sid=rp_session(user_id,gid,'mayor',gid)
    text=(f"🏛️ *دفتر شهردار — {md_escape(c['name'])}*\n━━━━━━━━━━━━\n💰 خزانه: *{fmt_money(c['budget'])}*\n"
          f"💸 مالیات: {g['tax_rate']}٪\n👮 پلیس: {g['police']}٪ | 🏥 درمان: {g['hospital']}٪\n"
          f"🚇 حمل‌ونقل: {g['transit']}٪ | 🎓 آموزش: {g['education']}٪\n🏗 توسعه: {g['development']}\n"
          f"📜 قوانین فعال: {len(laws)} | پروژه فعال: {len(proj)}")
    kb=InlineKeyboardMarkup([
      [_btn('💰 خزانه',f'v2:mr:{sid}:treasury'),_btn('💸 مالیات',f'v2:mr:{sid}:tax')],
      [_btn('👮 پلیس',f'v2:mr:{sid}:police'),_btn('🏥 درمان',f'v2:mr:{sid}:hospital')],
      [_btn('🚇 حمل‌ونقل',f'v2:mr:{sid}:transit'),_btn('🎓 آموزش',f'v2:mr:{sid}:education')],
      [_btn('🏗 پروژه جدید',f'v2:mr:{sid}:project'),_btn('📜 قانون جدید',f'v2:mr:{sid}:law')],
      [_btn('📊 گزارش شهر',f'v2:mr:{sid}:report'),_btn('🗳 انتخابات', 'city:city')],
      [_back('v2:city:open')]
    ])
    await _answer(query,text,kb,parse_mode='Markdown')


async def rp_mayor_action(query,user_id,sid,action):
    gid=query.message.chat.id if query.message else 0
    if not rp_session_ok(sid,user_id,gid,'mayor',gid): await query.answer('🔒 پنل منقضی یا غیرمجاز است.',show_alert=True); return
    c=rp_city(gid)
    if not c or c.get('mayor_id')!=user_id: await query.answer('⛔ دسترسی شهردار لازم است.',show_alert=True); return
    with db() as conn:
        g=dict(conn.execute('SELECT * FROM city_governance WHERE chat_id=?',(gid,)).fetchone())
        if action in ('police','hospital','transit','education'):
            cost=10000
            if c['budget']<cost: msg='💸 بودجه شهر کافی نیست.'
            else:
                val=min(100,g[action]+5)
                conn.execute(f'UPDATE city_governance SET {action}=? WHERE chat_id=?',(val,gid))
                conn.execute('UPDATE cities SET budget=budget-?,score=score+2 WHERE chat_id=?',(cost,gid))
                msg=f'✅ خدمات {action} ارتقا یافت. هزینه {fmt_money(cost)}.'
        elif action=='tax':
            val=min(30,g['tax_rate']+1); conn.execute('UPDATE city_governance SET tax_rate=? WHERE chat_id=?',(val,gid)); msg=f'💸 مالیات شهر به {val}٪ رسید.'
        elif action=='treasury': msg=f"💰 خزانه شهر: {fmt_money(c['budget'])}"
        elif action=='project':
            # پروژه‌های یک‌کلیکی تا هیچ دکمه‌ای بدون اثر نماند.
            options=[('پارک مرکزی',25000,'شادی شهروندان +5'),('ایستگاه حمل‌ونقل',50000,'حمل‌ونقل +8'),('درمانگاه محلی',60000,'درمان +8'),('مدرسه دولتی',70000,'آموزش +8')]
            kb=InlineKeyboardMarkup([[_btn(f'{n} — {fmt_money(cost)}',f'v2:mrp:{sid}:{i}') ] for i,(n,cost,e) in enumerate(options)])
            kb.inline_keyboard.append([_back('v2:city:open')]); await _answer(query,'🏗 *انتخاب پروژه شهری*',kb,parse_mode='Markdown'); return
        elif action=='law':
            options=[('ممنوعیت زباله در خیابان','محیط زیست +5'),('تخفیف حمل‌ونقل عمومی','رضایت +5'),('مجوز کسب‌وکار آسان','اقتصاد +5')]
            kb=InlineKeyboardMarkup([[_btn(n,f'v2:mrl:{sid}:{i}') ] for i,(n,e) in enumerate(options)]); kb.inline_keyboard.append([_back('v2:city:open')]); await _answer(query,'📜 *قانون جدید را انتخاب کن*',kb,parse_mode='Markdown'); return
        elif action=='report':
            msg=(f"📊 گزارش شهر\nخزانه: {fmt_money(c['budget'])}\nامتیاز: {c['score']}\n"
                 f"پلیس: {g['police']}٪\nدرمان: {g['hospital']}٪\nحمل‌ونقل: {g['transit']}٪\nآموزش: {g['education']}٪")
        else: msg='بخش نامعتبر است.'
    await query.answer(msg,show_alert=True); await rp_mayor_open(query,user_id)


async def rp_mayor_project(query,user_id,sid,index):
    gid=query.message.chat.id; c=rp_city(gid)
    if not rp_session_ok(sid,user_id,gid,'mayor',gid) or not c or c.get('mayor_id')!=user_id: await query.answer('🔒 دسترسی معتبر نیست.',show_alert=True); return
    opts=[('پارک مرکزی',25000,'شادی شهروندان +5'),('ایستگاه حمل‌ونقل',50000,'حمل‌ونقل +8'),('درمانگاه محلی',60000,'درمان +8'),('مدرسه دولتی',70000,'آموزش +8')]
    if not 0<=index<len(opts): return
    name,cost,effect=opts[index]
    with db() as conn:
        if c['budget']<cost: await query.answer('💸 بودجه کافی نیست.',show_alert=True); return
        conn.execute('UPDATE cities SET budget=budget-?,score=score+3 WHERE chat_id=?',(cost,gid))
        conn.execute('INSERT INTO rp_city_projects(chat_id,name,cost,effect,status) VALUES(?,?,?,?,\'done\')',(gid,name,cost,effect))
        if index==1: conn.execute('UPDATE city_governance SET transit=MIN(100,transit+8),development=development+8 WHERE chat_id=?',(gid,))
        elif index==2: conn.execute('UPDATE city_governance SET hospital=MIN(100,hospital+8),development=development+8 WHERE chat_id=?',(gid,))
        elif index==3: conn.execute('UPDATE city_governance SET education=MIN(100,education+8),development=development+8 WHERE chat_id=?',(gid,))
        else: conn.execute('UPDATE city_governance SET development=development+5 WHERE chat_id=?',(gid,))
    await query.answer(f'🏗️ {name} اجرا شد.',show_alert=True); await rp_mayor_open(query,user_id)


async def rp_mayor_law(query,user_id,sid,index):
    gid=query.message.chat.id; c=rp_city(gid)
    if not rp_session_ok(sid,user_id,gid,'mayor',gid) or not c or c.get('mayor_id')!=user_id: await query.answer('🔒 دسترسی معتبر نیست.',show_alert=True); return
    opts=[('ممنوعیت زباله در خیابان','محیط زیست +5'),('تخفیف حمل‌ونقل عمومی','رضایت +5'),('مجوز کسب‌وکار آسان','اقتصاد +5')]
    if not 0<=index<len(opts): return
    title,effect=opts[index]
    with db() as conn: conn.execute('INSERT INTO rp_city_laws(chat_id,title,effect) VALUES(?,?,?)',(gid,title,effect)); conn.execute('UPDATE cities SET score=score+1 WHERE chat_id=?',(gid,))
    await query.answer('📜 قانون ثبت و فعال شد.',show_alert=True); await rp_mayor_open(query,user_id)


# ------------------------------ دولت و انتخابات ملی V2 ------------------------------

async def rp_nation_open(query,user_id):
    s=_national_state()
    leader=get_user(s['leader_id']) if s and s.get('leader_id') else None
    lname=(leader or {}).get('username') or 'بدون رئیس‌جمهور'
    e=_national_open_election()
    text=(f"🌍 *کشور Life RP*\n━━━━━━━━━━━━\n👑 رئیس‌جمهور: *{md_escape(str(lname))}*\n"
          f"💰 خزانه: *{fmt_money(s['treasury'])}*\n💸 مالیات: {s['tax_rate']}٪\n💵 تورم: {s['inflation']:.2f}\n"
          f"⭐ محبوبیت: {s['approval']}٪ | 🛡 ثبات: {s['stability']}٪\n🏥 سلامت {s['health']}٪ | 🎓 آموزش {s['education']}٪\n"
          f"🛣 زیرساخت {s['infrastructure']}٪ | 🛡 امنیت {s['security']}٪")
    kb=InlineKeyboardMarkup([[_btn('🗳 انتخابات ملی','v2:nation:election'),_btn('📊 آمار کشور','v2:nation:stats')],[_btn('📜 قوانین ملی','v2:nation:laws')]])
    if _is_leader(user_id): kb.inline_keyboard.append([_btn('👑 دولت و کابینه','v2:nation:gov')])
    kb.inline_keyboard.append([_back('v2:p:open')])
    await _answer(query,text,kb,parse_mode='Markdown')


async def rp_nation_stats(query,user_id):
    s=_national_state()
    with db() as conn:
        cities=conn.execute('SELECT COUNT(*) c FROM cities WHERE active=1').fetchone()['c']
        users=conn.execute('SELECT COUNT(*) c FROM users').fetchone()['c']
    await _answer(query,f"📊 *گزارش کشور*\n\n👥 جمعیت بازی: {users}\n🏙 شهرهای فعال: {cities}\n💰 خزانه: {fmt_money(s['treasury'])}\n📈 تورم: {s['inflation']:.2f}\n⭐ محبوبیت دولت: {s['approval']}٪\n🛡 ثبات: {s['stability']}٪",InlineKeyboardMarkup([[_back('v2:nation:open')]]),parse_mode='Markdown')


async def rp_nation_laws(query,user_id):
    with db() as conn: rows=conn.execute('SELECT * FROM rp_national_laws WHERE active=1 ORDER BY id DESC LIMIT 15').fetchall()
    lines=['📜 *قوانین ملی*','']
    if not rows: lines.append('هنوز قانون ویژه‌ای تصویب نشده؛ قوانین عمومی برقرار است.')
    for r in rows: lines.append(f"• {r['title']} — {r['effect']}")
    await _answer(query,'\n'.join(lines),InlineKeyboardMarkup([[_back('v2:nation:open')]]),parse_mode='Markdown')


async def rp_nation_election(query,user_id):
    e=_national_open_election()
    if not e:
        with db() as conn:
            now=time.time(); cur=conn.execute('INSERT INTO national_elections(status,started_at) VALUES(\'open\',?)',(now,)); eid=cur.lastrowid
        e={'id':eid,'status':'open'}
    rows=_national_candidates(e['id'])
    voted=False
    with db() as conn: voted=bool(conn.execute('SELECT 1 FROM national_votes WHERE election_id=? AND voter_id=?',(e['id'],user_id)).fetchone())
    lines=['🗳️ *انتخابات ملی*','']
    for r in rows: lines.append(f"• {r['username'] or r['user_id']} — 🗳️ {r['votes']} رأی")
    if not rows: lines.append('هنوز نامزدی ثبت نشده.')
    kb=[]
    for r in rows:
        if r['user_id']!=user_id and not voted: kb.append([_btn(f"🗳️ رأی به {r['username'] or r['user_id']}",f'v2:nvote:{e["id"]}:{r["user_id"]}')])
    if not voted: kb.append([_btn('🙋 نامزد می‌شوم','v2:nation:candidate')])
    else: lines.append('\n✅ شما قبلاً رأی داده‌اید.')
    if _is_leader(user_id): kb.append([_btn('⏹ پایان انتخابات (مدیر/رئیس‌جمهور)','v2:nation:finish')])
    kb.append([_back('v2:nation:open')]); await _answer(query,'\n'.join(lines),InlineKeyboardMarkup(kb),parse_mode='Markdown')


async def rp_nation_candidate(query,user_id):
    e=_national_open_election()
    if not e: await query.answer('انتخاباتی باز نیست.',show_alert=True); return
    with db() as conn: conn.execute('INSERT OR IGNORE INTO national_candidates(election_id,user_id) VALUES(?,?)',(e['id'],user_id))
    await query.answer('🙋 نامزدی شما ثبت شد.',show_alert=True); await rp_nation_election(query,user_id)


async def rp_nation_vote(query,user_id,eid,candidate):
    with db() as conn:
        e=conn.execute('SELECT * FROM national_elections WHERE id=? AND status=\'open\'',(eid,)).fetchone()
        if not e: await query.answer('انتخابات بسته شده.',show_alert=True); return
        if not conn.execute('SELECT 1 FROM national_candidates WHERE election_id=? AND user_id=?',(eid,candidate)).fetchone(): await query.answer('نامزد معتبر نیست.',show_alert=True); return
        if conn.execute('SELECT 1 FROM national_votes WHERE election_id=? AND voter_id=?',(eid,user_id)).fetchone(): await query.answer('قبلاً رأی داده‌ای.',show_alert=True); return
        conn.execute('INSERT INTO national_votes(election_id,voter_id,candidate_id) VALUES(?,?,?)',(eid,user_id,candidate))
    await query.answer('✅ رأی ثبت شد.',show_alert=True); await rp_nation_election(query,user_id)


async def rp_nation_finish(query,user_id):
    if not _is_leader(user_id): await query.answer('⛔ فقط رئیس‌جمهور یا مدیر.',show_alert=True); return
    e=_national_open_election()
    if not e: await query.answer('انتخابات بازی نیست.',show_alert=True); return
    rows=_national_candidates(e['id']); winner=rows[0]['user_id'] if rows else None
    with db() as conn:
        conn.execute("UPDATE national_elections SET status='finished',finished_at=?,winner_id=? WHERE id=?",(time.time(),winner,e['id']))
        if winner: conn.execute('UPDATE national_state SET leader_id=?,approval=60 WHERE id=1',(winner,))
    await query.answer('🏁 انتخابات پایان یافت.',show_alert=True); await rp_nation_open(query,user_id)


async def rp_government(query,user_id):
    if not _is_leader(user_id): await query.answer('⛔ فقط رئیس‌جمهور کشور.',show_alert=True); return
    s=_national_state(); sid=rp_session(user_id,query.message.chat.id,'leader',None)
    with db() as conn: cabinet=conn.execute('SELECT * FROM rp_cabinet ORDER BY role').fetchall()
    lines=[f"👑 *دولت و کابینه*\nخزانه: {fmt_money(s['treasury'])}\n"]
    for r in cabinet: lines.append(f"• {r['role']} → {r['user_id']}")
    kb=InlineKeyboardMarkup([
      [_btn('💰 سرمایه‌گذاری اقتصادی',f'v2:lr:{sid}:economy'),_btn('🛡 تقویت امنیت',f'v2:lr:{sid}:security')],
      [_btn('🏥 بودجه سلامت',f'v2:lr:{sid}:health'),_btn('🎓 بودجه آموزش',f'v2:lr:{sid}:education')],
      [_btn('🛣 بودجه زیرساخت',f'v2:lr:{sid}:infra'),_btn('💸 مالیات',f'v2:lr:{sid}:tax')],
      [_btn('📜 قانون ملی',f'v2:lr:{sid}:law'),_btn('📊 گزارش دولت',f'v2:lr:{sid}:report')],
      [_back('v2:nation:open')]
    ])
    await _answer(query,'\n'.join(lines),kb,parse_mode='Markdown')


async def rp_leader_action(query,user_id,sid,action):
    cid=query.message.chat.id if query.message else user_id
    if not rp_session_ok(sid,user_id,cid,'leader',None) or not _is_leader(user_id): await query.answer('🔒 دسترسی این پنل معتبر نیست.',show_alert=True); return
    with db() as conn:
        s=dict(conn.execute('SELECT * FROM national_state WHERE id=1').fetchone())
        costs={'economy':500000,'security':300000,'health':250000,'education':250000,'infra':400000}
        cols={'security':'security','health':'health','education':'education','infra':'infrastructure'}
        if action in costs:
            cost=costs[action]
            if s['treasury']<cost: msg='💸 خزانه کشور کافی نیست.'
            else:
                col=cols.get(action)
                if action=='economy':
                    conn.execute('UPDATE national_state SET treasury=treasury-?,inflation=MAX(0.2,inflation-0.05),stability=MIN(100,stability+3) WHERE id=1',(cost,))
                else:
                    conn.execute(f'UPDATE national_state SET treasury=treasury-?,{col}=MIN(100,{col}+8),approval=MIN(100,approval+2) WHERE id=1',(cost,))
                msg=f'✅ بودجه {action} اختصاص یافت: {fmt_money(cost)}'
        elif action=='tax':
            val=min(35,s['tax_rate']+1); conn.execute('UPDATE national_state SET tax_rate=? WHERE id=1',(val,)); msg=f'💸 مالیات کشور به {val}٪ رسید.'
        elif action=='law':
            opts=[('قانون حمایت از اشتغال','اقتصاد +5'),('قانون توسعه آموزش','آموزش +5'),('قانون امنیت عمومی','امنیت +5')]
            kb=InlineKeyboardMarkup([[_btn(n,f'v2:lrlaw:{sid}:{i}')] for i,(n,e) in enumerate(opts)]+[[_back('v2:nation:gov')]])
            await _answer(query,'📜 قانون ملی را انتخاب کن:',kb); return
        elif action=='report':
            msg=(f"📊 گزارش دولت\nخزانه {fmt_money(s['treasury'])}\nتورم {s['inflation']:.2f}\n"
                 f"محبوبیت {s['approval']}٪\nثبات {s['stability']}٪\nامنیت {s['security']}٪\nسلامت {s['health']}٪\nآموزش {s['education']}٪\nزیرساخت {s['infrastructure']}٪")
        else: msg='بخش نامعتبر است.'
    await query.answer(msg,show_alert=True); await rp_government(query,user_id)


async def rp_leader_law(query,user_id,sid,index):
    cid=query.message.chat.id if query.message else user_id
    if not rp_session_ok(sid,user_id,cid,'leader',None) or not _is_leader(user_id): await query.answer('🔒 دسترسی معتبر نیست.',show_alert=True); return
    opts=[('قانون حمایت از اشتغال','اقتصاد +5'),('قانون توسعه آموزش','آموزش +5'),('قانون امنیت عمومی','امنیت +5')]
    if not 0<=index<len(opts): return
    n,effect=opts[index]
    with db() as conn: conn.execute('INSERT INTO rp_national_laws(title,effect) VALUES(?,?)',(n,effect)); conn.execute('UPDATE national_state SET approval=MIN(100,approval+2) WHERE id=1')
    await query.answer('📜 قانون ملی تصویب شد.',show_alert=True); await rp_government(query,user_id)


# ------------------------------ مسیر تعامل کاربران ------------------------------

async def rp_target_picker(query,user_id,action):
    rows=get_user(user_id)
    with db() as conn: users=conn.execute('SELECT user_id,username FROM users WHERE user_id!=? ORDER BY username LIMIT 30',(user_id,)).fetchall()
    kb=[[_btn(r['username'] or str(r['user_id']),f'v2:target:{action}:{r["user_id"]}')] for r in users]
    kb.append([_back('v2:p:social')]); await _answer(query,'👥 کاربر موردنظر را انتخاب کن:',InlineKeyboardMarkup(kb))


async def rp_target_action(query,user_id,action,target):
    if target==user_id: await query.answer('نمی‌توانی با خودت این کار را انجام دهی.',show_alert=True); return
    target_u=get_user(target)
    if not target_u: await query.answer('کاربر پیدا نشد.',show_alert=True); return
    if action=='add':
        with db() as conn:
            conn.execute('INSERT OR IGNORE INTO friendships(user_id,friend_id) VALUES(?,?)',(user_id,target))
            conn.execute('INSERT OR IGNORE INTO friendships(user_id,friend_id) VALUES(?,?)',(target,user_id))
            conn.execute('INSERT INTO rp_relationships(user_id,target_id,kind,score) VALUES(?,?,?,?) ON CONFLICT(user_id,target_id,kind) DO UPDATE SET score=MIN(100,score+5)',(user_id,target,'friend',50))
        msg='🤝 دوستی ثبت شد.'
    elif action=='interact':
        u=get_user(user_id); gain=random.choice([3,5,8]); rp_change_stat(user_id,happiness=u['happiness']+gain,stress=u['stress']-3,xp=u['xp']+5)
        with db() as conn: conn.execute('INSERT INTO rp_relationships(user_id,target_id,kind,score) VALUES(?,?,?,?) ON CONFLICT(user_id,target_id,kind) DO UPDATE SET score=MIN(100,score+excluded.score)',(user_id,target,'social',gain))
        msg='💬 گفت‌وگوی خوبی داشتید؛ رابطه بهتر شد.'
    elif action=='propose':
        # از جدول proposals موجود استفاده می‌کنیم.
        with db() as conn: conn.execute('INSERT INTO rp_relationships(user_id,target_id,kind,score) VALUES(?,?,?,?) ON CONFLICT(user_id,target_id,kind) DO UPDATE SET score=MAX(score,excluded.score)',(user_id,target,'proposal',1))
        msg='💌 پیشنهاد ازدواج ثبت شد. برای پذیرش، از سیستم خانواده استفاده کن.'
    else: msg='عملیات نامعتبر.'
    await query.answer(msg,show_alert=True); await rp_render_social(query,user_id)


# ------------------------------ Dispatcher V2 ------------------------------

async def liferp_callback(update,context):
    q=update.callback_query; data=q.data or ''; uid=q.from_user.id
    if not data.startswith('v2:'): return False
    ensure_user(uid,q.from_user.username or q.from_user.first_name)
    if not await enforce_maintenance(update,context): return True
    try:
        parts=data.split(':')
        if data=='v2:p:open': await rp_render_personal(q,uid)
        elif data=='v2:p:profile': await rp_render_profile(q,uid)
        elif data=='v2:p:career': await rp_render_career(q,uid)
        elif data=='v2:p:home': await rp_render_home(q,uid)
        elif data=='v2:p:needs': await rp_render_needs(q,uid)
        elif data=='v2:p:shop': await rp_render_shop(q,uid)
        elif data=='v2:p:inventory': await rp_render_inventory(q,uid)
        elif data=='v2:p:social': await rp_render_social(q,uid)
        elif data=='v2:p:actions': await rp_render_actions(q,uid)
        elif data=='v2:p:event': await rp_daily_event(q,uid)
        elif parts[1]=='act': await rp_action(q,uid,parts[2])
        elif parts[1]=='buy': await rp_buy(q,uid,parts[2],int(parts[3]))
        elif parts[1]=='job': await rp_choose_job(q,uid,parts[2])
        elif data=='v2:city:open': await rp_city_open(q,uid)
        elif data=='v2:city:stats': await rp_city_stats_view(q,uid)
        elif data=='v2:city:citizens': await rp_city_citizens(q,uid)
        elif data=='v2:nation:open': await rp_nation_open(q,uid)
        elif data=='v2:nation:stats': await rp_nation_stats(q,uid)
        elif data=='v2:nation:laws': await rp_nation_laws(q,uid)
        elif data=='v2:nation:election': await rp_nation_election(q,uid)
        elif data=='v2:nation:candidate': await rp_nation_candidate(q,uid)
        elif data=='v2:nation:finish': await rp_nation_finish(q,uid)
        elif data=='v2:nation:gov': await rp_government(q,uid)
        elif parts[1]=='nvote': await rp_nation_vote(q,uid,int(parts[2]),int(parts[3]))
        elif parts[1]=='city' and parts[2]=='mayor': await rp_mayor_open(q,uid)
        elif data=='v2:city:mayor': await rp_mayor_open(q,uid)
        elif parts[1]=='mr': await rp_mayor_action(q,uid,parts[2],parts[3])
        elif parts[1]=='mrp': await rp_mayor_project(q,uid,parts[2],int(parts[3]))
        elif parts[1]=='mrl': await rp_mayor_law(q,uid,parts[2],int(parts[3]))
        elif parts[1]=='lr': await rp_leader_action(q,uid,parts[2],parts[3])
        elif parts[1]=='lrlaw': await rp_leader_law(q,uid,parts[2],int(parts[3]))
        elif parts[1]=='social': await rp_target_picker(q,uid,parts[2])
        elif parts[1]=='target': await rp_target_action(q,uid,parts[2],int(parts[3]))
        else: await q.answer('بخش نامعتبر است.',show_alert=True)
    except Exception as exc:
        logger.exception('LifeRP V2 callback error: %s',exc)
        await q.answer('⚠️ این عملیات خطا داشت؛ دوباره تلاش کن.',show_alert=True)
    return True


# جایگزین منوی شروع می‌شود، اما تمام سیستم‌های قدیمی همچنان قابل دسترسی‌اند.
async def liferp_menu_command(update,context):
    uid=update.effective_user.id; ensure_user(uid,update.effective_user.username or update.effective_user.first_name); rp_apply_needs(uid)
    if update.effective_chat.type in GROUP_TYPES and not city_is_active(update.effective_chat.id):
        await cmd_menu(update,context); return
    if update.effective_chat.type in GROUP_TYPES: rp_join_city(update.effective_chat.id,uid)
    await update.message.reply_text('🌆 *Life RP — زندگی مجازی*\n\nتو فقط پول جمع نمی‌کنی؛ زندگی می‌کنی، شغل عوض می‌کنی، دوست پیدا می‌کنی، در شهر رأی می‌دهی و حتی می‌توانی شهردار یا رئیس‌جمهور کشور شوی.\n\n👇 از زندگی خودت شروع کن:',reply_markup=rp_personal_menu(uid),parse_mode='Markdown')


def register_liferp_v2(app):
    init_liferp_v2_db()
    # این Handler در گروه پایین‌تر از گاردهای امنیتی قرار می‌گیرد و فقط v2 را می‌گیرد.
    app.add_handler(CallbackQueryHandler(liferp_callback, pattern=r'^v2:'), group=-1)
    app.add_handler(CommandHandler('life', liferp_menu_command), group=1)
    app.add_handler(CommandHandler('liferp', liferp_menu_command), group=1)


# ============================================================================
# LIFE RP V3 — هسته‌ی جهان زنده، اقتصاد واقعی، دولت و بازار بازیکنان
# ============================================================================
# توکن عمداً از سورس خارج است؛ BOT_TOKEN را در محیط تنظیم کنید.
# ID مدیر و کانال خبر به صورت پیش‌فرض برای تست قابل تنظیم هستند.
V3_ADMIN_IDS = {5888377320}
NEWS_CHANNEL_ID = -1001465731038
GAME_OWNER_ID = 5888377320

V3_LEVELS = [
    (0, '🍼 تازه‌وارد'), (100, '👤 شهروند'), (300, '🧑‍💼 شاغل'),
    (700, '⭐ شهروند فعال'), (1500, '💎 مرفه'), (3000, '🏆 ثروتمند'),
    (6000, '👑 بانفوذ'), (12000, '🌟 نخبه'), (25000, '🏛️ سرمایه‌دار'),
    (50000, '🌍 اسطوره زندگی'),
]

V3_SKILLS = {
    'programming': ('💻 برنامه‌نویسی', 1.0), 'medicine': ('🩺 پزشکی', 1.0),
    'engineering': ('🔧 مهندسی', 1.0), 'management': ('📊 مدیریت', 1.0),
    'law': ('⚖️ حقوق', 1.0), 'security': ('🛡️ امنیت', 1.0),
    'military': ('🎖️ نظامی', 1.0), 'finance': ('💰 مالی', 1.0),
    'sales': ('🛒 فروش', 1.0), 'craft': ('🛠️ فنی', 1.0),
    'education': ('🎓 آموزش', 1.0), 'media': ('📰 رسانه', 1.0),
}

V3_JOBS = {
    'programmer': ('برنامه‌نویس', 'programming', 9000, 25),
    'doctor': ('پزشک', 'medicine', 13000, 30),
    'engineer': ('مهندس', 'engineering', 10500, 28),
    'accountant': ('حسابدار', 'finance', 7000, 22),
    'lawyer': ('وکیل', 'law', 8500, 24),
    'police': ('افسر پلیس', 'security', 7500, 25),
    'soldier': ('سرباز', 'military', 6500, 28),
    'teacher': ('معلم', 'education', 6000, 20),
    'journalist': ('خبرنگار', 'media', 6500, 20),
    'mechanic': ('مکانیک', 'craft', 6200, 24),
    'sales': ('فروشنده', 'sales', 5200, 20),
    'manager': ('مدیر', 'management', 11000, 25),
}

V3_DEPARTMENTS = {
    'police': ('👮 پلیس', 'security'), 'court': ('⚖️ دادگستری', 'law'),
    'army': ('🎖️ ارتش', 'military'), 'health': ('🏥 بهداشت', 'medicine'),
    'education': ('🎓 آموزش', 'education'), 'economy': ('💰 اقتصاد', 'finance'),
}

V3_SHOP = {
    'food': ('🍔 غذا', 800, 12, 'hunger'), 'medicine': ('💊 دارو', 2500, 8, 'health'),
    'phone': ('📱 گوشی', 12000, 3, 'happiness'), 'laptop': ('💻 لپ‌تاپ', 45000, 5, 'happiness'),
    'clothes': ('👕 لباس', 6000, 4, 'happiness'), 'fuel': ('⛽ سوخت', 1800, 8, 'energy'),
}


def v3_db_init():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS v3_settings(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS v3_world(id INTEGER PRIMARY KEY CHECK(id=1), day INTEGER DEFAULT 1, economy REAL DEFAULT 1.0, inflation REAL DEFAULT 2.0, crime INTEGER DEFAULT 20, employment INTEGER DEFAULT 70);
        CREATE TABLE IF NOT EXISTS v3_cities(chat_id INTEGER PRIMARY KEY, name TEXT, treasury INTEGER DEFAULT 2000000, population INTEGER DEFAULT 0, tax REAL DEFAULT 5, mayor_id INTEGER, approval INTEGER DEFAULT 60, services INTEGER DEFAULT 50, industry INTEGER DEFAULT 30, development INTEGER DEFAULT 20, last_income REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS v3_country(id INTEGER PRIMARY KEY CHECK(id=1), name TEXT DEFAULT 'جمهوری Life RP', treasury INTEGER DEFAULT 30000000, president_id INTEGER, king_id INTEGER, tax REAL DEFAULT 10, approval INTEGER DEFAULT 60, stability INTEGER DEFAULT 70, health INTEGER DEFAULT 50, education INTEGER DEFAULT 50, security INTEGER DEFAULT 50, infrastructure INTEGER DEFAULT 50, gdp INTEGER DEFAULT 100000000, inflation REAL DEFAULT 3.0);
        CREATE TABLE IF NOT EXISTS v3_departments(id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT, scope_id INTEGER, code TEXT, name TEXT, chief_id INTEGER, treasury INTEGER DEFAULT 0, salary_budget INTEGER DEFAULT 0, active INTEGER DEFAULT 1, UNIQUE(scope,scope_id,code));
        CREATE TABLE IF NOT EXISTS v3_hiring(id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT, scope_id INTEGER, department_id INTEGER, title TEXT, skill TEXT, min_skill INTEGER DEFAULT 1, salary INTEGER DEFAULT 0, description TEXT, status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS v3_applications(id INTEGER PRIMARY KEY AUTOINCREMENT, hiring_id INTEGER, user_id INTEGER, text TEXT, status TEXT DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(hiring_id,user_id));
        CREATE TABLE IF NOT EXISTS v3_employment(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, department_id INTEGER, hiring_id INTEGER, salary INTEGER, active INTEGER DEFAULT 1, hired_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS v3_player_market(id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER, buyer_id INTEGER, item_type TEXT, item_id INTEGER, title TEXT, price INTEGER, status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS v3_market_escrow(listing_id INTEGER PRIMARY KEY, buyer_id INTEGER, amount INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS v3_stocks(symbol TEXT PRIMARY KEY, name TEXT, price INTEGER, volume INTEGER DEFAULT 0, company_owner INTEGER, dividend REAL DEFAULT 0.0);
        CREATE TABLE IF NOT EXISTS v3_portfolio(user_id INTEGER, symbol TEXT, qty INTEGER DEFAULT 0, avg_price REAL DEFAULT 0, PRIMARY KEY(user_id,symbol));
        CREATE TABLE IF NOT EXISTS v3_orders(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, symbol TEXT, side TEXT, qty INTEGER, price INTEGER, status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS v3_tickets(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, category TEXT, text TEXT, attachment_id TEXT, attachment_type TEXT, status TEXT DEFAULT 'open', admin_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS v3_ticket_messages(id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER, sender_id INTEGER, text TEXT, attachment_id TEXT, attachment_type TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS v3_news(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, body TEXT, kind TEXT, sent INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS v3_elections(id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT, scope_id INTEGER, office TEXT, status TEXT DEFAULT 'open', started_at REAL DEFAULT 0, ends_at REAL DEFAULT 0, winner_id INTEGER);
        CREATE TABLE IF NOT EXISTS v3_candidates(election_id INTEGER,user_id INTEGER,program TEXT DEFAULT '',PRIMARY KEY(election_id,user_id));
        CREATE TABLE IF NOT EXISTS v3_votes(election_id INTEGER,voter_id INTEGER,candidate_id INTEGER,PRIMARY KEY(election_id,voter_id));
        CREATE TABLE IF NOT EXISTS v3_laws(id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT, scope_id INTEGER, title TEXT, effect TEXT, active INTEGER DEFAULT 1, created_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS v3_salary_log(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,role TEXT,amount INTEGER,paid_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS v3_activity(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,kind TEXT,detail TEXT,amount INTEGER DEFAULT 0,xp INTEGER DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS v3_sessions(sid TEXT PRIMARY KEY,user_id INTEGER,chat_id INTEGER,kind TEXT,entity_id INTEGER,expires REAL);
        ''')
        c.execute("INSERT OR IGNORE INTO v3_world(id) VALUES(1)")
        c.execute("INSERT OR IGNORE INTO v3_country(id) VALUES(1)")
        defaults=[('SHOP','فروشگاه عمومی','sales'),('STOCK','بورس Life RP','finance')]
        for code,name,skill in defaults:
            c.execute("INSERT OR IGNORE INTO v3_departments(scope,scope_id,code,name) VALUES('national',1,?,?,?)" if False else "SELECT 1", ())
        for code,(name,skill) in V3_DEPARTMENTS.items():
            c.execute("INSERT OR IGNORE INTO v3_departments(scope,scope_id,code,name,treasury,salary_budget) VALUES('national',1,?,?,500000,500000)",(code,name))
        stocks=[('LIFE','Life Industries',12000),('BANK','Life Bank',18000),('TECH','Life Tech',25000),('MED','Life Health',15000)]
        for sym,name,price in stocks:
            c.execute("INSERT OR IGNORE INTO v3_stocks(symbol,name,price) VALUES(?,?,?)",(sym,name,price))


def v3_user(u):
    ensure_user(u, str(u))
    with db() as c:
        c.execute("ALTER TABLE users ADD COLUMN life_score INTEGER DEFAULT 0") if 'life_score' not in [r[1] for r in c.execute('PRAGMA table_info(users)')] else None
        c.execute("ALTER TABLE users ADD COLUMN reputation INTEGER DEFAULT 50") if 'reputation' not in [r[1] for r in c.execute('PRAGMA table_info(users)')] else None
        c.execute("ALTER TABLE users ADD COLUMN education_level INTEGER DEFAULT 0") if 'education_level' not in [r[1] for r in c.execute('PRAGMA table_info(users)')] else None
    return get_user(u)


def v3_level(xp, assets=0, reputation=50):
    score=max(0,int(xp//10)+int(assets//100000)+max(0,reputation-50)*5)
    level=1; title=V3_LEVELS[0][1]
    for threshold,t in V3_LEVELS:
        if score>=threshold: level+=1; title=t
    return min(level,len(V3_LEVELS)),title,score


def v3_assets(uid):
    with db() as c:
        cash=c.execute('SELECT cash+bank FROM users WHERE user_id=?',(uid,)).fetchone()[0] or 0
        p=c.execute('SELECT COUNT(*) n FROM user_properties WHERE user_id=?',(uid,)).fetchone()['n']
        v=c.execute('SELECT COUNT(*) n FROM user_vehicles WHERE user_id=?',(uid,)).fetchone()['n']
    return cash+p*100000+v*50000


def v3_log(uid,kind,detail='',amount=0,xp=0):
    with db() as c: c.execute('INSERT INTO v3_activity(user_id,kind,detail,amount,xp) VALUES(?,?,?,?,?)',(uid,kind,detail,amount,xp))


def v3_session(uid,chat,kind,entity=None):
    import secrets
    sid=secrets.token_urlsafe(12); now=time.time()
    with db() as c:
        c.execute('DELETE FROM v3_sessions WHERE expires<?',(now,))
        c.execute('INSERT INTO v3_sessions VALUES(?,?,?,?,?,?)',(sid,uid,chat,kind,entity,now+900))
    return sid


def v3_session_ok(sid,uid,chat,kind,entity=None):
    if not sid: return False
    with db() as c:
        r=c.execute('SELECT * FROM v3_sessions WHERE sid=? AND user_id=? AND chat_id=? AND kind=? AND expires>?',(sid,uid,chat,kind,time.time())).fetchone()
    return bool(r and (entity is None or r['entity_id']==entity))


def v3_btn(t,d): return InlineKeyboardButton(t,callback_data='v3|'+d)


def v3_personal_kb():
    return InlineKeyboardMarkup([
        [v3_btn('👤 شخصیت','p|profile'),v3_btn('📈 سطح و مهارت','p|skills')],
        [v3_btn('💼 کار','p|jobs'),v3_btn('🏠 دارایی‌ها','p|assets')],
        [v3_btn('🛒 نیازهای روزمره','p|shop'),v3_btn('🤝 بازار کاربران','p|market')],
        [v3_btn('📈 بورس','p|stocks'),v3_btn('🏙 شهر من','city|open')],
        [v3_btn('🇮🇷 کشور','nation|open'),v3_btn('📰 اخبار','news|list')],
        [v3_btn('🎫 پشتیبانی','ticket|open'),v3_btn('👑 مدیریت','owner|open')],
    ])


def v3_job_kb():
    rows=[]
    for k,(n,skill,pay,cd) in V3_JOBS.items(): rows.append([v3_btn(f'{n} | {pay:,}💰',f'job|{k}')])
    return InlineKeyboardMarkup(rows+[[v3_btn('↩️ بازگشت','p|open')]])


def v3_ticket_kb():
    cats=[('🐞 باگ','bug'),('💳 مالی','finance'),('⚖️ شکایت','complaint'),('🚨 گزارش تخلف','report'),('❓ سوال','question'),('📌 سایر','other')]
    return InlineKeyboardMarkup([[v3_btn(t,f'ticket|cat|{k}')] for t,k in cats]+[[v3_btn('↩️ بازگشت','p|open')]])


async def v3_send_news(bot,title,body,kind='system'):
    with db() as c:
        cur=c.execute('INSERT INTO v3_news(title,body,kind) VALUES(?,?,?)',(title,body,kind)); nid=cur.lastrowid
    try:
        await bot.send_message(NEWS_CHANNEL_ID,f'📰 <b>{title}</b>\n\n{body}',parse_mode='HTML',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🎮 ورود به بازی',callback_data='v3|p|open')]]))
        with db() as c: c.execute('UPDATE v3_news SET sent=1 WHERE id=?',(nid,))
    except Exception as e: logger.warning('news channel: %s',e)


async def v3_menu(q,uid):
    v3_user(uid); await q.edit_message_text('🌍 <b>Life RP</b>\n\nزندگی، کار، پول، ملک، شرکت، بورس، سیاست و تصمیماتی که روی دنیای بازی اثر می‌گذارند.',parse_mode='HTML',reply_markup=v3_personal_kb())


async def v3_profile(q,uid):
    u=v3_user(uid); assets=v3_assets(uid); lvl,title,score=v3_level(u['xp'],assets,u.get('reputation',50))
    text=(f"👤 <b>{u.get('username') or uid}</b>\n━━━━━━━━━━━━\n"
          f"🎚 سطح: {lvl} — {title}\n⭐ امتیاز زندگی: {score}\n✨ XP: {u['xp']}\n"
          f"💵 نقد: {u['cash']:,}\n🏦 بانک: {u['bank']:,}\n💎 دارایی خالص تقریبی: {assets:,}\n"
          f"❤️ سلامت: {u['health']} | ⚡ انرژی: {u['energy']}\n😊 شادی: {u['happiness']} | 😰 استرس: {u['stress']}\n🎓 تحصیلات: {u.get('education_level',0)}\n⭐ اعتبار اجتماعی: {u.get('reputation',50)}")
    await q.edit_message_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup([[v3_btn('📈 مهارت‌ها','p|skills')],[v3_btn('↩️ بازگشت','p|open')]]))


async def v3_skills(q,uid):
    v3_user(uid)
    with db() as c: rows=c.execute('SELECT skill,level,xp FROM user_skills WHERE user_id=? ORDER BY level DESC',(uid,)).fetchall()
    text='📈 <b>مهارت‌های من</b>\n━━━━━━━━━━━━\n'
    if not rows: text+='هنوز مهارتی ثبت نشده. از کار و آموزش شروع کن.\n'
    for r in rows: text+=f"{V3_SKILLS.get(r['skill'],(r['skill'],))[0]} — سطح {r['level']} | XP {r['xp']}\n"
    text+='\nهر شغل به مهارت واقعی نیاز دارد و درآمد با سطح مهارت رشد می‌کند.'
    await q.edit_message_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup([[v3_btn('🏋️ تمرین مهارت','p|train')],[v3_btn('💼 شغل‌ها','p|jobs')],[v3_btn('↩️ بازگشت','p|open')]]))


async def v3_jobs(q,uid):
    u=v3_user(uid); lvl,title,score=v3_level(u['xp'],v3_assets(uid),u.get('reputation',50))
    text='💼 <b>بازار کار</b>\n━━━━━━━━━━━━\nهر شغل نیازمند مهارت است. استخدام‌های سازمانی از آگهی انجام می‌شوند.\n\n'
    for k,(n,s,pay,cd) in V3_JOBS.items(): text+=f'• {n}: {pay:,}💰 | مهارت {V3_SKILLS[s][0]}\n'
    await q.edit_message_text(text,parse_mode='HTML',reply_markup=v3_job_kb())


async def v3_assets_ui(q,uid):
    with db() as c:
        ps=c.execute('SELECT prop_key,COUNT(*) n FROM user_properties WHERE user_id=? GROUP BY prop_key',(uid,)).fetchall()
        vs=c.execute('SELECT veh_key,COUNT(*) n FROM user_vehicles WHERE user_id=? GROUP BY veh_key',(uid,)).fetchall()
    text='🏠 <b>دارایی‌ها</b>\n━━━━━━━━━━━━\n'
    text+='ملک:\n'+(''.join(f'• {PROPERTIES.get(r[0],{}).get("name",r[0])} ×{r[1]}\n' for r in ps) or 'نداری\n')
    text+='\n🚗 وسیله نقلیه:\n'+(''.join(f'• {VEHICLES.get(r[0],{}).get("name",r[0])} ×{r[1]}\n' for r in vs) or 'نداری\n')
    text+='\nدارایی‌ها کاربرد اقتصادی دارند: اجاره/درآمد ملک، هزینه نگهداری وسیله و امکان فروش در بازار.'
    await q.edit_message_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup([[v3_btn('🏪 خرید','p|shop')],[v3_btn('🤝 فروش به بازیکن','market|sell')],[v3_btn('↩️ بازگشت','p|open')]]))


async def v3_shop(q,uid):
    text='🛒 <b>فروشگاه و نیازهای روزمره</b>\n━━━━━━━━━━━━\nمصرف واقعی روی وضعیت شخصیت اثر می‌گذارد.\n\n'
    for k,(n,price,effect,stat) in V3_SHOP.items(): text+=f'• {n}: {price:,}💰 → +{effect} {stat}\n'
    kb=[[v3_btn(f'{n} | {p:,}','shop|buy|'+k) for k,(n,p,_,_) in [item]] for item in []]
    rows=[]
    for k,(n,p,e,st) in V3_SHOP.items(): rows.append([v3_btn(f'خرید {n} — {p:,}💰',f'shop|buy|{k}')])
    rows.append([v3_btn('↩️ بازگشت','p|open')])
    await q.edit_message_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(rows))


async def v3_buy_shop(q,uid,key):
    if key not in V3_SHOP: return await q.answer('کالا نامعتبر است.',show_alert=True)
    n,p,e,st=V3_SHOP[key]; u=v3_user(uid)
    if u['cash']<p: return await q.answer('پول کافی نداری.',show_alert=True)
    fields={st:min(100,u.get(st,0)+e)} if st in ('health','energy','happiness') else {}
    if st=='hunger': fields[st]=max(0,u.get(st,0)-e)
    with db() as c:
        c.execute('UPDATE users SET cash=cash-?,health=?,energy=?,happiness=?,hunger=? WHERE user_id=?',(p,fields.get('health',u['health']),fields.get('energy',u['energy']),fields.get('happiness',u['happiness']),fields.get('hunger',u['hunger']),uid))
    v3_log(uid,'purchase',n,-p,2); await q.answer('خرید انجام شد.'); await v3_shop(q,uid)


async def v3_choose_job(q,uid,key):
    if key not in V3_JOBS: return await q.answer('شغل نامعتبر.',show_alert=True)
    n,skill,pay,cd=V3_JOBS[key];
    with db() as c: r=c.execute('SELECT level FROM user_skills WHERE user_id=? AND skill=?',(uid,skill)).fetchone()
    sl=r['level'] if r else 0
    if sl<2: return await q.answer(f'برای {n} حداقل مهارت سطح 2 لازم است.',show_alert=True)
    with db() as c: c.execute('UPDATE users SET job=? WHERE user_id=?',(key,uid))
    await q.answer(f'شغل تو شد: {n}'); await v3_jobs(q,uid)


async def v3_market(q,uid):
    with db() as c:
        rows=c.execute("SELECT * FROM v3_player_market WHERE status='open' ORDER BY id DESC LIMIT 12").fetchall()
    text='🤝 <b>بازار کاربران</b>\n━━━━━━━━━━━━\nاینجا بازیکن‌ها واقعاً کالا و دارایی خودشان را می‌فروشند. خریدها انتقال مالکیت دارند.\n\n'
    kb=[]
    for r in rows:
        text+=f"#{r['id']} • {r['title']} — {r['price']:,}💰\n"
        kb.append([v3_btn(f"خرید #{r['id']} — {r['price']:,}",f'market|buy|{r["id"]}')])
    kb += [[v3_btn('➕ ثبت آگهی','market|sell')],[v3_btn('↩️ بازگشت','p|open')]]
    await q.edit_message_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(kb))


async def v3_stocks(q,uid):
    with db() as c:
        stocks=c.execute('SELECT * FROM v3_stocks ORDER BY symbol').fetchall(); port=c.execute('SELECT * FROM v3_portfolio WHERE user_id=? AND qty>0',(uid,)).fetchall()
    text='📈 <b>بورس Life RP</b>\n━━━━━━━━━━━━\nقیمت‌ها با اقتصاد جهانی و معاملات بازیکنان تغییر می‌کنند.\n\n'
    for s in stocks: text+=f"<b>{s['symbol']}</b> {s['name']} — {s['price']:,}💰\n"
    if port:
        text+='\n📊 سبد من:\n'+''.join(f"{r['symbol']} ×{r['qty']}\n" for r in port)
    kb=[[v3_btn(f'خرید {s["symbol"]}','stock|buy|'+s['symbol']) for s in stocks[:2]],[v3_btn('فروش سهم','stock|sell'),v3_btn('📊 سبد من','stock|portfolio')],[v3_btn('↩️ بازگشت','p|open')]]
    await q.edit_message_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(kb))


async def v3_stock_buy(q,uid,symbol):
    with db() as c: s=c.execute('SELECT * FROM v3_stocks WHERE symbol=?',(symbol,)).fetchone()
    if not s: return await q.answer('نماد نامعتبر.',show_alert=True)
    price=s['price']; u=v3_user(uid)
    if u['cash']<price: return await q.answer('برای خرید یک سهم پول کافی نیست.',show_alert=True)
    with db() as c:
        c.execute('UPDATE users SET cash=cash-? WHERE user_id=?',(price,uid))
        c.execute('INSERT INTO v3_portfolio(user_id,symbol,qty,avg_price) VALUES(?,?,1,?) ON CONFLICT(user_id,symbol) DO UPDATE SET avg_price=(avg_price*qty+excluded.avg_price)/(qty+1),qty=qty+1',(uid,symbol,price))
        c.execute('UPDATE v3_stocks SET volume=volume+1,price=MAX(100,CAST(price*1.002 AS INTEGER)) WHERE symbol=?',(symbol,))
    v3_log(uid,'stock_buy',symbol,-price,5); await q.answer('سهم خریداری شد.'); await v3_stocks(q,uid)



def v3_ensure_city(chat_id):
    with db() as c:
        r=c.execute('SELECT * FROM v3_cities WHERE chat_id=?',(chat_id,)).fetchone()
        if r: return r
        old=c.execute('SELECT name,mayor_id FROM cities WHERE chat_id=? AND active=1',(chat_id,)).fetchone()
        name=(old['name'] if old and old['name'] else f'شهر {chat_id}')
        mayor=(old['mayor_id'] if old else None)
        c.execute('INSERT INTO v3_cities(chat_id,name,mayor_id,population) VALUES(?,?,?,0)',(chat_id,name,mayor))
        for code,(dname,skill) in V3_DEPARTMENTS.items():
            c.execute("INSERT OR IGNORE INTO v3_departments(scope,scope_id,code,name,treasury,salary_budget) VALUES('city',?,?,?,100000,100000)",(chat_id,code,dname))
        return c.execute('SELECT * FROM v3_cities WHERE chat_id=?',(chat_id,)).fetchone()


def v3_set_city_role(chat_id, mayor_id):
    with db() as c:
        v3_ensure_city(chat_id)
        c.execute('UPDATE v3_cities SET mayor_id=? WHERE chat_id=?',(mayor_id,chat_id))
        try: c.execute('UPDATE cities SET mayor_id=? WHERE chat_id=?',(mayor_id,chat_id))
        except Exception: pass

async def v3_city(q,uid):
    chat=q.message.chat_id
    city=v3_ensure_city(chat)

    text=f"🏙️ <b>{city['name']}</b>\n━━━━━━━━━━━━\n💰 خزانه: {city['treasury']:,}\n👥 جمعیت: {city['population']}\n💸 مالیات: {city['tax']}%\n⭐ رضایت: {city['approval']}%\n🏗 توسعه: {city['development']}\n🏪 صنعت: {city['industry']}\n👑 شهردار: {city['mayor_id'] or 'ندارد'}"
    kb=[[v3_btn('🗳 انتخابات شهردار','election|city'),v3_btn('🏛 پنل شهردار','mayor|open')],[v3_btn('👮 استخدام پلیس','hire|city|police'),v3_btn('🏥 خدمات شهر','city|services')],[v3_btn('📢 آگهی‌های استخدام','hire|list|city')],[v3_btn('↩️ بازگشت','p|open')]]
    await q.edit_message_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(kb))


async def v3_nation(q,uid):
    with db() as c: n=c.execute('SELECT * FROM v3_country WHERE id=1').fetchone()
    text=f"🇮🇷 <b>{n['name']}</b>\n━━━━━━━━━━━━\n💰 خزانه: {n['treasury']:,}\n👑 پادشاه: {n['king_id'] or 'ندارد'}\n🏛 رئیس‌جمهور: {n['president_id'] or 'ندارد'}\n📈 GDP: {n['gdp']:,}\n💸 تورم: {n['inflation']:.1f}%\n⭐ رضایت: {n['approval']}%\n🛡 امنیت: {n['security']} | 🏥 سلامت: {n['health']}\n🎓 آموزش: {n['education']} | 🛣 زیرساخت: {n['infrastructure']}"
    kb=[[v3_btn('🗳 انتخابات رئیس‌جمهور','election|national'),v3_btn('🏛 دولت','gov|open')],[v3_btn('🏢 وزارتخانه‌ها','hire|national'),v3_btn('📢 آگهی استخدام','hire|list|national')],[v3_btn('↩️ بازگشت','p|open')]]
    await q.edit_message_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(kb))


async def v3_owner(q,uid):
    if uid not in V3_ADMIN_IDS and uid!=GAME_OWNER_ID: return await q.answer('این پنل فقط برای مالک بازی است.',show_alert=True)
    with db() as c: n=c.execute('SELECT * FROM v3_country WHERE id=1').fetchone()
    text=f"👑 <b>پنل مالک بازی</b>\n━━━━━━━━━━━━\nمالک: <code>{GAME_OWNER_ID}</code>\nپادشاه کشور: {n['king_id'] or 'تعیین نشده'}\nرئیس‌جمهور: {n['president_id'] or 'تعیین نشده'}\n\nمالک مستقیماً بر تمام لایه‌های بازی اختیار دارد."
    kb=[[v3_btn('👑 تعیین پادشاه','owner|king'),v3_btn('🏛 تعیین رئیس‌جمهور','owner|president')],[v3_btn('🏙 تعیین شهردار','owner|mayor')],[v3_btn('📰 ارسال خبر','owner|news'),v3_btn('📊 اقتصاد','owner|economy')],[v3_btn('🛠 مدیریت استخدام‌ها','hire|national')],[v3_btn('↩️ بازگشت','p|open')]]
    await q.edit_message_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(kb))



async def v3_mayor_action(q,uid,sid,action):
    chat=q.message.chat_id
    if not v3_session_ok(sid,uid,chat,'mayor',chat): return await q.answer('🔒 پنل منقضی یا غیرمعتبر است.',show_alert=True)
    costs={'budget':100000,'police':120000,'health':120000,'transit':150000,'project':250000,'tax':0,'news':0}
    with db() as c:
        city=c.execute('SELECT * FROM v3_cities WHERE chat_id=? AND mayor_id=?',(chat,uid)).fetchone()
        if not city: return await q.answer('دسترسی شهرداری معتبر نیست.',show_alert=True)
        cost=costs.get(action,0)
        if cost and city['treasury']<cost: return await q.answer('خزانه شهر برای این تصمیم کافی نیست.',show_alert=True)
        if action=='budget': c.execute('UPDATE v3_cities SET treasury=treasury-?,development=MIN(100,development+2),approval=MIN(100,approval+1) WHERE chat_id=?',(cost,chat))
        elif action=='police': c.execute('UPDATE v3_cities SET treasury=treasury-?,approval=MIN(100,approval+2) WHERE chat_id=?',(cost,chat)); c.execute('UPDATE v3_world SET crime=MAX(0,crime-2) WHERE id=1')
        elif action=='health': c.execute('UPDATE v3_cities SET treasury=treasury-?,approval=MIN(100,approval+2) WHERE chat_id=?',(cost,chat))
        elif action=='transit': c.execute('UPDATE v3_cities SET treasury=treasury-?,development=MIN(100,development+3),approval=MIN(100,approval+2) WHERE chat_id=?',(cost,chat))
        elif action=='project': c.execute('UPDATE v3_cities SET treasury=treasury-?,development=MIN(100,development+6),industry=MIN(100,industry+2) WHERE chat_id=?',(cost,chat))
        elif action=='tax': c.execute('UPDATE v3_cities SET tax=CASE WHEN tax>=20 THEN 5 ELSE tax+1 END WHERE chat_id=?',(chat,))
        elif action=='news': pass
    await q.answer('✅ تصمیم شهردار اجرا شد و روی شهر اثر گذاشت.')
    await v3_mayor(q,uid)


async def v3_gov_action(q,uid,sid,action):
    if not v3_session_ok(sid,uid,q.message.chat_id,'gov',1): return await q.answer('🔒 پنل دولت معتبر نیست.',show_alert=True)
    with db() as c:
        n=c.execute('SELECT * FROM v3_country WHERE id=1').fetchone()
        if n['president_id']!=uid and uid not in V3_ADMIN_IDS and uid!=GAME_OWNER_ID: return await q.answer('دسترسی دولت معتبر نیست.',show_alert=True)
        costs={'budget':1000000,'health':1500000,'education':1500000,'security':1800000,'infra':2000000,'tax':0}
        cost=costs.get(action,0)
        if cost and n['treasury']<cost: return await q.answer('خزانه کشور کافی نیست.',show_alert=True)
        col={'health':'health','education':'education','security':'security','infra':'infrastructure'}.get(action)
        if col: c.execute(f'UPDATE v3_country SET treasury=treasury-?,{col}=MIN(100,{col}+4),approval=MIN(100,approval+1) WHERE id=1',(cost,))
        elif action=='budget': c.execute('UPDATE v3_country SET treasury=treasury-?,gdp=gdp+3000000 WHERE id=1',(cost,))
        elif action=='tax': c.execute('UPDATE v3_country SET tax=CASE WHEN tax>=25 THEN 8 ELSE tax+1 END WHERE id=1')
    await q.answer('✅ سیاست دولت اجرا شد و شاخص کشور تغییر کرد.'); await v3_gov(q,uid)

async def v3_mayor(q,uid):
    chat=q.message.chat_id
    with db() as c: city=c.execute('SELECT * FROM v3_cities WHERE chat_id=?',(chat,)).fetchone()
    if not city or city['mayor_id']!=uid: return await q.answer('این پنل فقط برای شهردار همین شهر است.',show_alert=True)
    sid=v3_session(uid,chat,'mayor',chat)
    text=f"🏛 <b>پنل شهردار</b>\n━━━━━━━━━━━━\n💰 خزانه: {city['treasury']:,}\n⭐ محبوبیت: {city['approval']}%\n💸 مالیات: {city['tax']}%\n🏗 توسعه: {city['development']}\n\nوظیفه: درآمد شهر را افزایش بده، خدمات را تأمین کن، پروژه بساز و رضایت مردم را حفظ کن."
    kb=[[v3_btn('💰 بودجه','mayor|budget|'+sid),v3_btn('💸 مالیات','mayor|tax|'+sid)],[v3_btn('🏗 پروژه','mayor|project|'+sid),v3_btn('👮 پلیس','mayor|police|'+sid)],[v3_btn('🏥 درمان','mayor|health|'+sid),v3_btn('🚇 حمل‌ونقل','mayor|transit|'+sid)],[v3_btn('📢 استخدام','hire|city|police'),v3_btn('📰 خبر شهر','mayor|news|'+sid)],[v3_btn('↩️ شهر','city|open')]]
    await q.edit_message_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(kb))


async def v3_gov(q,uid):
    with db() as c: n=c.execute('SELECT * FROM v3_country WHERE id=1').fetchone()
    if n['president_id']!=uid and uid not in V3_ADMIN_IDS and uid!=GAME_OWNER_ID: return await q.answer('فقط رئیس‌جمهور، پادشاه یا مالک بازی.',show_alert=True)
    sid=v3_session(uid,q.message.chat_id,'gov',1)
    text=f"🏛 <b>دولت</b>\n━━━━━━━━━━━━\nرئیس‌جمهور: {n['president_id'] or '-'}\nخزانه: {n['treasury']:,}\nتورم: {n['inflation']:.1f}%\nرضایت: {n['approval']}%"
    kb=[[v3_btn('💰 بودجه','gov|budget|'+sid),v3_btn('💸 مالیات','gov|tax|'+sid)],[v3_btn('🏥 سلامت','gov|health|'+sid),v3_btn('🎓 آموزش','gov|education|'+sid)],[v3_btn('🛡 امنیت','gov|security|'+sid),v3_btn('🛣 زیرساخت','gov|infra|'+sid)],[v3_btn('🏢 وزارتخانه‌ها','hire|national')],[v3_btn('↩️ کشور','nation|open')]]
    await q.edit_message_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(kb))


async def v3_ticket(q,uid): await q.edit_message_text('🎫 <b>پشتیبانی</b>\n\nموضوع تیکت را انتخاب کن:',parse_mode='HTML',reply_markup=v3_ticket_kb())


async def v3_ticket_category(q,uid,cat):
    context_pending[q.message.chat_id]={'kind':'ticket','uid':uid,'cat':cat}
    await q.edit_message_text(f'🎫 موضوع: <b>{cat}</b>\n\nحالا متن درخواستت را در یک پیام بفرست. می‌توانی عکس/فایل هم ارسال کنی.',parse_mode='HTML')


async def v3_ticket_admin(q,uid):
    if uid not in V3_ADMIN_IDS and uid!=GAME_OWNER_ID: return await q.answer('فقط ادمین.',show_alert=True)
    with db() as c: rows=c.execute("SELECT * FROM v3_tickets WHERE status='open' ORDER BY id DESC LIMIT 20").fetchall()
    text='🎫 <b>تیکت‌های باز</b>\n━━━━━━━━━━━━\n'+(''.join(f"#{r['id']} | user {r['user_id']} | {r['category']}\n" for r in rows) or 'تیکت بازی وجود ندارد.')
    kb=[[v3_btn(f'باز کردن #{r["id"]}',f'ticket|admin|{r["id"]}')] for r in rows]+[[v3_btn('↩️ مدیریت','owner|open')]]
    await q.edit_message_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(kb))


async def v3_ticket_admin_view(q,uid,tid):
    if uid not in V3_ADMIN_IDS and uid!=GAME_OWNER_ID: return await q.answer('فقط ادمین.',show_alert=True)
    with db() as c:
        t=c.execute('SELECT * FROM v3_tickets WHERE id=?',(tid,)).fetchone(); msgs=c.execute('SELECT * FROM v3_ticket_messages WHERE ticket_id=? ORDER BY id',(tid,)).fetchall()
    if not t: return await q.answer('تیکت پیدا نشد.',show_alert=True)
    text=f"🎫 <b>تیکت #{tid}</b>\nکاربر: <code>{t['user_id']}</code>\nموضوع: {t['category']}\n\n{t['text']}\n\n"+''.join(f"\n👤 {m['sender_id']}: {m['text']}" for m in msgs)
    await q.edit_message_text(text[:4000],parse_mode='HTML',reply_markup=InlineKeyboardMarkup([[v3_btn('✉️ پاسخ','ticket|reply|'+str(tid)),v3_btn('✅ بستن','ticket|close|'+str(tid))],[v3_btn('↩️ تیکت‌ها','ticket|admin')]]))


async def v3_hiring_list(q,uid,scope):
    with db() as c: rows=c.execute("SELECT * FROM v3_hiring WHERE scope=? AND status='open' ORDER BY id DESC LIMIT 20",(scope,)).fetchall()
    text='📢 <b>آگهی‌های استخدام</b>\n━━━━━━━━━━━━\n'+(''.join(f"#{r['id']} • {r['title']} | حقوق {r['salary']:,} | مهارت {r['min_skill']}\n" for r in rows) or 'آگهی فعالی نیست.')
    kb=[[v3_btn(f'فرم #{r["id"]}','hire|apply|'+str(r['id']))] for r in rows]+[[v3_btn('↩️ بازگشت','nation|open' if scope=='national' else 'city|open')]]
    await q.edit_message_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(kb))


async def v3_apply(q,uid,hid):
    with db() as c: r=c.execute('SELECT * FROM v3_hiring WHERE id=? AND status="open"',(hid,)).fetchone()
    if not r: return await q.answer('آگهی بسته شده.',show_alert=True)
    context_pending[q.message.chat_id]={'kind':'jobapp','uid':uid,'hid':hid}
    await q.edit_message_text(f"📝 <b>فرم استخدام #{hid}</b>\n\nآگهی: {r['title']}\nحقوق: {r['salary']:,}\nمهارت لازم: {r['min_skill']}\n\nخودت و تجربه‌ات را در یک پیام توضیح بده:",parse_mode='HTML')


async def v3_election(q,uid,scope):
    sid=1 if scope=='national' else q.message.chat_id
    with db() as c:
        e=c.execute("SELECT * FROM v3_elections WHERE scope=? AND scope_id=? AND status='open' ORDER BY id DESC LIMIT 1",(scope,sid)).fetchone()
        if not e:
            cur=c.execute("INSERT INTO v3_elections(scope,scope_id,office,status,started_at,ends_at) VALUES(?,?,?,?,?,?)",(scope,sid,'رئیس‌جمهور' if scope=='national' else 'شهردار','open',time.time(),time.time()+86400)); eid=cur.lastrowid
        else: eid=e['id']
        cands=c.execute('SELECT * FROM v3_candidates WHERE election_id=?',(eid,)).fetchall()
        counts={r['candidate_id']:r['n'] for r in c.execute('SELECT candidate_id,COUNT(*) n FROM v3_votes WHERE election_id=? GROUP BY candidate_id',(eid,)).fetchall()}
    office='ریاست‌جمهوری' if scope=='national' else 'شهرداری'
    text=f'🗳 <b>انتخابات {office}</b>\n━━━━━━━━━━━━\n⏳ زمان رأی‌گیری: ۲۴ ساعت\n\n'
    text += ''.join(f"• <code>{r['user_id']}</code> — {counts.get(r['user_id'],0)} رأی\n" for r in cands) or 'هنوز نامزدی ثبت نشده.\n'
    kb=[[v3_btn('✍️ نامزد شدن',f'election|candidate|{eid}|{scope}')]]
    for r in cands:
        if r['user_id']!=uid: kb.append([v3_btn(f'🗳 رأی به {r["user_id"]}',f'election|vote|{eid}|{r["user_id"]}|{scope}')])
    if uid in V3_ADMIN_IDS or uid==GAME_OWNER_ID: kb.append([v3_btn('🏁 پایان و شمارش','election|finish|'+str(eid)+'|'+scope)])
    kb.append([v3_btn('📢 خبر در کانال','election|news|'+str(eid)+'|'+scope)])
    kb.append([v3_btn('↩️ بازگشت','nation|open' if scope=='national' else 'city|open')])
    await q.edit_message_text(text,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(kb))


async def v3_candidate(q,uid,eid,scope):
    with db() as c:
        exists=c.execute('SELECT 1 FROM v3_candidates WHERE election_id=? AND user_id=?',(eid,uid)).fetchone()
        if exists: return await q.answer('قبلاً نامزد شده‌ای.',show_alert=True)
        c.execute('INSERT INTO v3_candidates(election_id,user_id) VALUES(?,?)',(eid,uid))
    await q.answer('نامزدی ثبت شد.'); await v3_election(q,uid,scope)


async def v3_vote(q,uid,eid,cand,scope='national'):
    with db() as c:
        e=c.execute('SELECT * FROM v3_elections WHERE id=? AND status="open"',(eid,)).fetchone()
        if not e: return await q.answer('انتخابات بسته است.',show_alert=True)
        if e['ends_at'] and time.time()>e['ends_at']: return await q.answer('مهلت رأی‌گیری تمام شده.',show_alert=True)
        if not c.execute('SELECT 1 FROM v3_candidates WHERE election_id=? AND user_id=?',(eid,cand)).fetchone(): return await q.answer('نامزد معتبر نیست.',show_alert=True)
        try: c.execute('INSERT INTO v3_votes VALUES(?,?,?)',(eid,uid,cand))
        except sqlite3.IntegrityError: return await q.answer('قبلاً رأی داده‌ای.',show_alert=True)
    await q.answer('رأی ثبت شد.'); await v3_election(q,uid,scope)


async def v3_finish_election(q,uid,eid,scope,bot):
    if uid not in V3_ADMIN_IDS and uid!=GAME_OWNER_ID: return await q.answer('فقط مالک/ادمین می‌تواند انتخابات را ببندد.',show_alert=True)
    sid=1 if scope=='national' else q.message.chat_id
    with db() as c:
        e=c.execute('SELECT * FROM v3_elections WHERE id=? AND status="open"',(eid,)).fetchone()
        if not e: return await q.answer('انتخابات بسته است.',show_alert=True)
        rows=c.execute('SELECT candidate_id,COUNT(*) n FROM v3_votes WHERE election_id=? GROUP BY candidate_id ORDER BY n DESC,candidate_id',(eid,)).fetchall()
        if not rows: return await q.answer('هیچ رأیی ثبت نشده.',show_alert=True)
        winner=rows[0]['candidate_id']; c.execute('UPDATE v3_elections SET status="finished",finished_at=?,winner_id=? WHERE id=?',(time.time(),winner,eid))
        if scope=='national': c.execute('UPDATE v3_country SET president_id=? WHERE id=1',(winner,))
        else:
            c.execute('INSERT OR IGNORE INTO v3_cities(chat_id,name) VALUES(?,?,?)' if False else 'SELECT 1',())
            c.execute('UPDATE v3_cities SET mayor_id=? WHERE chat_id=?',(winner,sid))
            try: c.execute('UPDATE cities SET mayor_id=? WHERE chat_id=?',(winner,sid))
            except Exception: pass
    await q.answer(f'🏆 برنده: {winner}')
    await v3_send_news(bot,f'نتیجه انتخابات {"ریاست‌جمهوری" if scope=="national" else "شهرداری"}',f'🏆 برنده انتخابات: {winner}')
    await v3_election(q,uid,scope)


async def v3_train(q,uid):
    v3_user(uid)
    skills=list(V3_SKILLS.keys()); rows=[[v3_btn(V3_SKILLS[s][0],f'train|{s}') for s in skills[i:i+2]] for i in range(0,len(skills),2)]
    rows.append([v3_btn('↩️ مهارت‌ها','p|skills')]); await q.edit_message_text('🏋️ <b>آموزش مهارت</b>\n\nیک مهارت انتخاب کن. آموزش هزینه انرژی و زمان دارد و سطح مهارت روی استخدام و درآمد اثر می‌گذارد.',parse_mode='HTML',reply_markup=InlineKeyboardMarkup(rows))


async def v3_train_do(q,uid,skill):
    if skill not in V3_SKILLS: return await q.answer('مهارت نامعتبر.',show_alert=True)
    u=v3_user(uid)
    if u['energy']<15: return await q.answer('انرژی کافی نیست.',show_alert=True)
    with db() as c:
        c.execute('UPDATE users SET energy=energy-15,xp=xp+10 WHERE user_id=?',(uid,))
        c.execute('INSERT INTO user_skills(user_id,skill,level,xp) VALUES(?,?,1,10) ON CONFLICT(user_id,skill) DO UPDATE SET xp=xp+10,level=1+CAST((xp+10)/100 AS INTEGER)',(uid,skill))
    v3_log(uid,'training',skill,0,10); await q.answer('تمرین انجام شد.'); await v3_skills(q,uid)


async def v3_owner_set_role(q,uid,role):
    if uid!=GAME_OWNER_ID and uid not in V3_ADMIN_IDS: return await q.answer('فقط مالک.',show_alert=True)
    context_pending[q.message.chat_id]={'kind':'role','role':role,'uid':uid}
    prompt='chat_id|user_id' if role=='mayor' else 'user_id'
    await q.edit_message_text(f'👑 {prompt} را بفرست:')


async def v3_admin_economy(q,uid):
    if uid not in V3_ADMIN_IDS and uid!=GAME_OWNER_ID: return await q.answer('فقط مالک.',show_alert=True)
    with db() as c: n=c.execute('SELECT * FROM v3_country WHERE id=1').fetchone(); w=c.execute('SELECT * FROM v3_world WHERE id=1').fetchone()
    await q.edit_message_text(f"📊 اقتصاد\n\nخزانه کشور: {n['treasury']:,}\nGDP: {n['gdp']:,}\nتورم: {n['inflation']:.2f}%\nاقتصاد جهانی: {w['economy']:.2f}\nجرم: {w['crime']}%\nاشتغال: {w['employment']}%",reply_markup=InlineKeyboardMarkup([[v3_btn('↩️ مالک','owner|open')]]))


async def v3_handle_text(update,context):
    if not update.message or not update.effective_user: return False
    chat=update.effective_chat.id; uid=update.effective_user.id; pend=context_pending.get(chat)
    if not pend or pend.get('uid')!=uid: return False
    text=update.message.text or update.message.caption or ''
    kind=pend['kind']
    if kind=='ticket':
        with db() as c: cur=c.execute('INSERT INTO v3_tickets(user_id,category,text) VALUES(?,?,?)',(uid,pend['cat'],text)); tid=cur.lastrowid
        context_pending.pop(chat,None); await update.message.reply_text(f'🎫 تیکت #{tid} ثبت شد. پشتیبانی پاسخ خواهد داد.')
        return True
    if kind=='jobapp':
        with db() as c: c.execute('INSERT OR IGNORE INTO v3_applications(hiring_id,user_id,text) VALUES(?,?,?)',(pend['hid'],uid,text))
        context_pending.pop(chat,None); await update.message.reply_text('✅ درخواست استخدام ثبت شد.')
        return True
    if kind=='ticket_reply':
        tid=pend['tid']; with_db=False
        with db() as c: c.execute('INSERT INTO v3_ticket_messages(ticket_id,sender_id,text) VALUES(?,?,?)',(tid,uid,text)); c.execute('UPDATE v3_tickets SET updated_at=CURRENT_TIMESTAMP WHERE id=?',(tid,))
        context_pending.pop(chat,None); await update.message.reply_text('✉️ پاسخ ثبت شد.')
        with db() as c: t=c.execute('SELECT user_id FROM v3_tickets WHERE id=?',(tid,)).fetchone()
        try: await context.bot.send_message(t['user_id'],f'🎫 پاسخ پشتیبانی برای تیکت #{tid}:\n{text}')
        except Exception: pass
        return True
    if kind=='role':
        try: target=int(text.strip())
        except: await update.message.reply_text('ID نامعتبر است.'); return True
        role=pend['role']
        if role=='mayor':
            try: city_id,target=[int(x.strip()) for x in text.split('|',1)]
            except: await update.message.reply_text('برای شهردار: chat_id|user_id'); return True
            v3_set_city_role(city_id,target)
        else:
            with db() as c:
                if role=='king': c.execute('UPDATE v3_country SET king_id=? WHERE id=1',(target,))
                elif role=='president': c.execute('UPDATE v3_country SET president_id=? WHERE id=1',(target,))
        context_pending.pop(chat,None); await update.message.reply_text('✅ نقش ثبت شد.')
        return True
    return False


async def v3_callback(update,context):
    q=update.callback_query; data=q.data or ''
    if not data.startswith('v3|'): return False
    uid=q.from_user.id; v3_user(uid)
    try:
        p=data.split('|')
        if p[1]=='p':
            if p[2]=='open': await v3_menu(q,uid)
            elif p[2]=='profile': await v3_profile(q,uid)
            elif p[2]=='skills': await v3_skills(q,uid)
            elif p[2]=='jobs': await v3_jobs(q,uid)
            elif p[2]=='assets': await v3_assets_ui(q,uid)
            elif p[2]=='shop': await v3_shop(q,uid)
            elif p[2]=='market': await v3_market(q,uid)
            elif p[2]=='stocks': await v3_stocks(q,uid)
            elif p[2]=='train': await v3_train(q,uid)
        elif p[1]=='job': await v3_choose_job(q,uid,p[2])
        elif p[1]=='shop' and p[2]=='buy': await v3_buy_shop(q,uid,p[3])
        elif p[1]=='market':
            if p[2]=='buy':
                lid=int(p[3]);
                with db() as c: r=c.execute("SELECT * FROM v3_player_market WHERE id=? AND status='open'",(lid,)).fetchone()
                if not r or r['seller_id']==uid: return await q.answer('آگهی معتبر نیست.',show_alert=True)
                u=v3_user(uid)
                if u['cash']<r['price']: return await q.answer('موجودی کافی نیست.',show_alert=True)
                with db() as c:
                    c.execute('UPDATE users SET cash=cash-? WHERE user_id=?',(r['price'],uid)); c.execute('UPDATE users SET cash=cash+? WHERE user_id=?',(r['price'],r['seller_id'])); c.execute("UPDATE v3_player_market SET buyer_id=?,status='sold' WHERE id=?",(uid,lid))
                    if r['item_type']=='property': c.execute('UPDATE user_properties SET user_id=? WHERE id=? AND user_id=?',(uid,r['item_id'],r['seller_id']))
                    elif r['item_type']=='vehicle': c.execute('UPDATE user_vehicles SET user_id=? WHERE id=? AND user_id=?',(uid,r['item_id'],r['seller_id']))
                v3_log(uid,'market_buy',r['title'],-r['price'],8); await q.answer('معامله کامل شد.'); await v3_market(q,uid)
            elif p[2]=='sell': context_pending[q.message.chat_id]={'kind':'market','uid':uid}; await q.edit_message_text('➕ برای ثبت آگهی این قالب را در یک پیام بفرست:\nنوع|شناسه دارایی|عنوان|قیمت\nمثال: property|12|آپارتمان|250000')
        elif p[1]=='stock':
            if p[2]=='buy': await v3_stock_buy(q,uid,p[3])
            elif p[2]=='portfolio': await v3_stocks(q,uid)
        elif p[1]=='train': await v3_train_do(q,uid,p[2])
        elif p[1]=='city':
            if p[2]=='open': await v3_city(q,uid)
        elif p[1]=='nation':
            if p[2]=='open': await v3_nation(q,uid)
        elif p[1]=='mayor':
            if p[2]=='open': await v3_mayor(q,uid)
            else:
                sid=p[3]
                if not v3_session_ok(sid,uid,q.message.chat_id,'mayor',q.message.chat_id): return await q.answer('🔒 پنل منقضی یا غیرمعتبر است.',show_alert=True)
                await v3_mayor_action(q,uid,sid,p[2])
        elif p[1]=='gov':
            if p[2]=='open': await v3_gov(q,uid)
            else: await v3_gov_action(q,uid,p[3],p[2])
        elif p[1]=='owner':
            if p[2]=='open': await v3_owner(q,uid)
            elif p[2] in ('king','president','mayor'): await v3_owner_set_role(q,uid,p[2])
            elif p[2]=='economy': await v3_admin_economy(q,uid)
            elif p[2]=='news':
                context_pending[q.message.chat_id]={'kind':'news','uid':uid}; await q.edit_message_text('عنوان خبر و سپس متن را با | جدا کن: عنوان|متن')
        elif p[1]=='ticket':
            if p[2]=='open': await v3_ticket(q,uid)
            elif p[2]=='cat': await v3_ticket_category(q,uid,p[3])
            elif p[2]=='admin' and len(p)>3: await v3_ticket_admin_view(q,uid,int(p[3]))
            elif p[2]=='admin': await v3_ticket_admin(q,uid)
            elif p[2]=='reply': context_pending[q.message.chat_id]={'kind':'ticket_reply','uid':uid,'tid':int(p[3])}; await q.edit_message_text('پاسخ تیکت را بفرست:')
            elif p[2]=='close':
                if uid not in V3_ADMIN_IDS and uid!=GAME_OWNER_ID: return await q.answer('فقط ادمین.',show_alert=True)
                with db() as c: c.execute("UPDATE v3_tickets SET status='closed' WHERE id=?",(int(p[3]),))
                await q.answer('تیکت بسته شد.')
        elif p[1]=='hire':
            if p[2]=='list': await v3_hiring_list(q,uid,p[3])
            elif p[2]=='apply': await v3_apply(q,uid,int(p[3]))
            else:
                scope=p[2];
                if uid not in V3_ADMIN_IDS and uid!=GAME_OWNER_ID:
                    # رئیس بخش/شهردار/رئیس‌جمهور بعداً از جدول chiefs مجاز می‌شود
                    return await q.answer('برای ساخت آگهی باید رئیس بخش یا مقام مجاز باشی.',show_alert=True)
                context_pending[q.message.chat_id]={'kind':'hiring','uid':uid,'scope':scope}; await q.edit_message_text('آگهی را با قالب زیر بفرست:\nعنوان|مهارت|حداقل سطح|حقوق|توضیح')
        elif p[1]=='election':
            if p[2] in ('national','city'): await v3_election(q,uid,p[2] if p[2]=='national' else 'city')
            elif p[2]=='candidate': await v3_candidate(q,uid,int(p[3]),p[4])
            elif p[2]=='vote': await v3_vote(q,uid,int(p[3]),int(p[4]),p[5] if len(p)>5 else 'national')
            elif p[2]=='finish': await v3_finish_election(q,uid,int(p[3]),p[4],context.bot)
            elif p[2]=='news':
                if uid not in V3_ADMIN_IDS and uid!=GAME_OWNER_ID: return await q.answer('فقط مالک/ادمین.',show_alert=True)
                await v3_send_news(context.bot,'🗳 انتخابات Life RP',f'انتخابات فعال است. برای رأی دادن وارد بازی شوید.')
        elif p[1]=='news':
            with db() as c: rows=c.execute('SELECT * FROM v3_news ORDER BY id DESC LIMIT 10').fetchall()
            text='📰 <b>اخبار Life RP</b>\n━━━━━━━━━━━━\n'+''.join(f"• <b>{r['title']}</b> — {r['body']}\n" for r in rows)
            await q.edit_message_text(text[:4000],parse_mode='HTML',reply_markup=InlineKeyboardMarkup([[v3_btn('↩️ بازگشت','p|open')]]))
        await q.answer()
    except Exception as e:
        logger.exception('v3 callback: %s',e); await q.answer('⚠️ عملیات ناموفق بود.',show_alert=True)
    return True


async def v3_text_router(update,context):
    if not update.message: return False
    chat=update.effective_chat.id; pend=context_pending.get(chat)
    if not pend: return False
    uid=update.effective_user.id
    if pend.get('uid')!=uid: return False
    text=update.message.text or update.message.caption or ''
    kind=pend['kind']
    if kind=='market':
        try: typ,item_id,title,price=[x.strip() for x in text.split('|',3)]; item_id=int(item_id); price=int(price)
        except: await update.message.reply_text('فرمت اشتباه است.'); return True
        if typ not in ('property','vehicle') or price<=0: await update.message.reply_text('نوع یا قیمت نامعتبر.'); return True
        with db() as c:
            table='user_properties' if typ=='property' else 'user_vehicles'; key='prop_key' if typ=='property' else 'veh_key'
            r=c.execute(f'SELECT * FROM {table} WHERE id=? AND user_id=?',(item_id,uid)).fetchone()
            if not r: await update.message.reply_text('این دارایی متعلق به تو نیست.'); return True
            c.execute('INSERT INTO v3_player_market(seller_id,item_type,item_id,title,price) VALUES(?,?,?,?,?)',(uid,typ,item_id,title,price))
        context_pending.pop(chat,None); await update.message.reply_text('📢 آگهی ثبت شد و دارایی تا زمان فروش قابل معامله است.'); return True
    if kind=='hiring':
        try: title,skill,mins,salary,desc=[x.strip() for x in text.split('|',4)]; mins=int(mins); salary=int(salary)
        except: await update.message.reply_text('فرمت اشتباه است.'); return True
        scope=pend['scope']; sid=1 if scope=='national' else chat
        with db() as c: c.execute('INSERT INTO v3_hiring(scope,scope_id,title,skill,min_skill,salary,description) VALUES(?,?,?,?,?,?,?)',(scope,sid,title,skill,mins,salary,desc))
        context_pending.pop(chat,None); await update.message.reply_text('📢 آگهی استخدام منتشر شد.'); return True
    if kind=='news':
        if uid not in V3_ADMIN_IDS and uid!=GAME_OWNER_ID: return True
        try: title,body=text.split('|',1)
        except: await update.message.reply_text('فرمت: عنوان|متن'); return True
        context_pending.pop(chat,None); await v3_send_news(context.bot,title,body); await update.message.reply_text('📰 خبر در کانال منتشر شد.'); return True
    return await v3_handle_text(update,context)


async def v3_economy_tick(context):
    try:
        with db() as c:
            c.execute('UPDATE v3_world SET day=day+1, inflation=MAX(0.1,inflation+((RANDOM()%21)-10)/100.0), economy=MAX(0.5,MIN(2.0,economy+((RANDOM()%21)-10)/1000.0)) WHERE id=1')
            c.execute('UPDATE v3_stocks SET price=MAX(100,CAST(price*(1+((RANDOM()%101)-50)/10000.0) AS INTEGER))')
            c.execute("UPDATE users SET hunger=MIN(100,hunger+4),energy=MAX(0,energy-2),stress=MIN(100,stress+1),sleep=MAX(0,sleep-3)")
            cities=c.execute('SELECT * FROM v3_cities').fetchall()
            for city in cities:
                income=max(0,int(city['population']*(city['tax']/100)*1200*city['industry']/50))
                c.execute('UPDATE v3_cities SET treasury=treasury+?,last_income=? WHERE chat_id=?',(income,time.time(),city['chat_id']))
                if income: c.execute('UPDATE v3_country SET treasury=treasury+? WHERE id=1',(int(income*0.12),))
            # درآمد دوره‌ای ملک‌ها؛ مالکیت معنی اقتصادی دارد.
            props=c.execute('SELECT user_id,prop_key FROM user_properties').fetchall()
            for pr in props:
                inc=int(PROPERTIES.get(pr['prop_key'],{}).get('income',0))
                if inc:
                    c.execute('UPDATE users SET bank=bank+? WHERE user_id=?',(inc,pr['user_id']))
                    c.execute('INSERT INTO transactions(user_id,kind,amount,note) VALUES(?,?,?,?)',(pr['user_id'],'property_income',inc,PROPERTIES.get(pr['prop_key'],{}).get('name','ملک')))
            c.execute("UPDATE v3_country SET inflation=MAX(0.1,inflation+((RANDOM()%11)-5)/100.0),gdp=MAX(1000000,CAST(gdp*(1+((RANDOM()%11)-5)/10000.0) AS INTEGER)) WHERE id=1")
    except Exception as e: logger.warning('economy tick: %s',e)


async def v3_salary_tick(context):
    try:
        with db() as c:
            rows=c.execute('SELECT * FROM v3_employment WHERE active=1').fetchall()
            for r in rows:
                c.execute('UPDATE users SET bank=bank+? WHERE user_id=?',(r['salary'],r['user_id']))
                c.execute('INSERT INTO v3_salary_log(user_id,role,amount) VALUES(?,?,?)',(r['user_id'],'employment',r['salary']))
            n=c.execute('SELECT * FROM v3_country WHERE id=1').fetchone()
            for role,uid,sal in [('پادشاه',n['king_id'],500000),('رئیس‌جمهور',n['president_id'],180000)]:
                if uid:
                    c.execute('UPDATE users SET bank=bank+? WHERE user_id=?',(sal,uid)); c.execute('INSERT INTO v3_salary_log(user_id,role,amount) VALUES(?,?,?)',(uid,role,sal))
            for city in c.execute('SELECT chat_id,mayor_id FROM v3_cities WHERE mayor_id IS NOT NULL').fetchall():
                c.execute('UPDATE users SET bank=bank+? WHERE user_id=?',(90000,city['mayor_id'])); c.execute('INSERT INTO v3_salary_log(user_id,role,amount) VALUES(?,?,?)',(city['mayor_id'],'شهردار',90000))
            for d in c.execute('SELECT chief_id FROM v3_departments WHERE chief_id IS NOT NULL AND active=1').fetchall():
                c.execute('UPDATE users SET bank=bank+? WHERE user_id=?',(65000,d['chief_id'])); c.execute('INSERT INTO v3_salary_log(user_id,role,amount) VALUES(?,?,?)',(d['chief_id'],'رئیس بخش',65000))
    except Exception as e: logger.warning('salary tick: %s',e)


context_pending={}

def main():
    token = os.environ.get('BOT_TOKEN','').strip()
    if not token:
        raise SystemExit('BOT_TOKEN را در Environment Variable قرار بده.')
    init_db(); init_combined_db(); v3_db_init()
    app=Application.builder().token(token).post_init(setup_bot_commands).build()
    # V3 first: all new panels and security checks are handled before legacy callbacks.
    app.add_handler(CallbackQueryHandler(v3_callback, pattern=r'^v3\|'), group=-10)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, v3_text_router), group=-10)
    app.add_handler(CommandHandler('life', liferp_menu_command), group=0)
    app.add_handler(CommandHandler('liferp', liferp_menu_command), group=0)
    app.add_handler(CommandHandler('start', cmd_start), group=1)
    app.add_handler(CommandHandler('help', cmd_help), group=1)
    app.add_handler(CommandHandler('profile', cmd_profile), group=1)
    app.add_handler(CommandHandler('setbio', cmd_setbio), group=1)
    app.add_handler(CommandHandler('jobs', cmd_jobs), group=1)
    app.add_handler(CommandHandler('apply', cmd_apply), group=1)
    app.add_handler(CommandHandler('work', cmd_work), group=1)
    app.add_handler(CommandHandler('skills', cmd_skills), group=1)
    app.add_handler(CommandHandler('train', cmd_train), group=1)
    app.add_handler(CommandHandler('sleep', cmd_sleep), group=1)
    app.add_handler(CommandHandler('eat', cmd_eat), group=1)
    app.add_handler(CommandHandler('bank', cmd_bank), group=1)
    app.add_handler(CommandHandler('deposit', cmd_deposit), group=1)
    app.add_handler(CommandHandler('withdraw', cmd_withdraw), group=1)
    app.add_handler(CommandHandler('loan', cmd_loan), group=1)
    app.add_handler(CommandHandler('payloan', cmd_payloan), group=1)
    app.add_handler(CommandHandler('shop', cmd_shop), group=1)
    app.add_handler(CommandHandler('buyprop', cmd_buyprop), group=1)
    app.add_handler(CommandHandler('buyveh', cmd_buyveh), group=1)
    app.add_handler(CommandHandler('myassets', cmd_myassets), group=1)
    app.add_handler(CommandHandler('mission', cmd_mission), group=1)
    app.add_handler(CommandHandler('claim', cmd_claim), group=1)
    app.add_handler(CommandHandler('top', cmd_top), group=1)
    app.add_handler(CommandHandler('give', cmd_give), group=1)
    register_phase2(app); register_phase4(app); register_menu(app); register_liferp_v2(app)
    if app.job_queue:
        app.job_queue.run_repeating(periodic_decay,interval=600,first=600)
        app.job_queue.run_repeating(judicial_release_job,interval=60,first=60)
        app.job_queue.run_repeating(pay_role_salaries,interval=86400,first=86400)
        app.job_queue.run_repeating(v3_economy_tick,interval=3600,first=60)
        app.job_queue.run_repeating(v3_salary_tick,interval=86400,first=120)
    logger.info('Life RP V3 starting; news=%s owner=%s',NEWS_CHANNEL_ID,GAME_OWNER_ID)
    app.run_polling(allowed_updates=Update.ALL_TYPES)



# =============================================================================
# LIFE RP V4 — WORLD ENGINE
# A connected Life RP layer built on top of the existing V1/V2/V3 systems.
# =============================================================================
V4_OWNER_ID = 5888377320
V4_ADMIN_IDS = {5888377320}
V4_NEWS_CHANNEL_ID = -1001465731038

V4_SKILLS = {
    "programming":"برنامه‌نویسی","medicine":"پزشکی","engineering":"مهندسی",
    "management":"مدیریت","law":"حقوق","security":"امنیت","military":"نظامی",
    "finance":"مالی","sales":"فروش","driving":"رانندگی","cooking":"آشپزی",
    "farming":"کشاورزی","media":"رسانه","teaching":"آموزش","investing":"سرمایه‌گذاری",
    "repair":"فنی","communication":"ارتباطات",
}

V4_JOBS = {
    "worker":("کارگر","repair",1200,1),"seller":("فروشنده","sales",1800,1),
    "driver":("راننده","driving",2400,1),"cook":("آشپز","cooking",2700,1),
    "teacher":("معلم","teaching",4200,2),"nurse":("پرستار","medicine",4800,2),
    "engineer":("مهندس","engineering",6500,3),"developer":("برنامه‌نویس","programming",8000,3),
    "lawyer":("وکیل","law",7200,3),"doctor":("پزشک","medicine",11000,5),
    "manager":("مدیر","management",12500,5),"investor":("تحلیلگر سرمایه‌گذاری","investing",15000,5),
    "police":("مامور پلیس","security",6000,3),"soldier":("سرباز","military",5200,2),
    "journalist":("خبرنگار","media",5000,2),"accountant":("حسابدار","finance",6000,3),
}

def v4_btn(text,data):
    return InlineKeyboardButton(text,callback_data="life4|"+data)

def v4_db():
    return db()

def v4_init_db():
    with v4_db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS v4_sessions(
          sid TEXT PRIMARY KEY,user_id INTEGER,chat_id INTEGER,panel TEXT,entity_id TEXT,
          created REAL,expires REAL
        );
        CREATE TABLE IF NOT EXISTS v4_orgs(
          id INTEGER PRIMARY KEY AUTOINCREMENT,scope TEXT,scope_id TEXT,name TEXT,
          type TEXT,budget INTEGER DEFAULT 0,treasury INTEGER DEFAULT 0,chief_id INTEGER,
          salary INTEGER DEFAULT 0,active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS v4_hires(
          id INTEGER PRIMARY KEY AUTOINCREMENT,org_id INTEGER,user_id INTEGER,job TEXT,
          salary INTEGER,skill TEXT,status TEXT DEFAULT 'pending',created REAL DEFAULT 0,
          reviewed_by INTEGER
        );
        CREATE TABLE IF NOT EXISTS v4_tasks(
          id INTEGER PRIMARY KEY AUTOINCREMENT,org_id INTEGER,user_id INTEGER,title TEXT,
          reward INTEGER,skill TEXT,min_skill INTEGER DEFAULT 1,status TEXT DEFAULT 'open',
          result TEXT,created REAL DEFAULT 0,completed REAL
        );
        CREATE TABLE IF NOT EXISTS v4_orders(
          id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,title TEXT,description TEXT,
          price INTEGER,kind TEXT,status TEXT DEFAULT 'open',created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v4_market(
          id INTEGER PRIMARY KEY AUTOINCREMENT,seller INTEGER,item_type TEXT,item_id INTEGER,
          title TEXT,price INTEGER,status TEXT DEFAULT 'open',buyer INTEGER
        );
        CREATE TABLE IF NOT EXISTS v4_government_logs(
          id INTEGER PRIMARY KEY AUTOINCREMENT,actor INTEGER,action TEXT,amount INTEGER DEFAULT 0,
          entity TEXT,created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v4_news(
          id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,body TEXT,kind TEXT,created REAL DEFAULT 0,sent INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v4_tickets(
          id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,category TEXT,text TEXT,
          status TEXT DEFAULT 'open',created REAL DEFAULT 0,assigned INTEGER
        );
        CREATE TABLE IF NOT EXISTS v4_ticket_messages(
          id INTEGER PRIMARY KEY AUTOINCREMENT,ticket_id INTEGER,sender INTEGER,text TEXT,
          kind TEXT DEFAULT 'text',created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v4_elections(
          id INTEGER PRIMARY KEY AUTOINCREMENT,scope TEXT,scope_id TEXT,office TEXT,
          status TEXT DEFAULT 'open',started REAL DEFAULT 0,ends REAL DEFAULT 0,winner INTEGER
        );
        CREATE TABLE IF NOT EXISTS v4_candidates(
          election_id INTEGER,user_id INTEGER,manifesto TEXT DEFAULT '',
          PRIMARY KEY(election_id,user_id)
        );
        CREATE TABLE IF NOT EXISTS v4_votes(
          election_id INTEGER,voter INTEGER,candidate INTEGER,created REAL DEFAULT 0,
          PRIMARY KEY(election_id,voter)
        );
        CREATE TABLE IF NOT EXISTS v4_ledger(
          id INTEGER PRIMARY KEY AUTOINCREMENT,from_id INTEGER,to_id INTEGER,amount INTEGER,
          reason TEXT,created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v4_companies(
          id INTEGER PRIMARY KEY AUTOINCREMENT,owner INTEGER,name TEXT,capital INTEGER,
          revenue INTEGER DEFAULT 0,employees INTEGER DEFAULT 0,sector TEXT,
          level INTEGER DEFAULT 1,active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS v4_company_jobs(
          id INTEGER PRIMARY KEY AUTOINCREMENT,company_id INTEGER,title TEXT,skill TEXT,
          min_skill INTEGER,salary INTEGER,description TEXT,status TEXT DEFAULT 'open'
        );
        CREATE TABLE IF NOT EXISTS v4_company_apps(
          id INTEGER PRIMARY KEY AUTOINCREMENT,job_id INTEGER,user_id INTEGER,
          text TEXT,status TEXT DEFAULT 'pending',created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v4_asset_market(
          id INTEGER PRIMARY KEY AUTOINCREMENT,seller INTEGER,asset_type TEXT,asset_id INTEGER,
          price INTEGER,status TEXT DEFAULT 'open',buyer INTEGER
        );
        CREATE TABLE IF NOT EXISTS v4_departments(
          id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,scope TEXT,scope_id TEXT,
          chief_id INTEGER,budget INTEGER DEFAULT 0,salary INTEGER DEFAULT 0,mission TEXT
        );
        CREATE TABLE IF NOT EXISTS v4_player_stats(
          user_id INTEGER PRIMARY KEY,life_xp INTEGER DEFAULT 0,reputation INTEGER DEFAULT 50,
          happiness INTEGER DEFAULT 70,career_xp INTEGER DEFAULT 0,social_xp INTEGER DEFAULT 0,
          political_xp INTEGER DEFAULT 0
        );
        """)
        # Seed national departments once.
        n=c.execute("SELECT COUNT(*) n FROM v4_departments WHERE scope='national'").fetchone()["n"]
        if n==0:
            deps=[
                ("وزارت اقتصاد","finance",50000000,250000,"مدیریت درآمد، مالیات و ثبات اقتصادی"),
                ("وزارت بهداشت","health",35000000,220000,"سلامت و بیمارستان‌ها"),
                ("وزارت آموزش","education",30000000,210000,"مدارس، دانشگاه و مهارت"),
                ("وزارت کشور","interior",40000000,230000,"امنیت داخلی و مدیریت شهرها"),
                ("وزارت دفاع","defense",60000000,300000,"ارتش و دفاع"),
                ("وزارت زیرساخت","infra",45000000,230000,"راه، حمل‌ونقل و پروژه‌های ملی"),
                ("وزارت رسانه","media",15000000,180000,"اطلاع‌رسانی و اخبار"),
            ]
            for name,typ,bud,sal,mission in deps:
                c.execute("INSERT INTO v4_departments(name,scope,scope_id,budget,salary,mission) VALUES(?,?,?,?,?,?)",
                          (name,"national","1",bud,sal,mission))

def v4_session(uid,chat,panel,entity="0",ttl=900):
    import secrets
    sid=secrets.token_urlsafe(12)
    now=time.time()
    with v4_db() as c:
        c.execute("INSERT INTO v4_sessions VALUES(?,?,?,?,?,?,?)",
                  (sid,uid,chat,panel,str(entity),now,now+ttl))
    return sid

def v4_auth(sid,uid,chat,panel,entity=None):
    with v4_db() as c:
        r=c.execute("SELECT * FROM v4_sessions WHERE sid=?",(sid,)).fetchone()
    if not r or r["user_id"]!=uid or r["chat_id"]!=chat or r["panel"]!=panel or r["expires"]<time.time():
        return False
    return entity is None or str(entity)==str(r["entity_id"])

def v4_admin(uid): return uid in V4_ADMIN_IDS or uid==V4_OWNER_ID

def v4_owner(uid): return uid==V4_OWNER_ID

def v4_user(uid):
    u=get_user(uid)
    if not u: u=ensure_user(uid,str(uid))
    with v4_db() as c:
        c.execute("INSERT OR IGNORE INTO v4_player_stats(user_id) VALUES(?)",(uid,))
    return get_user(uid)

def v4_add_xp(uid,amount,kind="life"):
    with v4_db() as c:
        c.execute(f"UPDATE v4_player_stats SET {kind}_xp={kind}_xp+? WHERE user_id=?",(amount,uid))
        c.execute("UPDATE users SET xp=xp+? WHERE user_id=?",(amount,uid))

def v4_level(uid):
    u=v4_user(uid)
    with v4_db() as c: s=c.execute("SELECT * FROM v4_player_stats WHERE user_id=?",(uid,)).fetchone()
    nw=net_worth(u)
    # Hybrid progression: life XP + net worth + reputation. Wealth alone cannot carry a new player.
    score=int(s["life_xp"] + s["career_xp"]*2 + s["social_xp"] + s["political_xp"]*2 + nw//50000)
    thresholds=[(0,"تازه‌وارد"),(100,"شهروند"),(300,"شاغل"),(700,"شهروند فعال"),
                (1500,"متخصص"),(3000,"حرفه‌ای"),(6000,"کارآفرین"),(12000,"بانفوذ"),
                (25000,"نخبه"),(50000,"سرمایه‌دار"),(100000,"اسطوره")]
    lvl=1; title=thresholds[0][1]
    for i,(t,n) in enumerate(thresholds,1):
        if score>=t: lvl,title=i,n
    return lvl,title,score,s

def v4_main_menu(uid,private=True):
    rows=[
      [v4_btn("👤 پروفایل","profile"),v4_btn("💼 کار و شغل","jobs")],
      [v4_btn("📚 مهارت‌ها","skills"),v4_btn("🎓 تحصیل","study")],
      [v4_btn("💰 اقتصاد من","money"),v4_btn("🏦 بانک","bank")],
      [v4_btn("🏠 املاک","assets"),v4_btn("🚗 خودرو","vehicles")],
      [v4_btn("📈 بورس","stocks"),v4_btn("🤝 بازار کاربران","market")],
      [v4_btn("👨‍👩‍👧 روابط","social"),v4_btn("⚖️ قانون و سوابق","law")],
      [v4_btn("🏙️ شهر","city"),v4_btn("🇮🇷 کشور","nation")],
      [v4_btn("📰 اخبار","news"),v4_btn("🎫 پشتیبانی","ticket")],
      [v4_btn("🎯 مأموریت‌ها","missions"),v4_btn("🌍 رویدادهای جهان","events")],
    ]
    if v4_owner(uid): rows.append([v4_btn("👑 پنل پادشاه","king"),v4_btn("🛠 مالک بازی","owner")])
    elif v4_admin(uid): rows.append([v4_btn("🛠 پنل مدیریت","owner")])
    return InlineKeyboardMarkup(rows)

async def v4_menu(q,uid):
    u=v4_user(uid); lvl,title,score,s=v4_level(uid)
    text=(f"🌍 <b>Life RP</b>\n━━━━━━━━━━━━\n"
          f"👤 {q.from_user.first_name}\n🎚 سطح زندگی: {lvl} — {title}\n"
          f"✨ امتیاز زندگی: {score}\n💰 نقد: {u['cash']:,}\n🏦 بانک: {u['bank']:,}\n"
          f"💎 دارایی خالص: {net_worth(u):,}\n❤️ سلامت {u['health']} | ⚡ انرژی {u['energy']}\n"
          f"😊 شادی {u['happiness']} | 😰 استرس {u['stress']}\n⭐ اعتبار اجتماعی: {s['reputation']}")
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=v4_main_menu(uid,q.message.chat.type=="private"))

async def v4_profile(q,uid):
    u=v4_user(uid); lvl,title,score,s=v4_level(uid)
    job=JOBS.get(u.get("job"),{}).get("name","بیکار") if u.get("job") else "بیکار"
    with v4_db() as c:
        jobs=c.execute("SELECT COUNT(*) n FROM v4_hires WHERE user_id=? AND status='active'",(uid,)).fetchone()["n"]
    text=(f"👤 <b>شناسنامه زندگی</b>\n━━━━━━━━━━━━\n"
          f"نام: {q.from_user.first_name}\nسن: {u['age']}\n💼 شغل: {job}\n"
          f"🎚 سطح {lvl} — {title}\n✨ XP: {score}\n💎 دارایی: {net_worth(u):,}\n"
          f"💰 نقد {u['cash']:,} | 🏦 بانک {u['bank']:,}\n"
          f"❤️ {u['health']} | 😊 {u['happiness']} | 😰 {u['stress']} | 🍔 {u['hunger']} | 😴 {u['sleep']}\n"
          f"⭐ اعتبار {s['reputation']}\n🏢 استخدام سازمانی فعال: {jobs}")
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(
        [[v4_btn("📚 مهارت‌ها","skills"),v4_btn("🎯 مأموریت‌ها","missions")],
         [v4_btn("↩️ منوی اصلی","home")]]))

async def v4_skills(q,uid):
    v4_user(uid)
    with v4_db() as c: rows=c.execute("SELECT skill,level,xp FROM user_skills WHERE user_id=? ORDER BY level DESC,skill",(uid,)).fetchall()
    text="📚 <b>مهارت‌های من</b>\n━━━━━━━━━━━━\n"
    for r in rows: text+=f"• {V4_SKILLS.get(r['skill'],r['skill'])}: سطح {r['level']} | XP {r['xp']}/{r['level']*100}\n"
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(
        [[v4_btn("🏋️ تمرین","train"),v4_btn("💼 شغل‌ها","jobs")],[v4_btn("↩️ بازگشت","home")]]))

async def v4_jobs(q,uid):
    v4_user(uid)
    with v4_db() as c:
        ads=c.execute("SELECT h.*,o.name org FROM v4_hires h LEFT JOIN v4_orgs o ON o.id=h.org_id WHERE h.status='ad' ORDER BY h.id DESC LIMIT 20").fetchall()
    text="💼 <b>بازار کار و استخدام</b>\n━━━━━━━━━━━━\n"
    text+="مشاغل آزاد:\n"
    for k,(n,sk,pay,ml) in V4_JOBS.items(): text+=f"• {n} — {pay:,}💰 | {V4_SKILLS[sk]} سطح {ml}\n"
    text+="\n📢 آگهی‌های سازمانی:\n"
    if ads:
        text+="".join(f"#{r['id']} {r['org'] or 'سازمان'} — {r['job']} — {r['salary']:,}💰\n" for r in ads)
    else:text+="فعلاً آگهی‌ای نیست.\n"
    await q.edit_message_text(text[:4000],parse_mode="HTML",reply_markup=InlineKeyboardMarkup(
        [[v4_btn("⚡ انجام کار","work"),v4_btn("📢 آگهی‌ها","jobs_ads")],
         [v4_btn("🏋️ تمرین مهارت","train")],[v4_btn("↩️ منوی اصلی","home")]]))

async def v4_work(q,uid):
    u=v4_user(uid)
    if not u.get("job"): return await q.answer("اول یک شغل انتخاب یا درخواست استخدام ثبت کن.",show_alert=True)
    key=u["job"]; j=JOBS.get(key) or V4_JOBS.get(key)
    if not j:return await q.answer("شغل فعلی نامعتبر است.",show_alert=True)
    if isinstance(j,tuple): name,skill,pay,minskill=j; energy=18
    else: name,skill,pay,minskill=j["name"],j["skill"],j["pay"],j["min_level"]; energy=j["energy"]
    s=get_skill(uid,skill) if skill else {"level":1}
    if s["level"]<minskill:return await q.answer(f"مهارت {V4_SKILLS.get(skill,skill)} باید سطح {minskill} باشد.",show_alert=True)
    if u["energy"]<energy:return await q.answer("انرژی کافی نداری؛ استراحت کن.",show_alert=True)
    performance=random.uniform(.85,1.20)*(1+.04*(s["level"]-minskill))
    earned=max(1,int(pay*performance))
    update_user(uid,cash=u["cash"]+earned,energy=max(0,u["energy"]-energy),
                stress=min(100,u["stress"]+6),hunger=min(100,u["hunger"]+6),xp=u["xp"]+12,last_work=time.time())
    add_skill_xp(uid,skill,12)
    v4_add_xp(uid,15,"career")
    log_tx(uid,"work",earned,name)
    await q.answer(f"شیفت انجام شد: +{earned:,} تومان")
    await v4_jobs(q,uid)

async def v4_train(q,uid):
    keys=list(V4_SKILLS.items())
    rows=[]
    for i in range(0,len(keys),2):
        row=[v4_btn(keys[i][1],f"train_do|{keys[i][0]}")]
        if i+1<len(keys): row.append(v4_btn(keys[i+1][1],f"train_do|{keys[i+1][0]}"))
        rows.append(row)
    rows.append([v4_btn("↩️ بازگشت","skills")])
    await q.edit_message_text("🏋️ <b>انتخاب مهارت برای تمرین</b>\nهر تمرین انرژی مصرف می‌کند و XP واقعی مهارت می‌دهد.",
                              parse_mode="HTML",reply_markup=InlineKeyboardMarkup(rows))

async def v4_train_do(q,uid,skill):
    if skill not in V4_SKILLS:return await q.answer("مهارت نامعتبر.",show_alert=True)
    u=v4_user(uid)
    if u["energy"]<12:return await q.answer("انرژی کافی نداری.",show_alert=True)
    gain=random.randint(8,18)+u["intelligence"]//5
    nl,up=add_skill_xp(uid,skill,gain)
    update_user(uid,energy=max(0,u["energy"]-12),intelligence=u["intelligence"]+1)
    v4_add_xp(uid,10,"career")
    await q.answer(f"+{gain} XP مهارت | سطح {nl}" + (" 🎉" if up else ""))
    await v4_skills(q,uid)

async def v4_money(q,uid):
    u=v4_user(uid)
    with v4_db() as c: tx=c.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 8",(uid,)).fetchall()
    text=f"💰 <bاقتصاد شخصی</b>\n━━━━━━━━━━━━\n💵 نقد: {u['cash']:,}\n🏦 بانک: {u['bank']:,}\n💳 وام: {u['loan_amount']:,}\n📊 اعتبار: {u['credit_score']}\n\nتراکنش‌های اخیر:\n"
    text+="".join(f"• {r['kind']}: {r['amount']:,} — {r['note']}\n" for r in tx) or "هنوز تراکنشی نیست."
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(
        [[v4_btn("🏦 بانک","bank"),v4_btn("🤝 انتقال","transfer")],[v4_btn("↩️ منوی اصلی","home")]]))

async def v4_bank(q,uid):
    u=v4_user(uid)
    await q.edit_message_text(f"🏦 <b>بانک</b>\n━━━━━━━━━━━━\nموجودی: {u['bank']:,}\nنقد: {u['cash']:,}\nاعتبار: {u['credit_score']}\nوام: {u['loan_amount']:,}\n\nبرای عملیات بانکی از دکمه‌های زیر استفاده کن.",
        parse_mode="HTML",reply_markup=InlineKeyboardMarkup([
        [v4_btn("💵 واریز","bank_deposit"),v4_btn("💸 برداشت","bank_withdraw")],
        [v4_btn("💳 وام","bank_loan"),v4_btn("↩️ اقتصاد من","money")]]))

async def v4_assets(q,uid):
    u=v4_user(uid)
    with v4_db() as c:
        p=c.execute("SELECT id,prop_key FROM user_properties WHERE user_id=?",(uid,)).fetchall()
        v=c.execute("SELECT id,veh_key FROM user_vehicles WHERE user_id=?",(uid,)).fetchall()
    text="🏠 <b>دارایی‌های من</b>\n━━━━━━━━━━━━\n"
    text+="املاک:\n"+("".join(f"#{r['id']} {PROPERTIES.get(r['prop_key'],{}).get('name',r['prop_key'])} | درآمد {PROPERTIES.get(r['prop_key'],{}).get('income',0):,}\n" for r in p) or "ندارم\n")
    text+="\n🚗 خودرو:\n"+("".join(f"#{r['id']} {VEHICLES.get(r['veh_key'],{}).get('name',r['veh_key'])}\n" for r in v) or "ندارم\n")
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(
        [[v4_btn("🛒 خرید ملک/خودرو","shop"),v4_btn("🤝 فروش دارایی","asset_sell")],
         [v4_btn("↩️ منوی اصلی","home")]]))

async def v4_shop(q,uid):
    rows=[]
    for k,p in PROPERTIES.items(): rows.append([v4_btn(f"🏠 {p['name']} | {p['price']:,}","buyprop|"+k)])
    for k,v in VEHICLES.items(): rows.append([v4_btn(f"🚗 {v['name']} | {v['price']:,}","buyveh|"+k)])
    rows.append([v4_btn("↩️ دارایی‌ها","assets")])
    await q.edit_message_text("🛒 <b>بازار دارایی</b>\nخرید دارایی از اقتصاد بازی کم می‌کند و دارایی مالک درآمد/کاربرد دارد.",
                              parse_mode="HTML",reply_markup=InlineKeyboardMarkup(rows))

async def v4_buyprop(q,uid,key):
    if key not in PROPERTIES:return await q.answer("ملک نامعتبر.",show_alert=True)
    u=v4_user(uid); p=PROPERTIES[key]; total=u["cash"]+u["bank"]
    if total<p["price"]:return await q.answer("سرمایه کافی نیست.",show_alert=True)
    fc=min(u["cash"],p["price"]); fb=p["price"]-fc
    with v4_db() as c:
        c.execute("UPDATE users SET cash=cash-?,bank=bank-? WHERE user_id=?",(fc,fb,uid))
        c.execute("INSERT INTO user_properties(user_id,prop_key) VALUES(?,?)",(uid,key))
    log_tx(uid,"property_purchase",-p["price"],p["name"]); v4_add_xp(uid,25)
    await q.answer("ملک خریداری شد.")
    await v4_assets(q,uid)

async def v4_buyveh(q,uid,key):
    if key not in VEHICLES:return await q.answer("وسیله نامعتبر.",show_alert=True)
    u=v4_user(uid); v=VEHICLES[key]; total=u["cash"]+u["bank"]
    if total<v["price"]:return await q.answer("سرمایه کافی نیست.",show_alert=True)
    fc=min(u["cash"],v["price"]); fb=v["price"]-fc
    with v4_db() as c:
        c.execute("UPDATE users SET cash=cash-?,bank=bank-?,happiness=MIN(100,happiness+?) WHERE user_id=?",(fc,fb,v["happiness"],uid))
        c.execute("INSERT INTO user_vehicles(user_id,veh_key) VALUES(?,?)",(uid,key))
    log_tx(uid,"vehicle_purchase",-v["price"],v["name"]); v4_add_xp(uid,15)
    await q.answer("وسیله نقلیه خریداری شد."); await v4_assets(q,uid)

async def v4_market(q,uid):
    with v4_db() as c: rows=c.execute("SELECT * FROM v4_market WHERE status='open' ORDER BY id DESC LIMIT 20").fetchall()
    text="🤝 <b>بازار کاربران</b>\n━━━━━━━━━━━━\nهر معامله انتقال مالکیت و ثبت مالی دارد.\n\n"
    text+="".join(f"#{r['id']} {r['title']} — {r['price']:,} تومان\n" for r in rows) or "آگهی‌ای نیست."
    kb=[[v4_btn(f"🛒 خرید #{r['id']}","mkt_buy|"+str(r["id"]))] for r in rows]
    kb += [[v4_btn("➕ ثبت سفارش/آگهی","mkt_new")],[v4_btn("↩️ منوی اصلی","home")]]
    await q.edit_message_text(text[:4000],parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb))

async def v4_stocks(q,uid):
    with v4_db() as c:
        stocks=c.execute("SELECT * FROM v3_stocks ORDER BY symbol").fetchall()
        port=c.execute("SELECT * FROM v3_portfolio WHERE user_id=? AND qty>0",(uid,)).fetchall()
    text="📈 <b>بورس Life RP</b>\n━━━━━━━━━━━━\n"
    text+="".join(f"• <b>{s['symbol']}</b> {s['name']} — {s['price']:,}\n" for s in stocks)
    text+="\nسبد من:\n"+("".join(f"{r['symbol']} × {r['qty']}\n" for r in port) or "خالی")
    kb=[]
    for s in stocks[:8]: kb.append([v4_btn(f"خرید {s['symbol']}","stock_buy|"+s["symbol"])])
    kb += [[v4_btn("📊 معاملات بورس","stock_trade")],[v4_btn("↩️ منوی اصلی","home")]]
    await q.edit_message_text(text[:4000],parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb))

async def v4_city(q,uid):
    chat=q.message.chat_id
    city=v3_ensure_city(chat)
    await q.edit_message_text(
      f"🏙️ <b>{city['name']}</b>\n━━━━━━━━━━━━\n💰 خزانه {city['treasury']:,}\n"
      f"👥 جمعیت {city['population']}\n💸 مالیات {city['tax']}%\n⭐ رضایت {city['approval']}%\n"
      f"🏗 توسعه {city['development']} | 🏭 صنعت {city['industry']}\n👑 شهردار: {city['mayor_id'] or 'ندارد'}",
      parse_mode="HTML",reply_markup=InlineKeyboardMarkup([
        [v4_btn("🏛 پنل شهردار","mayor"),v4_btn("🗳 انتخابات شهردار","election_city")],
        [v4_btn("👮 پلیس","org_city|police"),v4_btn("⚖️ دادگستری","org_city|court")],
        [v4_btn("🏥 بیمارستان","org_city|hospital"),v4_btn("🏢 شرکت‌ها","companies")],
        [v4_btn("📢 استخدام‌های شهر","jobs_ads_city"),v4_btn("📰 اخبار شهر","news")],
        [v4_btn("↩️ منوی اصلی","home")]]))

async def v4_nation(q,uid):
    with v4_db() as c: n=c.execute("SELECT * FROM v3_country WHERE id=1").fetchone()
    text=(f"🇮🇷 <b>{n['name']}</b>\n━━━━━━━━━━━━\n👑 پادشاه: {n['king_id'] or 'ندارد'}\n"
          f"🏛 رئیس‌جمهور: {n['president_id'] or 'ندارد'}\n💰 خزانه: {n['treasury']:,}\n"
          f"📈 GDP: {n['gdp']:,}\n💸 تورم: {n['inflation']:.1f}%\n⭐ رضایت: {n['approval']}%\n"
          f"🛡 امنیت: {n['security']} | 🏥 سلامت: {n['health']} | 🎓 آموزش: {n['education']} | 🛣 زیرساخت: {n['infrastructure']}")
    kb=[[v4_btn("🏛 پنل رئیس‌جمهور","president"),v4_btn("🗳 انتخابات ریاست‌جمهوری","election_national")],
        [v4_btn("🏢 وزارتخانه‌ها","ministries"),v4_btn("🏙 شهرها","cities")],
        [v4_btn("📰 اخبار کشور","news")],[v4_btn("↩️ منوی اصلی","home")]]
    if v4_owner(uid): kb.insert(0,[v4_btn("👑 پادشاه","king")])
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb))

async def v4_king(q,uid):
    if not v4_owner(uid):return await q.answer("فقط مالک/پادشاه.",show_alert=True)
    with v4_db() as c: n=c.execute("SELECT * FROM v3_country WHERE id=1").fetchone()
    sid=v4_session(uid,q.message.chat_id,"king","1")
    text=(f"👑 <b>کاخ پادشاهی</b>\n━━━━━━━━━━━━\nمالک: {V4_OWNER_ID}\n"
          f"پادشاه: {n['king_id'] or uid}\nرئیس‌جمهور: {n['president_id'] or 'تعیین نشده'}\n"
          f"💰 خزانه کشور: {n['treasury']:,}\n\nپادشاه رأس قدرت است و می‌تواند انتصاب‌ها و سیاست‌های کلان را کنترل کند.")
    kb=[[v4_btn("🏛 تعیین رئیس‌جمهور","king_set|president|"+sid),v4_btn("👑 تعیین پادشاه","king_set|king|"+sid)],
        [v4_btn("🏙 تعیین شهردار","king_set|mayor|"+sid),v4_btn("🏢 وزرا","ministries")],
        [v4_btn("💰 بودجه کشور","king_budget|"+sid),v4_btn("📜 قوانین","laws")],
        [v4_btn("🗳 انتخابات","election_national"),v4_btn("📰 اخبار","news")],
        [v4_btn("📊 گزارش کامل","world_report")],[v4_btn("↩️ کشور","nation")]]
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb))

async def v4_owner_panel(q,uid):
    if not v4_admin(uid):return await q.answer("دسترسی فقط برای مالک/ادمین.",show_alert=True)
    text=("🛠 <b>پنل مالک بازی</b>\n━━━━━━━━━━━━\n"
          "مدیریت مستقیم جهان، کاربران، نقش‌ها، اخبار، اقتصاد و پشتیبانی.\n")
    with v4_db() as c:
        users=c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        tickets=c.execute("SELECT COUNT(*) n FROM v4_tickets WHERE status='open'").fetchone()["n"]
        apps=c.execute("SELECT COUNT(*) n FROM v4_hires WHERE status='pending'").fetchone()["n"]
    text+=f"\n👥 کاربران: {users}\n🎫 تیکت باز: {tickets}\n📋 درخواست استخدام: {apps}"
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup([
      [v4_btn("👑 پادشاه","king"),v4_btn("🏛 رئیس‌جمهور","president")],
      [v4_btn("🏙 شهردار","owner_mayor"),v4_btn("🏢 وزارتخانه‌ها","ministries")],
      [v4_btn("📰 ارسال خبر","owner_news"),v4_btn("💰 اقتصاد","owner_economy")],
      [v4_btn("🎫 پشتیبانی","ticket_admin"),v4_btn("📋 استخدام‌ها","hire_admin")],
      [v4_btn("🌍 گزارش جهان","world_report")],[v4_btn("↩️ منوی اصلی","home")]]))

async def v4_president(q,uid):
    with v4_db() as c:n=c.execute("SELECT * FROM v3_country WHERE id=1").fetchone()
    if not (n["president_id"]==uid or v4_owner(uid) or v4_admin(uid)):return await q.answer("فقط رئیس‌جمهور یا پادشاه.",show_alert=True)
    sid=v4_session(uid,q.message.chat_id,"president","1")
    text=(f"🏛 <b>دفتر رئیس‌جمهور</b>\n━━━━━━━━━━━━\nخزانه: {n['treasury']:,}\n"
          f"تورم: {n['inflation']:.1f}% | رضایت: {n['approval']}%\n"
          f"اقتصاد: {n['gdp']:,}\n\nوظیفه: مدیریت بودجه، کابینه، اقتصاد و عملکرد وزارتخانه‌ها.")
    kb=[[v4_btn("💰 اقتصاد","pres_action|economy|"+sid),v4_btn("💸 مالیات","pres_action|tax|"+sid)],
        [v4_btn("🏥 سلامت","pres_action|health|"+sid),v4_btn("🎓 آموزش","pres_action|education|"+sid)],
        [v4_btn("🛡 امنیت","pres_action|security|"+sid),v4_btn("🛣 زیرساخت","pres_action|infra|"+sid)],
        [v4_btn("🏢 وزارتخانه‌ها","ministries"),v4_btn("📋 وظایف","gov_tasks")],
        [v4_btn("📰 گزارش دولت","news")],[v4_btn("↩️ کشور","nation")]]
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb))

async def v4_mayor(q,uid):
    chat=q.message.chat_id
    city=v3_ensure_city(chat)
    if city["mayor_id"]!=uid and not v4_owner(uid) and not v4_admin(uid):return await q.answer("فقط شهردار این شهر.",show_alert=True)
    sid=v4_session(uid,chat,"mayor",chat)
    text=(f"🏛 <b>دفتر شهردار</b>\n━━━━━━━━━━━━\n🏙 {city['name']}\n"
          f"💰 خزانه {city['treasury']:,}\n👥 {city['population']}\n⭐ رضایت {city['approval']}%\n"
          f"💸 مالیات {city['tax']}%\n🏗 توسعه {city['development']}\n\n"
          "وظایف: بودجه، خدمات، پلیس، پروژه، اشتغال و رضایت شهروندان.")
    kb=[[v4_btn("💰 بودجه","may_action|budget|"+sid),v4_btn("💸 مالیات","may_action|tax|"+sid)],
        [v4_btn("🏗 پروژه","may_action|project|"+sid),v4_btn("👮 پلیس","org_city|police")],
        [v4_btn("🏥 درمان","org_city|hospital"),v4_btn("🚇 حمل‌ونقل","may_action|transport|"+sid)],
        [v4_btn("💼 استخدام","hire_city|"+sid),v4_btn("🗳 انتخابات","election_city")],
        [v4_btn("📋 وظایف امروز","may_tasks"),v4_btn("📊 گزارش","may_report")],
        [v4_btn("↩️ شهر","city")]]
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb))

async def v4_ministries(q,uid):
    with v4_db() as c: rows=c.execute("SELECT * FROM v4_departments WHERE scope='national' ORDER BY id").fetchall()
    text="🏢 <b>وزارتخانه‌ها</b>\n━━━━━━━━━━━━\n"
    for r in rows:
        chief=r["chief_id"] or "تعیین نشده"
        text+=f"• <b>{r['name']}</b>\nبودجه: {r['budget']:,} | رئیس: {chief}\nوظیفه: {r['mission']}\n\n"
    kb=[[v4_btn("👥 رؤسا/انتصابات","ministry_manage")] ,[v4_btn("📢 آگهی استخدام","hire_national")],
        [v4_btn("↩️ کشور","nation")]]
    await q.edit_message_text(text[:4000],parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb))

async def v4_ticket(q,uid):
    await q.edit_message_text("🎫 <b>پشتیبانی</b>\nموضوع درخواستت را انتخاب کن:",
      parse_mode="HTML",reply_markup=InlineKeyboardMarkup([
        [v4_btn("🐞 باگ","ticket_cat|bug"),v4_btn("💳 مالی","ticket_cat|finance")],
        [v4_btn("⚖️ شکایت","ticket_cat|complaint"),v4_btn("🚨 گزارش تخلف","ticket_cat|report")],
        [v4_btn("❓ سؤال","ticket_cat|question"),v4_btn("📌 سایر","ticket_cat|other")],
        [v4_btn("📂 تیکت‌های من","my_tickets")],[v4_btn("↩️ منوی اصلی","home")]]))

async def v4_ticket_cat(q,uid,cat):
    context_pending[q.message.chat_id]={"v4":"ticket","uid":uid,"cat":cat}
    await q.edit_message_text(f"🎫 موضوع: {cat}\n\nحالا متن درخواست را در پیام بعدی بفرست. عکس/فایل هم قابل ثبت است.")

async def v4_news(q,uid):
    with v4_db() as c: rows=c.execute("SELECT * FROM v4_news ORDER BY id DESC LIMIT 15").fetchall()
    text="📰 <b>اخبار Life RP</b>\n━━━━━━━━━━━━\n"+("".join(f"• <b>{r['title']}</b>\n{r['body']}\n\n" for r in rows) or "هنوز خبری منتشر نشده.")
    await q.edit_message_text(text[:4000],parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[v4_btn("↩️ منوی اصلی","home")]]))

async def v4_election(q,uid,scope):
    sid="1" if scope=="national" else str(q.message.chat_id)
    office="ریاست‌جمهوری" if scope=="national" else "شهرداری"
    with v4_db() as c:
        e=c.execute("SELECT * FROM v4_elections WHERE scope=? AND scope_id=? AND status='open' ORDER BY id DESC LIMIT 1",(scope,sid)).fetchone()
        if not e:
            if not (v4_owner(uid) or v4_admin(uid)): return await q.answer("انتخاباتی در حال برگزاری نیست.",show_alert=True)
            now=time.time(); ends=now+86400
            c.execute("INSERT INTO v4_elections(scope,scope_id,office,started,ends) VALUES(?,?,?,?,?)",(scope,sid,office,now,ends))
            e=c.execute("SELECT * FROM v4_elections WHERE id=last_insert_rowid()").fetchone()
        cands=c.execute("SELECT * FROM v4_candidates WHERE election_id=?",(e["id"],)).fetchall()
        counts={r["candidate"]:r["n"] for r in c.execute("SELECT candidate,COUNT(*) n FROM v4_votes WHERE election_id=? GROUP BY candidate",(e["id"],)).fetchall()}
    text=f"🗳 <b>انتخابات {office}</b>\n━━━━━━━━━━━━\n⏳ پایان: {datetime.fromtimestamp(e['ends']).strftime('%Y-%m-%d %H:%M')}\n\n"
    text+="".join(f"• {r['user_id']} — {counts.get(r['user_id'],0)} رأی\n" for r in cands) or "نامزدی ثبت نشده."
    kb=[[v4_btn("✍️ ثبت نامزدی","cand|"+str(e["id"])),v4_btn("🗳 رأی‌دادن","vote_menu|"+str(e["id"]))],
        [v4_btn("📢 خبر انتخابات","election_news|"+str(e["id"]))]]
    if v4_admin(uid):kb.append([v4_btn("🏁 پایان انتخابات","finish_election|"+str(e["id"]) )])
    kb.append([v4_btn("↩️ بازگشت","nation" if scope=="national" else "city")])
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb))

async def v4_vote_menu(q,uid,eid):
    with v4_db() as c: cands=c.execute("SELECT * FROM v4_candidates WHERE election_id=?",(eid,)).fetchall()
    kb=[[v4_btn(f"🗳 رأی به {r['user_id']}","vote|%s|%s"%(eid,r["user_id"]))] for r in cands if r["user_id"]!=uid]
    kb.append([v4_btn("↩️ انتخابات","election_back|"+str(eid))])
    await q.edit_message_text("نامزد موردنظر را انتخاب کن:",reply_markup=InlineKeyboardMarkup(kb))

async def v4_vote(q,uid,eid,candidate):
    with v4_db() as c:
        e=c.execute("SELECT * FROM v4_elections WHERE id=? AND status='open'",(eid,)).fetchone()
        if not e:return await q.answer("انتخابات بسته است.",show_alert=True)
        try:c.execute("INSERT INTO v4_votes VALUES(?,?,?,?)",(eid,uid,candidate,time.time()))
        except sqlite3.IntegrityError:return await q.answer("قبلاً رأی داده‌ای.",show_alert=True)
    v4_add_xp(uid,5,"political"); await q.answer("رأی ثبت شد.")
    await v4_vote_menu(q,uid,eid)

async def v4_candidate(q,uid,eid):
    context_pending[q.message.chat_id]={"v4":"candidate","uid":uid,"eid":eid}
    await q.edit_message_text("فرم نامزدی را بفرست:\nنام/شناسه اختیاری | برنامه و وعده‌های انتخاباتی")

async def v4_finish_election(q,uid,eid,bot):
    if not v4_admin(uid):return await q.answer("فقط مالک/ادمین.",show_alert=True)
    with v4_db() as c:
        e=c.execute("SELECT * FROM v4_elections WHERE id=? AND status='open'",(eid,)).fetchone()
        if not e:return await q.answer("انتخابات بسته است.",show_alert=True)
        w=c.execute("SELECT candidate,COUNT(*) n FROM v4_votes WHERE election_id=? GROUP BY candidate ORDER BY n DESC,candidate",(eid,)).fetchone()
        if not w:return await q.answer("رأیی ثبت نشده.",show_alert=True)
        c.execute("UPDATE v4_elections SET status='closed',winner=? WHERE id=?",(w["candidate"],eid))
        if e["scope"]=="national": c.execute("UPDATE v3_country SET president_id=? WHERE id=1",(w["candidate"],))
        else:c.execute("UPDATE v3_cities SET mayor_id=? WHERE chat_id=?",(w["candidate"],int(e["scope_id"])))
    await v4_send_news(bot,"نتیجه انتخابات",f"برنده انتخابات {e['office']}: {w['candidate']}","election")
    await q.edit_message_text(f"🏁 انتخابات پایان یافت.\nبرنده: {w['candidate']}",reply_markup=InlineKeyboardMarkup([[v4_btn("↩️ منوی اصلی","home")]]))

async def v4_send_news(bot,title,body,kind="system"):
    with v4_db() as c:
        c.execute("INSERT INTO v4_news(title,body,kind,created) VALUES(?,?,?,?)",(title,body,kind,time.time()))
    try:
        await bot.send_message(V4_NEWS_CHANNEL_ID,f"📰 <b>{title}</b>\n\n{body}",parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎮 ورود به بازی",callback_data="life4|home")]]))
    except Exception as e: logger.warning("news: %s",e)

async def v4_hiring(q,uid,scope,sid=None):
    if scope=="city":
        chat=q.message.chat_id
        with v4_db() as c: city=v3_ensure_city(chat)
        allowed=city["mayor_id"]==uid or v4_owner(uid) or v4_admin(uid)
        orgscope="city"
        scopeid=str(chat)
    else:
        with v4_db() as c:n=c.execute("SELECT * FROM v3_country WHERE id=1").fetchone()
        allowed=n["president_id"]==uid or v4_owner(uid) or v4_admin(uid)
        orgscope="national";scopeid="1"
    if not allowed:return await q.answer("مجوز انتشار آگهی استخدام را نداری.",show_alert=True)
    context_pending[q.message.chat_id]={"v4":"hiring","uid":uid,"scope":orgscope,"scope_id":scopeid}
    await q.edit_message_text("فرم آگهی:\nعنوان | مهارت | حداقل سطح | حقوق | توضیح")

async def v4_jobs_ads(q,uid,scope):
    sid=str(q.message.chat_id) if scope=="city" else "1"
    with v4_db() as c:
        rows=c.execute("SELECT * FROM v4_orgs WHERE scope=? AND scope_id=?",(scope,sid)).fetchall()
    text="📢 <b>استخدام‌ها</b>\n━━━━━━━━━━━━\n"
    kb=[]
    for o in rows:
        ads=c.execute("SELECT * FROM v4_hires WHERE org_id=? AND status='ad'",(o["id"],)).fetchall()
        for a in ads:
            text+=f"#{a['id']} {o['name']} — {a['job']} — {a['salary']:,}\n"
            kb.append([v4_btn(f"📝 درخواست #{a['id']}","apply|"+str(a["id"]))])
    await q.edit_message_text(text or "آگهی فعالی نیست.",parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb+[[v4_btn("↩️ شغل‌ها","jobs")]]))

async def v4_apply(q,uid,adid):
    with v4_db() as c:r=c.execute("SELECT * FROM v4_hires WHERE id=? AND status='ad'",(adid,)).fetchone()
    if not r:return await q.answer("آگهی دیگر فعال نیست.",show_alert=True)
    context_pending[q.message.chat_id]={"v4":"apply","uid":uid,"adid":adid}
    await q.edit_message_text("📝 فرم درخواست استخدام را بفرست:\nمتن معرفی، تجربه و دلیل درخواست")

async def v4_org(q,uid,orgtype):
    chat=q.message.chat_id
    names={"police":"👮 پلیس","court":"⚖️ دادگستری","hospital":"🏥 بیمارستان","army":"🪖 ارتش"}
    name=names.get(orgtype,orgtype)
    with v4_db() as c:
        r=c.execute("SELECT * FROM v4_orgs WHERE scope='city' AND scope_id=? AND type=?",(str(chat),orgtype)).fetchone()
        if not r:
            c.execute("INSERT INTO v4_orgs(scope,scope_id,name,type,budget,treasury,salary) VALUES('city',?,?,?,?,?,?)",
                      (str(chat),name,orgtype,1000000,500000,50000))
            r=c.execute("SELECT * FROM v4_orgs WHERE id=last_insert_rowid()").fetchone()
    text=f"{name}\n━━━━━━━━━━━━\n💰 بودجه: {r['budget']:,}\n💵 خزانه: {r['treasury']:,}\n👑 رئیس: {r['chief_id'] or 'تعیین نشده'}\n\nاین سازمان مأموریت و استخدام واقعی دارد."
    kb=[[v4_btn("📢 آگهی استخدام","org_hire|"+str(r["id"])),v4_btn("📋 مأموریت‌ها","org_tasks|"+str(r["id"]))]]
    if r["chief_id"]==uid or v4_owner(uid) or v4_admin(uid):kb.append([v4_btn("👑 مدیریت سازمان","org_manage|"+str(r["id"]))])
    kb.append([v4_btn("↩️ شهر","city")])
    await q.edit_message_text(text,reply_markup=InlineKeyboardMarkup(kb))

async def v4_missions(q,uid):
    with v4_db() as c:
        tasks=c.execute("SELECT * FROM v4_tasks WHERE user_id=? AND status='assigned' ORDER BY id DESC",(uid,)).fetchall()
    text="🎯 <b>ماموریت‌های من</b>\n━━━━━━━━━━━━\n"
    text+="".join(f"#{r['id']} {r['title']} — پاداش {r['reward']:,}\n" for r in tasks) or "ماموریت سازمانی فعالی نداری."
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[v4_btn("💼 کار","jobs")],[v4_btn("↩️ منوی اصلی","home")]]))

async def v4_social(q,uid):
    u=v4_user(uid)
    with v4_db() as c:
        fr=c.execute("SELECT COUNT(*) n FROM friendships WHERE user_id=?",(uid,)).fetchone()["n"]
    await q.edit_message_text(f"👨‍👩‍👧 <b>روابط و زندگی اجتماعی</b>\n━━━━━━━━━━━━\n👥 دوستان: {fr}\n💍 وضعیت ازدواج: {'متأهل' if u.get('married_to') else 'مجرد'}\n⭐ اعتبار اجتماعی از تعاملات و عملکردت تغییر می‌کند.",
        parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[v4_btn("👥 دوستان","friends")],[v4_btn("💍 ازدواج/روابط","relationship")],[v4_btn("↩️ منوی اصلی","home")]]))

async def v4_events(q,uid):
    await q.edit_message_text("🌍 <b>جهان زنده</b>\n━━━━━━━━━━━━\nاقتصاد، تورم، بازار، شهرها و نیازهای شهروندان در چرخه‌های زمانی تغییر می‌کنند.\n\nرویدادهای آینده در همین بخش منتشر می‌شوند.",
        parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[v4_btn("📰 اخبار","news")],[v4_btn("↩️ منوی اصلی","home")]]))

async def v4_world_report(q,uid):
    if not v4_admin(uid) and not v4_owner(uid):return await q.answer("دسترسی مالک/ادمین.",show_alert=True)
    with v4_db() as c:
        users=c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        orgs=c.execute("SELECT COUNT(*) n FROM v4_orgs").fetchone()["n"]
        comps=c.execute("SELECT COUNT(*) n FROM v4_companies WHERE active=1").fetchone()["n"]
        open_e=c.execute("SELECT COUNT(*) n FROM v4_elections WHERE status='open'").fetchone()["n"]
    with v4_db() as c:n=c.execute("SELECT * FROM v3_country WHERE id=1").fetchone()
    await q.edit_message_text(
      f"📊 <b>گزارش جهان</b>\n━━━━━━━━━━━━\n👥 کاربران {users}\n🏢 سازمان‌ها {orgs}\n🏭 شرکت‌ها {comps}\n🗳 انتخابات فعال {open_e}\n"
      f"💰 خزانه کشور {n['treasury']:,}\n📈 GDP {n['gdp']:,}\n💸 تورم {n['inflation']:.1f}%\n⭐ رضایت {n['approval']}%",
      parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[v4_btn("↩️ مالک","owner")]]))

async def v4_callback(update,context):
    q=update.callback_query
    if not q:return False
    data=q.data or ""
    if not data.startswith("life4|"):return False
    uid=q.from_user.id
    try:
        p=data.split("|"); a=p[1]
        if a=="home":await v4_menu(q,uid)
        elif a=="profile":await v4_profile(q,uid)
        elif a=="skills":await v4_skills(q,uid)
        elif a=="jobs":await v4_jobs(q,uid)
        elif a=="work":await v4_work(q,uid)
        elif a=="train":await v4_train(q,uid)
        elif a=="train_do":await v4_train_do(q,uid,p[2])
        elif a=="money":await v4_money(q,uid)
        elif a=="bank":await v4_bank(q,uid)
        elif a=="assets":await v4_assets(q,uid)
        elif a=="shop":await v4_shop(q,uid)
        elif a=="buyprop":await v4_buyprop(q,uid,p[2])
        elif a=="buyveh":await v4_buyveh(q,uid,p[2])
        elif a=="market":await v4_market(q,uid)
        elif a=="stocks":await v4_stocks(q,uid)
        elif a=="city":await v4_city(q,uid)
        elif a=="nation":await v4_nation(q,uid)
        elif a=="king":await v4_king(q,uid)
        elif a=="owner":await v4_owner_panel(q,uid)
        elif a=="president":await v4_president(q,uid)
        elif a=="mayor":await v4_mayor(q,uid)
        elif a=="ministries":await v4_ministries(q,uid)
        elif a=="news":await v4_news(q,uid)
        elif a=="ticket":await v4_ticket(q,uid)
        elif a=="ticket_cat":await v4_ticket_cat(q,uid,p[2])
        elif a=="election_city":await v4_election(q,uid,"city")
        elif a=="election_national":await v4_election(q,uid,"national")
        elif a=="vote_menu":await v4_vote_menu(q,uid,int(p[2]))
        elif a=="vote":await v4_vote(q,uid,int(p[2]),int(p[3]))
        elif a=="cand":await v4_candidate(q,uid,int(p[2]))
        elif a=="finish_election":await v4_finish_election(q,uid,int(p[2]),context.bot)
        elif a=="election_back":
            with v4_db() as c:e=c.execute("SELECT scope FROM v4_elections WHERE id=?",(int(p[2]),)).fetchone()
            await v4_election(q,uid,e["scope"] if e else "national")
        elif a=="election_news":
            await v4_send_news(context.bot,"🗳 انتخابات Life RP","رأی‌گیری فعال است. برای رأی دادن وارد بازی شوید.","election")
            await q.answer("خبر ارسال شد.")
        elif a=="jobs_ads":await v4_jobs_ads(q,uid,"national")
        elif a=="jobs_ads_city":await v4_jobs_ads(q,uid,"city")
        elif a=="hire_national":await v4_hiring(q,uid,"national")
        elif a=="hire_city":await v4_hiring(q,uid,"city",p[2])
        elif a=="apply":await v4_apply(q,uid,int(p[2]))
        elif a=="org_city":await v4_org(q,uid,p[2])
        elif a=="missions":await v4_missions(q,uid)
        elif a=="events":await v4_events(q,uid)
        elif a=="social":await v4_social(q,uid)
        elif a=="world_report":await v4_world_report(q,uid)
        elif a=="owner_news":
            if not v4_admin(uid):return await q.answer("فقط مالک/ادمین.",show_alert=True)
            context_pending[q.message.chat_id]={"v4":"news","uid":uid}; await q.edit_message_text("خبر را بفرست:\nعنوان | متن")
        elif a=="owner_economy":
            if not v4_admin(uid):return await q.answer("فقط مالک/ادمین.",show_alert=True)
            await q.edit_message_text("📊 اقتصاد مرکزی آماده است.\nچرخه اقتصادی، درآمد شهرها و خزانه کشور در Tickهای بازی به‌روزرسانی می‌شود.",
                reply_markup=InlineKeyboardMarkup([[v4_btn("↩️ مالک","owner")]]))
        elif a=="ticket_admin":
            if not v4_admin(uid):return await q.answer("فقط مالک/ادمین.",show_alert=True)
            with v4_db() as c:rows=c.execute("SELECT * FROM v4_tickets WHERE status='open' ORDER BY id DESC LIMIT 20").fetchall()
            kb=[[v4_btn(f"🎫 #{r['id']} {r['category']}","ticket_view|"+str(r["id"]))] for r in rows]
            kb.append([v4_btn("↩️ مالک","owner")])
            await q.edit_message_text("🎫 تیکت‌های باز:",reply_markup=InlineKeyboardMarkup(kb))
        elif a=="ticket_view":
            if not v4_admin(uid):return await q.answer("فقط ادمین.",show_alert=True)
            with v4_db() as c:
                t=c.execute("SELECT * FROM v4_tickets WHERE id=?",(int(p[2]),)).fetchone()
                ms=c.execute("SELECT * FROM v4_ticket_messages WHERE ticket_id=? ORDER BY id",(int(p[2]),)).fetchall()
            if not t:return await q.answer("تیکت نیست.",show_alert=True)
            text=f"🎫 #{t['id']}\n👤 کاربر: {t['user_id']}\nموضوع: {t['category']}\n\n{t['text']}\n\n"+''.join(f"{m['sender']}: {m['text']}\n" for m in ms)
            await q.edit_message_text(text[:4000],reply_markup=InlineKeyboardMarkup([[v4_btn("✉️ پاسخ","ticket_reply|"+str(t["id"])),v4_btn("✅ بستن","ticket_close|"+str(t["id"]))],[v4_btn("↩️ تیکت‌ها","ticket_admin")]]))
        elif a=="ticket_reply":
            context_pending[q.message.chat_id]={"v4":"ticket_reply","uid":uid,"tid":int(p[2])};await q.edit_message_text("پاسخ را بفرست:")
        elif a=="ticket_close":
            if not v4_admin(uid):return await q.answer("فقط ادمین.",show_alert=True)
            with v4_db() as c:c.execute("UPDATE v4_tickets SET status='closed' WHERE id=?",(int(p[2]),))
            await q.answer("تیکت بسته شد.")
        elif a=="my_tickets":
            with v4_db() as c:rows=c.execute("SELECT * FROM v4_tickets WHERE user_id=? ORDER BY id DESC LIMIT 10",(uid,)).fetchall()
            await q.edit_message_text("🎫 تیکت‌های من\n\n"+''.join(f"#{r['id']} {r['category']} — {r['status']}\n" for r in rows),
                                      reply_markup=InlineKeyboardMarkup([[v4_btn("↩️ پشتیبانی","ticket")]]))
        elif a=="king_set":
            sid=p[3]
            if not v4_owner(uid) or not v4_auth(sid,uid,q.message.chat_id,"king","1"):return await q.answer("Session نامعتبر.",show_alert=True)
            context_pending[q.message.chat_id]={"v4":"setrole","uid":uid,"role":p[2]};await q.edit_message_text("شناسه کاربر را بفرست:")
        elif a=="pres_action":
            sid=p[3]
            with v4_db() as c:n=c.execute("SELECT president_id FROM v3_country WHERE id=1").fetchone()
            if not v4_auth(sid,uid,q.message.chat_id,"president","1") or (n["president_id"]!=uid and not v4_owner(uid)):return await q.answer("دسترسی رد شد.",show_alert=True)
            action=p[2]
            cost={"health":1500000,"education":1500000,"security":1800000,"infra":2000000}.get(action,0)
            col={"health":"health","education":"education","security":"security","infra":"infrastructure"}.get(action)
            with v4_db() as c:
                n=c.execute("SELECT * FROM v3_country WHERE id=1").fetchone()
                if cost and n["treasury"]<cost:return await q.answer("خزانه کافی نیست.",show_alert=True)
                if col:c.execute(f"UPDATE v3_country SET treasury=treasury-?,{col}=MIN(100,{col}+5),approval=MIN(100,approval+1) WHERE id=1",(cost,))
                elif action=="tax":c.execute("UPDATE v3_country SET inflation=MAX(0.1,inflation-0.2) WHERE id=1")
                c.execute("INSERT INTO v4_government_logs(actor,action,amount,entity,created) VALUES(?,?,?,?,?)",(uid,action,cost,"country",time.time()))
            await q.answer("تصمیم دولتی اجرا شد.");await v4_president(q,uid)
        elif a=="may_action":
            sid=p[3];chat=q.message.chat_id
            with v4_db() as c:city=c.execute("SELECT * FROM v3_cities WHERE chat_id=?",(chat,)).fetchone()
            if not city or not v4_auth(sid,uid,chat,"mayor",chat) or (city["mayor_id"]!=uid and not v4_owner(uid)):return await q.answer("دسترسی رد شد.",show_alert=True)
            action=p[2]
            if action=="budget":
                await q.answer("بودجه شهر با پروژه‌ها و سازمان‌ها مصرف می‌شود.")
            elif action=="tax":
                new=min(40,city["tax"]+1)
                with v4_db() as c:c.execute("UPDATE v3_cities SET tax=? WHERE chat_id=?",(new,chat))
                await q.answer(f"مالیات شهر {new}% شد.")
            elif action=="project":
                cost=500000
                with v4_db() as c:
                    if city["treasury"]<cost:return await q.answer("خزانه کافی نیست.",show_alert=True)
                    c.execute("UPDATE v3_cities SET treasury=treasury-?,development=development+2,approval=MAX(0,approval-1) WHERE chat_id=?",(cost,chat))
                await q.answer("پروژه شهری آغاز شد.")
            elif action=="transport":
                with v4_db() as c:c.execute("UPDATE v3_cities SET treasury=MAX(0,treasury-300000),development=development+1 WHERE chat_id=?",(chat,))
                await q.answer("حمل‌ونقل توسعه یافت.")
            await v4_mayor(q,uid)
        elif a=="king_budget":
            sid=p[2]
            if not v4_owner(uid) or not v4_auth(sid,uid,q.message.chat_id,"king","1"):return await q.answer("دسترسی رد شد.",show_alert=True)
            await q.answer("بودجه کشور از خزانه و مالیات مدیریت می‌شود.")
        else:
            await q.answer("این بخش در حال توسعه است.",show_alert=True)
        await q.answer()
    except Exception as e:
        logger.exception("life4 callback: %s",e)
        try: await q.answer("⚠️ عملیات ناموفق بود.",show_alert=True)
        except: pass
    return True

async def v4_text_router(update,context):
    if not update.message:return False
    pend=context_pending.get(update.effective_chat.id)
    if not pend or pend.get("v4") is None:return False
    uid=update.effective_user.id
    if pend.get("uid")!=uid:return False
    text=update.message.text or update.message.caption or ""
    kind=pend["v4"]
    try:
        if kind=="ticket":
            with v4_db() as c:
                cur=c.execute("INSERT INTO v4_tickets(user_id,category,text,created) VALUES(?,?,?,?)",(uid,pend["cat"],text[:3500],time.time()))
                tid=cur.lastrowid
            context_pending.pop(update.effective_chat.id,None)
            await update.message.reply_text(f"🎫 تیکت #{tid} ثبت شد. پشتیبانی بررسی می‌کند.")
            return True
        if kind=="ticket_reply":
            tid=pend["tid"]
            with v4_db() as c:c.execute("INSERT INTO v4_ticket_messages(ticket_id,sender,text,created) VALUES(?,?,?,?)",(tid,uid,text,time.time()))
            context_pending.pop(update.effective_chat.id,None);await update.message.reply_text("پاسخ ثبت شد.");return True
        if kind=="news":
            if not v4_admin(uid):return True
            title,body=text.split("|",1);context_pending.pop(update.effective_chat.id,None)
            await v4_send_news(context.bot,title,body,"admin");await update.message.reply_text("📰 خبر ارسال شد.");return True
        if kind=="candidate":
            manifesto=text.split("|",1)[-1]
            with v4_db() as c:
                c.execute("INSERT OR REPLACE INTO v4_candidates(election_id,user_id,manifesto) VALUES(?,?,?)",(pend["eid"],uid,manifesto))
            context_pending.pop(update.effective_chat.id,None);await update.message.reply_text("✍️ نامزدی ثبت شد.");return True
        if kind=="setrole":
            target=int(text.strip());role=pend["role"]
            with v4_db() as c:
                if role=="president":c.execute("UPDATE v3_country SET president_id=? WHERE id=1",(target,))
                elif role=="king":c.execute("UPDATE v3_country SET king_id=? WHERE id=1",(target,))
                elif role=="mayor":
                    try: chat_id,target_user=map(int,text.replace(" ","").split("|"))
                    except: await update.message.reply_text("برای شهردار: chat_id|user_id");return True
                    c.execute("UPDATE v3_cities SET mayor_id=? WHERE chat_id=?",(target_user,chat_id))
            context_pending.pop(update.effective_chat.id,None);await update.message.reply_text("👑 انتصاب انجام شد.");return True
        if kind=="hiring":
            title,skill,mins,salary,desc=[x.strip() for x in text.split("|",4)]
            mins=int(mins);salary=int(salary)
            with v4_db() as c:
                o=c.execute("SELECT * FROM v4_orgs WHERE scope=? AND scope_id=? LIMIT 1",(pend["scope"],pend["scope_id"])).fetchone()
                if not o:
                    c.execute("INSERT INTO v4_orgs(scope,scope_id,name,type,treasury,budget) VALUES(?,?,?,?,?,?)",
                              (pend["scope"],pend["scope_id"],"سازمان دولتی","government",1000000,2000000))
                    o=c.execute("SELECT * FROM v4_orgs WHERE id=last_insert_rowid()").fetchone()
                c.execute("INSERT INTO v4_hires(org_id,user_id,job,salary,skill,status,created) VALUES(?,?,?,?,?,?,?)",
                          (o["id"],0,title,salary,skill,"ad",time.time()))
            context_pending.pop(update.effective_chat.id,None);await update.message.reply_text("📢 آگهی استخدام منتشر شد.");return True
        if kind=="apply":
            adid=pend["adid"]
            with v4_db() as c:
                r=c.execute("SELECT * FROM v4_hires WHERE id=? AND status='ad'",(adid,)).fetchone()
                if not r:await update.message.reply_text("آگهی بسته شده.");return True
                c.execute("UPDATE v4_hires SET user_id=?,status='pending' WHERE id=?",(uid,adid))
            context_pending.pop(update.effective_chat.id,None);await update.message.reply_text("📨 درخواست استخدام ثبت شد.");return True
    except Exception as e:
        logger.exception("life4 text: %s",e);await update.message.reply_text("فرمت یا عملیات نامعتبر بود.")
        return True
    return False

async def v4_engine_tick(context):
    try:
        with v4_db() as c:
            # Personal needs
            c.execute("UPDATE users SET hunger=MIN(100,hunger+3),sleep=MAX(0,sleep-2),energy=MAX(0,energy-1),stress=MIN(100,stress+1)")
            # Property income
            for r in c.execute("SELECT user_id,prop_key FROM user_properties").fetchall():
                inc=int(PROPERTIES.get(r["prop_key"],{}).get("income",0))
                if inc:
                    c.execute("UPDATE users SET bank=bank+? WHERE user_id=?",(inc,r["user_id"]))
                    c.execute("INSERT INTO transactions(user_id,kind,amount,note) VALUES(?,?,?,?)",(r["user_id"],"property_income",inc,r["prop_key"]))
            # City tax and national share
            for city in c.execute("SELECT * FROM v3_cities").fetchall():
                income=max(0,int(city["population"]*city["tax"]/100*1500*max(.5,city["industry"]/50)))
                c.execute("UPDATE v3_cities SET treasury=treasury+?,last_income=? WHERE chat_id=?",(income,time.time(),city["chat_id"]))
                c.execute("UPDATE v3_country SET treasury=treasury+? WHERE id=1",(int(income*.15),))
            # Company revenue
            for co in c.execute("SELECT * FROM v4_companies WHERE active=1").fetchall():
                rev=max(0,int(5000*co["level"]*(1+co["employees"]*.03)))
                c.execute("UPDATE v4_companies SET revenue=revenue+? WHERE id=?",(rev,co["id"]))
                c.execute("UPDATE users SET bank=bank+? WHERE user_id=?",(max(0,rev//10),co["owner"]))
            # Macro economy
            c.execute("UPDATE v3_country SET inflation=MAX(0.1,MIN(50,inflation+((RANDOM()%21)-10)/100.0)),gdp=MAX(1000000,CAST(gdp*(1+((RANDOM()%21)-10)/10000.0) AS INTEGER)) WHERE id=1")
            c.execute("UPDATE v3_stocks SET price=MAX(100,CAST(price*(1+((RANDOM()%101)-50)/10000.0) AS INTEGER))")
    except Exception as e:logger.warning("v4 tick: %s",e)

async def v4_salary_tick(context):
    try:
        with v4_db() as c:
            for r in c.execute("SELECT * FROM v4_hires WHERE status='active' AND user_id>0").fetchall():
                c.execute("UPDATE users SET bank=bank+? WHERE user_id=?",(r["salary"],r["user_id"]))
                c.execute("INSERT INTO transactions(user_id,kind,amount,note) VALUES(?,?,?,?)",(r["user_id"],"org_salary",r["salary"],r["job"]))
            n=c.execute("SELECT * FROM v3_country WHERE id=1").fetchone()
            salaries=[("king_id",600000,"پادشاه"),("president_id",220000,"رئیس‌جمهور")]
            for col,sal,label in salaries:
                if n[col]:
                    c.execute("UPDATE users SET bank=bank+? WHERE user_id=?",(sal,n[col]))
                    c.execute("INSERT INTO transactions(user_id,kind,amount,note) VALUES(?,?,?,?)",(n[col],"official_salary",sal,label))
            for city in c.execute("SELECT mayor_id FROM v3_cities WHERE mayor_id IS NOT NULL").fetchall():
                c.execute("UPDATE users SET bank=bank+? WHERE user_id=?",(100000,city["mayor_id"]))
                c.execute("INSERT INTO transactions(user_id,kind,amount,note) VALUES(?,?,?,?)",(city["mayor_id"],"mayor_salary",100000,"شهردار"))
            for d in c.execute("SELECT chief_id,salary FROM v4_departments WHERE chief_id IS NOT NULL").fetchall():
                c.execute("UPDATE users SET bank=bank+? WHERE user_id=?",(d["salary"],d["chief_id"]))
    except Exception as e:logger.warning("v4 salary: %s",e)

async def v4_command(update,context):
    u=v4_user(update.effective_user.id)
    # private/group-safe: panel always belongs to Telegram user who clicked.
    await update.message.reply_text("🌍 <b>Life RP</b>\nاز منوی زیر وارد زندگی مجازی خودت شو.",
                                    parse_mode="HTML",reply_markup=v4_main_menu(update.effective_user.id,update.effective_chat.type=="private"))

def register_v4(app):
    v4_init_db()
    app.add_handler(CallbackQueryHandler(v4_callback,pattern=r"^life4\|"),group=-30)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND,v4_text_router),group=-30)
    app.add_handler(CommandHandler(["life4","life"],v4_command),group=-20)

async def v4_daily_cleanup(context):
    try:
        with v4_db() as c:
            c.execute("DELETE FROM v4_sessions WHERE expires<?",(time.time(),))
            # Complete expired elections automatically.
            rows=c.execute("SELECT id FROM v4_elections WHERE status='open' AND ends<=?",(time.time(),)).fetchall()
        for r in rows:
            # Use a synthetic callback impossible; finalize in DB directly.
            with v4_db() as c:
                e=c.execute("SELECT * FROM v4_elections WHERE id=?",(r["id"],)).fetchone()
                w=c.execute("SELECT candidate,COUNT(*) n FROM v4_votes WHERE election_id=? GROUP BY candidate ORDER BY n DESC,candidate",(r["id"],)).fetchone()
                if w:
                    c.execute("UPDATE v4_elections SET status='closed',winner=? WHERE id=?",(w["candidate"],r["id"]))
                    if e["scope"]=="national":c.execute("UPDATE v3_country SET president_id=? WHERE id=1",(w["candidate"],))
                    elif e["scope"]=="city":c.execute("UPDATE v3_cities SET mayor_id=? WHERE chat_id=?",(w["candidate"],int(e["scope_id"])))
            if w:
                await v4_send_news(context.bot,"نتیجه انتخابات Life RP",f"نتیجه انتخابات {e['office']}: {w['candidate']}","election")
    except Exception as e:logger.warning("cleanup: %s",e)


# =============================================================================
# LIFE RP V5 — WORLD / CONSTITUTION / RP ENGINE
# =============================================================================
# V5 is an integrated RP layer over the mature V4 data model.  It does not
# remove the older economy/job/city/company/stock systems; it adds a rule-driven
# world layer, a secure session UI, and a proper legal/court workflow.

V5_PREFIX = "life5|"
V5_NEWS_CHANNEL_ID = int(os.environ.get("NEWS_CHANNEL_ID", "-1001465731038"))
V5_OWNER_ID = int(os.environ.get("OWNER_ID", str(next(iter(ADMIN_IDS), 0))))
V5_ADMIN_IDS = set(ADMIN_IDS) | {5888377320}


def v5_db():
    return db()


def v5_init_db():
    with v5_db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS v5_laws(
          id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, title TEXT,
          description TEXT, category TEXT, fine INTEGER DEFAULT 0,
          jail_hours INTEGER DEFAULT 0, severity INTEGER DEFAULT 1, active INTEGER DEFAULT 1,
          created REAL DEFAULT 0, created_by INTEGER
        );
        CREATE TABLE IF NOT EXISTS v5_cases(
          id INTEGER PRIMARY KEY AUTOINCREMENT, city_id TEXT, complainant INTEGER,
          defendant INTEGER, incident TEXT, status TEXT DEFAULT 'reported',
          investigator INTEGER, prosecutor INTEGER, judge INTEGER, court_chat INTEGER,
          opened REAL DEFAULT 0, updated REAL DEFAULT 0, closed REAL,
          outcome TEXT DEFAULT '', verdict TEXT DEFAULT '', sentence TEXT DEFAULT '', appeal_status TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS v5_case_evidence(
          id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER, submitted_by INTEGER,
          kind TEXT, content TEXT, file_id TEXT DEFAULT '', reliability INTEGER DEFAULT 50,
          created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v5_case_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER, actor INTEGER,
          event TEXT, detail TEXT, created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v5_hearings(
          id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER, judge INTEGER,
          scheduled REAL, status TEXT DEFAULT 'scheduled', opened REAL, attendance_deadline REAL,
          judge_joined REAL, complainant_joined REAL, defendant_joined REAL,
          court_chat INTEGER, result TEXT DEFAULT '', created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v5_hearing_messages(
          id INTEGER PRIMARY KEY AUTOINCREMENT, hearing_id INTEGER, sender INTEGER,
          role TEXT, text TEXT, created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v5_disciplinary(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, role TEXT,
          reason TEXT, severity INTEGER DEFAULT 1, related_case INTEGER,
          created REAL DEFAULT 0, resolved INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v5_reports(
          id INTEGER PRIMARY KEY AUTOINCREMENT, reporter INTEGER, target INTEGER,
          city_id TEXT, category TEXT, text TEXT, status TEXT DEFAULT 'open',
          created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v5_bribes(
          id INTEGER PRIMARY KEY AUTOINCREMENT, payer INTEGER, receiver INTEGER,
          amount INTEGER, purpose TEXT, related_case INTEGER, status TEXT DEFAULT 'offered',
          created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v5_audit(
          id INTEGER PRIMARY KEY AUTOINCREMENT, actor INTEGER, action TEXT,
          target INTEGER DEFAULT 0, amount INTEGER DEFAULT 0, entity TEXT DEFAULT '',
          detail TEXT DEFAULT '', created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v5_trade_escrow(
          id INTEGER PRIMARY KEY AUTOINCREMENT, seller INTEGER, buyer INTEGER,
          asset_type TEXT, asset_id INTEGER, price INTEGER, status TEXT DEFAULT 'pending',
          created REAL DEFAULT 0, completed REAL
        );
        CREATE TABLE IF NOT EXISTS v5_job_apps(
          id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT, scope_id TEXT,
          department_id INTEGER, job_title TEXT, applicant INTEGER, skill TEXT,
          skill_value INTEGER DEFAULT 0, cover TEXT DEFAULT '', status TEXT DEFAULT 'pending',
          reviewed_by INTEGER, created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v5_dept_jobs(
          id INTEGER PRIMARY KEY AUTOINCREMENT, department_id INTEGER, title TEXT,
          skill TEXT, min_skill INTEGER DEFAULT 1, salary INTEGER DEFAULT 0,
          duty TEXT, slots INTEGER DEFAULT 1, active INTEGER DEFAULT 1, created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v5_role_assignments(
          user_id INTEGER PRIMARY KEY, role TEXT, scope TEXT DEFAULT 'national',
          scope_id TEXT DEFAULT '1', appointed_by INTEGER, appointed REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v5_econ_ledger(
          id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT, scope_id TEXT,
          kind TEXT, amount INTEGER, actor INTEGER DEFAULT 0, detail TEXT, created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v5_world_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT,
          effect TEXT, severity INTEGER DEFAULT 1, active INTEGER DEFAULT 1, created REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS v5_settings(key TEXT PRIMARY KEY, value TEXT);
        """)
        defaults=[
          ("L01","سرقت","برداشت یا تصاحب غیرمجاز مال دیگری","مالی",10000,6,2),
          ("L02","کلاهبرداری","فریب برای به‌دست‌آوردن مال یا منفعت","مالی",15000,8,3),
          ("L03","خشونت","آسیب عمدی به شخص دیگر","عمومی",20000,12,4),
          ("L04","رشوه","پیشنهاد یا دریافت منفعت برای تغییر وظیفه اداری","اداری",30000,16,5),
          ("L05","اختلاس","برداشت غیرمجاز از خزانه یا دارایی سازمان","اداری",50000,24,5),
          ("L06","پولشویی","پنهان‌سازی منشأ غیرقانونی پول","مالی",40000,20,5),
          ("L07","تخریب","آسیب عمدی به اموال عمومی یا خصوصی","عمومی",12000,8,3),
          ("L08","اخلال عمومی","ایجاد اختلال عمدی و شدید در خدمات عمومی","عمومی",25000,12,4),
        ]
        for row in defaults:
            c.execute("INSERT OR IGNORE INTO v5_laws(code,title,description,category,fine,jail_hours,severity,created) VALUES(?,?,?,?,?,?,?,?)",(*row,time.time()))
        c.execute("INSERT OR IGNORE INTO v5_settings(key,value) VALUES('constitution','1')")


def v5_btn(text, data):
    return InlineKeyboardButton(text, callback_data=V5_PREFIX + data)


def v5_kb(rows):
    return InlineKeyboardMarkup(rows)


def v5_owner(uid): return uid == V5_OWNER_ID

def v5_admin(uid): return uid in V5_ADMIN_IDS


def v5_session(uid, chat, panel, entity="0", ttl=1200):
    import secrets
    sid=secrets.token_urlsafe(16)
    now=time.time()
    with v5_db() as c:
        c.execute("INSERT INTO v4_sessions(sid,user_id,chat_id,panel,entity_id,created,expires) VALUES(?,?,?,?,?,?,?)",
                  (sid,uid,chat,panel,str(entity),now,now+ttl))
    return sid


def v5_auth(sid, uid, chat, panel, entity=None):
    with v5_db() as c: r=c.execute("SELECT * FROM v4_sessions WHERE sid=?",(sid,)).fetchone()
    return bool(r and r["user_id"]==uid and r["chat_id"]==chat and r["panel"]==panel and r["expires"]>=time.time() and (entity is None or str(r["entity_id"])==str(entity)))


def v5_audit(actor, action, target=0, amount=0, entity="", detail=""):
    with v5_db() as c:
        c.execute("INSERT INTO v5_audit(actor,action,target,amount,entity,detail,created) VALUES(?,?,?,?,?,?,?)",
                  (actor,action,target,amount,entity,detail,time.time()))


def v5_role(uid):
    with v5_db() as c:
        r=c.execute("SELECT role,scope,scope_id FROM v5_role_assignments WHERE user_id=?",(uid,)).fetchone()
        if r: return dict(r)
        n=c.execute("SELECT king_id,president_id FROM v3_country WHERE id=1").fetchone()
        if n and n["king_id"]==uid: return {"role":"king","scope":"national","scope_id":"1"}
        if n and n["president_id"]==uid: return {"role":"president","scope":"national","scope_id":"1"}
    return {"role":"citizen","scope":"none","scope_id":"0"}


def v5_level(uid):
    u=v4_user(uid)
    lvl,title,score,s=v4_level(uid)
    # Broader RP progression: career + social + politics + reputation + life.
    rep=max(0,min(100,int(s["reputation"])))
    score += rep*5
    tiers=[(0,"تازه‌وارد"),(150,"شهروند"),(450,"شهروند فعال"),(900,"ماهر"),(1800,"حرفه‌ای"),
           (3500,"متخصص"),(7000,"کارآفرین"),(14000,"بانفوذ"),(28000,"نخبه"),(55000,"چهره ملی"),(100000,"اسطوره")]
    level=1; name=tiers[0][1]
    for i,(t,n) in enumerate(tiers,1):
        if score>=t: level,name=i,n
    return level,name,score


def v5_city_id(chat_id): return str(chat_id)


def v5_ensure_city(chat_id, title="شهر جدید"):
    with v5_db() as c:
        r=c.execute("SELECT * FROM v3_cities WHERE chat_id=?",(chat_id,)).fetchone()
        if r:return r
        # Compatible with the existing V3 city schema.
        cols=[x[1] for x in c.execute("PRAGMA table_info(v3_cities)").fetchall()]
        if not cols:return None
        vals={"chat_id":chat_id,"name":title,"mayor_id":None,"population":1,"treasury":5000000,"tax":5,"development":20,"approval":70,"industry":50}
        use={k:v for k,v in vals.items() if k in cols}
        q="INSERT INTO v3_cities("+",".join(use)+") VALUES("+",".join("?" for _ in use)+")"
        c.execute(q,tuple(use.values()))
        return c.execute("SELECT * FROM v3_cities WHERE chat_id=?",(chat_id,)).fetchone()


def v5_legal_permission(uid, action, case=None):
    role=v5_role(uid)["role"]
    allowed={
      "report":{"citizen","police","judge","prosecutor","president","mayor","king"},
      "investigate":{"police","prosecutor","judge","king"},
      "arrest":{"police","king"},
      "refer":{"police","prosecutor","king"},
      "schedule":{"judge","king"},
      "verdict":{"judge","king"},
      "discipline":{"police_chief","court_chief","judge","king"},
    }.get(action,set())
    return v5_owner(uid) or role in allowed


async def v5_home(q, uid):
    lvl,name,score=v5_level(uid)
    role=v5_role(uid)["role"]
    rows=[
      [v5_btn("👤 شخصیت من","profile"),v5_btn("💼 شغل و مهارت","career")],
      [v5_btn("💰 اقتصاد","economy"),v5_btn("🏠 دارایی‌ها","assets")],
      [v5_btn("🤝 بازار امن","trade"),v5_btn("📈 بورس","stocks")],
      [v5_btn("👨‍👩‍👧 روابط و خانواده","social"),v5_btn("🎯 مأموریت و رویداد","life")],
      [v5_btn("🏙️ شهر","city"),v5_btn("🇮🇷 کشور و دولت","country")],
      [v5_btn("⚖️ قانون و دادگاه","law"),v5_btn("🚔 پلیس","police")],
      [v5_btn("📰 اخبار","news"),v5_btn("🎫 پشتیبانی","support")],
    ]
    if role in {"president","king"} or v5_admin(uid): rows.append([v5_btn("🏛️ دولت","government")])
    if role in {"mayor","king"} or v5_admin(uid): rows.append([v5_btn("🏙️ مدیریت شهر","mayor")])
    if v5_owner(uid): rows.append([v5_btn("👑 پادشاه — کنترل جهان","king")])
    await q.edit_message_text(f"🌍 <b>Life RP</b>\n━━━━━━━━━━━━\n👤 {q.from_user.first_name}\n🎚 سطح {lvl} — {name}\n✨ امتیاز {score:,}\n🎭 نقش: {role}\n\nاین دنیا با اقتصاد، شغل، روابط، قانون، دولت، شهر و پیامدهای واقعی اداره می‌شود.",parse_mode="HTML",reply_markup=v5_kb(rows))


async def v5_profile(q,uid):
    u=v4_user(uid); lvl,name,score=v5_level(uid); role=v5_role(uid)["role"]
    await q.edit_message_text(f"👤 <b>شناسنامه شهروند</b>\n━━━━━━━━━━━━\nنام: {q.from_user.first_name}\nنقش: {role}\nسطح: {lvl} — {name}\nامتیاز: {score:,}\n💵 نقد: {u['cash']:,}\n🏦 بانک: {u['bank']:,}\n❤️ سلامت: {u['health']}\n⚡ انرژی: {u['energy']}\n😊 شادی: {u['happiness']}\n😰 استرس: {u['stress']}\n🧠 هوش: {u['intelligence']}\n💳 اعتبار: {u['credit']}",parse_mode="HTML",reply_markup=v5_kb([[v5_btn("📚 مهارت‌ها","skills"),v5_btn("📋 سوابق","records")],[v5_btn("↩️ خانه","home")]]))


async def v5_skills(q,uid):
    v4_user(uid)
    with v5_db() as c:
        rows=c.execute("SELECT * FROM user_skills WHERE user_id=?",(uid,)).fetchall()
    text="📚 <b>مهارت‌های من</b>\n━━━━━━━━━━━━\n"
    text += "\n".join(f"• {r['skill']}: {r['level']}" for r in rows) if rows else "هنوز مهارتی ثبت نشده."
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=v5_kb([[v5_btn("🏋️ تمرین","train"),v5_btn("💼 شغل","career")],[v5_btn("↩️ پروفایل","profile")]]))


async def v5_career(q,uid):
    with v5_db() as c:
        jobs=c.execute("SELECT id,title,skill,min_skill,salary,duty,slots FROM v5_dept_jobs WHERE active=1 ORDER BY id DESC LIMIT 15").fetchall()
        deps=c.execute("SELECT id,name,chief_id FROM v4_departments ORDER BY id").fetchall()
    rows=[]
    for j in jobs[:10]: rows.append([v5_btn(f"📋 {j['title']} — {j['salary']:,}",f"applyjob|{j['id']}")])
    rows += [[v5_btn("🏢 استخدام‌های دولتی","jobs")],[v5_btn("🏭 شرکت‌ها","companies")],[v5_btn("📚 مهارت‌ها","skills")],[v5_btn("↩️ خانه","home")]]
    await q.edit_message_text("💼 <b>بازار کار</b>\nهر شغل مهارت لازم و وظیفه مشخص دارد؛ خروجی کار بر اساس مهارت محاسبه می‌شود.\n\n📢 آگهی‌های فعال:",parse_mode="HTML",reply_markup=v5_kb(rows))


async def v5_jobs(q,uid):
    with v5_db() as c:
        rows=c.execute("SELECT h.id,h.job,h.salary,h.skill,h.status,o.name FROM v4_hires h JOIN v4_orgs o ON o.id=h.org_id WHERE h.status='ad' ORDER BY h.id DESC LIMIT 20").fetchall()
    kb=[[v5_btn(f"📢 {r['job']} | {r['salary']:,}",f"applyad|{r['id']}")] for r in rows]
    kb += [[v5_btn("🏛️ شغل‌های تخصصی","career"),v5_btn("↩️ خانه","home")]]
    await q.edit_message_text("📋 <b>استخدام سازمانی</b>\nدرخواست استخدام ثبت می‌شود و رئیس همان سازمان آن را بررسی می‌کند.",parse_mode="HTML",reply_markup=v5_kb(kb))


async def v5_law(q,uid):
    with v5_db() as c:
        cases=c.execute("SELECT * FROM v5_cases WHERE (complainant=? OR defendant=?) AND status NOT IN ('closed','dismissed') ORDER BY id DESC LIMIT 10",(uid,uid)).fetchall()
        reports=c.execute("SELECT * FROM v5_reports WHERE reporter=? ORDER BY id DESC LIMIT 10",(uid,)).fetchall()
    text="⚖️ <b>نظام حقوقی</b>\n━━━━━━━━━━━━\nقانون در Life RP یک سیستم مرحله‌ای است: گزارش → بررسی → تحقیق → جمع‌آوری دلیل → ارجاع → جلسه دادگاه → رأی → تجدیدنظر.\n\n"
    text += "پرونده‌های من:\n" + ("\n".join(f"#{r['id']} {r['status']} — {r['incident'][:45]}" for r in cases) if cases else "پرونده‌ای ندارید.")
    kb=[[v5_btn("📝 ثبت شکایت/گزارش","report")],[v5_btn("🔎 پرونده‌های فعال","mycases"),v5_btn("📜 قوانین","laws")],[v5_btn("↩️ خانه","home")]]
    if v5_legal_permission(uid,"investigate"): kb.insert(1,[v5_btn("👮 پرونده‌های پلیس","police_cases")])
    if v5_role(uid)["role"] in {"judge","court_chief","king"}: kb.insert(1,[v5_btn("⚖️ دادگاه‌های من","judge_cases")])
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=v5_kb(kb))


async def v5_laws(q,uid):
    with v5_db() as c: rows=c.execute("SELECT * FROM v5_laws WHERE active=1 ORDER BY severity DESC,id").fetchall()
    text="📜 <b>قانون اساسی و کیفری Life RP</b>\n━━━━━━━━━━━━\n"
    text += "\n".join(f"<b>{r['code']} — {r['title']}</b>\nجریمه: {r['fine']:,} | حبس: {r['jail_hours']} ساعت\n{r['description']}" for r in rows)
    await q.edit_message_text(text[:3900],parse_mode="HTML",reply_markup=v5_kb([[v5_btn("⚖️ دادگاه","law")],[v5_btn("↩️ خانه","home")]]))


async def v5_report(q,uid):
    sid=v5_session(uid,q.message.chat_id,"report")
    context_pending[(q.message.chat_id,uid)]={"v5":"report","sid":sid}
    await q.edit_message_text("📝 گزارش را در یک پیام بفرست. فرمت:\n<code>شناسه متهم | دسته جرم | شرح اتفاق</code>\n\nاگر متهم را نمی‌شناسی، به‌جای شناسه 0 بنویس.",parse_mode="HTML",reply_markup=v5_kb([[v5_btn("لغو","law")]]))


async def v5_my_cases(q,uid):
    with v5_db() as c: rows=c.execute("SELECT * FROM v5_cases WHERE complainant=? OR defendant=? ORDER BY id DESC LIMIT 20",(uid,uid)).fetchall()
    kb=[[v5_btn(f"⚖️ پرونده #{r['id']} — {r['status']}",f"case|{r['id']}")] for r in rows]
    kb.append([v5_btn("↩️ قانون","law")])
    await q.edit_message_text("⚖️ پرونده‌های مرتبط با شما:",reply_markup=v5_kb(kb))


async def v5_case(q,uid,cid):
    with v5_db() as c:
        r=c.execute("SELECT * FROM v5_cases WHERE id=?",(cid,)).fetchone()
        ev=c.execute("SELECT * FROM v5_case_evidence WHERE case_id=? ORDER BY id",(cid,)).fetchall()
        h=c.execute("SELECT * FROM v5_hearings WHERE case_id=? ORDER BY id DESC LIMIT 1",(cid,)).fetchone()
    if not r or (uid not in {r["complainant"],r["defendant"],r["investigator"],r["judge"],r["prosecutor"]} and not v5_admin(uid)):
        return await q.answer("دسترسی به این پرونده ندارید.",show_alert=True)
    text=f"⚖️ <b>پرونده #{cid}</b>\n━━━━━━━━━━━━\nشاکی: {r['complainant']}\nمتهم: {r['defendant']}\nوضعیت: {r['status']}\nموضوع: {r['incident']}\nتحقیق‌کننده: {r['investigator'] or 'تعیین نشده'}\nقاضی: {r['judge'] or 'تعیین نشده'}\n\nمدارک: {len(ev)}\n"
    if h: text += f"جلسه: {datetime.fromtimestamp(h['scheduled']).strftime('%Y-%m-%d %H:%M')} — {h['status']}\n"
    kb=[]
    if uid in {r["investigator"],r["prosecutor"]} or v5_admin(uid): kb.append([v5_btn("➕ ثبت مدرک","evidence|"+str(cid))])
    if uid==r["judge"] or v5_owner(uid): kb.append([v5_btn("📅 برنامه جلسه","schedule|"+str(cid))])
    if h and h["status"] in {"open","scheduled"} and uid in {r["complainant"],r["defendant"],r["judge"]}: kb.append([v5_btn("⚖️ ورود به جلسه","join|"+str(h["id"]))])
    if uid==r["investigator"] or v5_admin(uid): kb.append([v5_btn("➡️ ارجاع به دادگاه","refer|"+str(cid))])
    if (uid==r["investigator"] or v5_admin(uid)) and r["status"] in {"investigating","arrest_requested"}: kb.append([v5_btn("🔒 درخواست بازداشت","arrest|"+str(cid))])
    if v5_owner(uid) and r["status"] in {"referred","arrest_requested"}: kb.append([v5_btn("⚖️ تعیین قاضی","assignjudge|"+str(cid))])
    if uid==r["judge"] or v5_owner(uid): kb.append([v5_btn("📜 صدور رأی","verdict|"+str(cid))])
    kb.append([v5_btn("↩️ قانون","law")])
    await q.edit_message_text(text[:3900],parse_mode="HTML",reply_markup=v5_kb(kb))


async def v5_police(q,uid):
    role=v5_role(uid)["role"]
    if role not in {"police","police_chief","prosecutor","king"} and not v5_admin(uid):
        return await q.answer("این پنل مخصوص مأموران مجاز است.",show_alert=True)
    with v5_db() as c:
        reports=c.execute("SELECT * FROM v5_reports WHERE status='open' ORDER BY id DESC LIMIT 15").fetchall()
        cases=c.execute("SELECT * FROM v5_cases WHERE status IN ('reported','investigating') ORDER BY id DESC LIMIT 15").fetchall()
    kb=[[v5_btn(f"📝 گزارش #{r['id']} — {r['category']}",f"reportcase|{r['id']}")] for r in reports]
    kb += [[v5_btn(f"🔎 پرونده #{r['id']} — {r['status']}",f"case|{r['id']}")] for r in cases]
    kb.append([v5_btn("↩️ قانون","law")])
    await q.edit_message_text("🚔 <b>پنل پلیس</b>\nبازداشت آزاد نیست: مأمور باید گزارش/حادثه، مبنای قانونی و روند تحقیق داشته باشد.",parse_mode="HTML",reply_markup=v5_kb(kb))


async def v5_reportcase(q,uid,rid):
    if not v5_legal_permission(uid,"investigate"): return await q.answer("دسترسی رد شد.",show_alert=True)
    with v5_db() as c:
        r=c.execute("SELECT * FROM v5_reports WHERE id=?",(rid,)).fetchone()
        if not r:return await q.answer("گزارش پیدا نشد.",show_alert=True)
        c.execute("UPDATE v5_reports SET status='investigating' WHERE id=?",(rid,))
        cur=c.execute("INSERT INTO v5_cases(city_id,complainant,defendant,incident,status,investigator,opened,updated) VALUES(?,?,?,?,?,?,?,?)",
                      (r["city_id"],r["reporter"],r["target"],r["text"],"investigating",uid,time.time(),time.time()))
        cid=cur.lastrowid
        c.execute("INSERT INTO v5_case_events(case_id,actor,event,detail,created) VALUES(?,?,?,?,?)",(cid,uid,"investigation_started",f"report #{rid}",time.time()))
    v5_audit(uid,"start_investigation",r["target"],entity=f"case:{cid}",detail=f"report:{rid}")
    await q.answer(f"تحقیق پرونده #{cid} شروع شد.")
    await v5_case(q,uid,cid)


async def v5_evidence(q,uid,cid):
    with v5_db() as c:r=c.execute("SELECT * FROM v5_cases WHERE id=?",(cid,)).fetchone()
    if not r or uid not in {r["investigator"],r["prosecutor"],r["judge"]} and not v5_admin(uid): return await q.answer("دسترسی رد شد.",show_alert=True)
    context_pending[(q.message.chat_id,uid)]={"v5":"evidence","cid":cid}
    await q.edit_message_text("🔎 مدرک را بفرست. متن یا کپشن عکس/فایل قابل ثبت است. فرمت:\n<code>نوع مدرک | شرح مدرک</code>",parse_mode="HTML")


async def v5_arrest(q,uid,cid):
    with v5_db() as c:
        r=c.execute("SELECT * FROM v5_cases WHERE id=?",(cid,)).fetchone()
        if not r:return await q.answer("پرونده نیست.",show_alert=True)
        if uid not in {r["investigator"]} and not v5_owner(uid): return await q.answer("فقط مأمور پرونده می‌تواند اقدام کند.",show_alert=True)
        ev=c.execute("SELECT COUNT(*) n FROM v5_case_evidence WHERE case_id=?",(cid,)).fetchone()["n"]
        if ev<1:return await q.answer("بدون حداقل یک مدرک قابل بررسی، بازداشت مجاز نیست.",show_alert=True)
        c.execute("UPDATE v5_cases SET status='arrest_requested',updated=? WHERE id=?",(time.time(),cid))
        c.execute("INSERT INTO v5_case_events(case_id,actor,event,detail,created) VALUES(?,?,?,?,?)",(cid,uid,"arrest_requested","evidence threshold met",time.time()))
    v5_audit(uid,"arrest_request",r["defendant"],entity=f"case:{cid}")
    await q.answer("درخواست بازداشت ثبت شد و برای ارجاع قضایی آماده است.")


async def v5_refer(q,uid,cid):
    with v5_db() as c:
        r=c.execute("SELECT * FROM v5_cases WHERE id=?",(cid,)).fetchone()
        if not r or (uid!=r["investigator"] and not v5_owner(uid)): return await q.answer("دسترسی رد شد.",show_alert=True)
        c.execute("UPDATE v5_cases SET status='referred',updated=? WHERE id=?",(time.time(),cid))
        c.execute("INSERT INTO v5_case_events(case_id,actor,event,detail,created) VALUES(?,?,?,?,?)",(cid,uid,"referred_to_court","investigation complete",time.time()))
    await q.answer("پرونده به دادگاه ارجاع شد.")
    await v5_case(q,uid,cid)


async def v5_assignjudge(q,uid,cid):
    if not v5_owner(uid): return await q.answer("تعیین قاضی فقط با پادشاه است.",show_alert=True)
    with v5_db() as c:r=c.execute("SELECT * FROM v5_cases WHERE id=?",(cid,)).fetchone()
    if not r:return await q.answer("پرونده نیست.",show_alert=True)
    context_pending[(q.message.chat_id,uid)]={"v5":"assignjudge","cid":cid}
    await q.edit_message_text("⚖️ شناسه کاربر قاضی را بفرست. قاضی باید در نقش judge باشد یا پادشاه او را منصوب کند.")


async def v5_schedule(q,uid,cid):
    with v5_db() as c:r=c.execute("SELECT * FROM v5_cases WHERE id=?",(cid,)).fetchone()
    if not r or (uid!=r["judge"] and not v5_owner(uid)): return await q.answer("فقط قاضی پرونده می‌تواند جلسه تعیین کند.",show_alert=True)
    context_pending[(q.message.chat_id,uid)]={"v5":"schedule","cid":cid}
    await q.edit_message_text("📅 زمان جلسه را به شکل <code>YYYY-MM-DD HH:MM</code> بفرست.",parse_mode="HTML")


async def v5_hearing_job(context):
    await v5_open_hearing(context.bot, int(context.job.data))


async def v5_open_hearing(bot,hid):
    with v5_db() as c:
        h=c.execute("SELECT * FROM v5_hearings WHERE id=?",(hid,)).fetchone()
        if not h or h["status"] not in {"scheduled"}: return
        now=time.time(); deadline=now+300
        c.execute("UPDATE v5_hearings SET status='open',opened=?,attendance_deadline=? WHERE id=?",(now,deadline,hid))
        c.execute("UPDATE v5_cases SET status='hearing' WHERE id=?",(h["case_id"],))
        case=c.execute("SELECT * FROM v5_cases WHERE id=?",(h["case_id"],)).fetchone()
    text=f"⚖️ جلسه دادگاه پرونده #{case['id']} آغاز شد.\n\nقاضی: {case['judge']}\nشاکی: {case['complainant']}\nمتهم: {case['defendant']}\n\n⏱ طرفین ۵ دقیقه برای اعلام حضور فرصت دارند."
    for uid in {case["judge"],case["complainant"],case["defendant"]}:
        if uid:
            try: await bot.send_message(uid,text,reply_markup=v5_kb([[v5_btn("⚖️ ورود به جلسه",f"join|{hid}")]]))
            except Exception: pass


async def v5_join(q,uid,hid):
    with v5_db() as c:
        h=c.execute("SELECT * FROM v5_hearings WHERE id=?",(hid,)).fetchone()
        if not h:return await q.answer("جلسه نیست.",show_alert=True)
        case=c.execute("SELECT * FROM v5_cases WHERE id=?",(h["case_id"],)).fetchone()
        role=""
        col=""
        if uid==case["judge"]: role,col="judge","judge_joined"
        elif uid==case["complainant"]: role,col="complainant","complainant_joined"
        elif uid==case["defendant"]: role,col="defendant","defendant_joined"
        else:return await q.answer("شما عضو این جلسه نیستید.",show_alert=True)
        c.execute(f"UPDATE v5_hearings SET {col}=? WHERE id=?",(time.time(),hid))
        c.execute("INSERT INTO v5_hearing_messages(hearing_id,sender,role,text,created) VALUES(?,?,?,?,?)",(hid,uid,role,"اعلام حضور",time.time()))
    await q.edit_message_text(f"⚖️ وارد جلسه پرونده #{case['id']} شدی.\nنقش: {role}\n\nبرای ارسال صحبت خود از دکمه پیام استفاده کن.",reply_markup=v5_kb([[v5_btn("💬 ارسال صحبت","speak|"+str(hid))],[v5_btn("📎 افزودن مدرک","hevidence|"+str(hid))],[v5_btn("↩️ پرونده","case|"+str(case['id']))]]))


async def v5_speak(q,uid,hid):
    context_pending[(q.message.chat_id,uid)]={"v5":"speak","hid":hid}
    await q.edit_message_text("💬 متن دفاع/اظهارات خود را بفرست.")


async def v5_verdict(q,uid,cid):
    with v5_db() as c:r=c.execute("SELECT * FROM v5_cases WHERE id=?",(cid,)).fetchone()
    if not r or (uid!=r["judge"] and not v5_owner(uid)):return await q.answer("فقط قاضی پرونده.",show_alert=True)
    context_pending[(q.message.chat_id,uid)]={"v5":"verdict","cid":cid}
    await q.edit_message_text("📜 رأی را بفرست:\n<code>محکومیت/تبرئه | شرح رأی | ساعت حبس | مبلغ جریمه</code>",parse_mode="HTML")


async def v5_king(q,uid):
    if not v5_owner(uid):return await q.answer("فقط پادشاه.",show_alert=True)
    with v5_db() as c:
        n=c.execute("SELECT * FROM v3_country WHERE id=1").fetchone()
        users=c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        cases=c.execute("SELECT COUNT(*) n FROM v5_cases WHERE status NOT IN ('closed','dismissed')").fetchone()["n"]
        audit=c.execute("SELECT COUNT(*) n FROM v5_audit").fetchone()["n"]
    rows=[[v5_btn("👑 انتصابات","appoint"),v5_btn("🗳 انتخابات","elections")],
          [v5_btn("🏛️ دولت و وزارتخانه‌ها","government"),v5_btn("🏙️ شهرها و شهرداران","cities")],
          [v5_btn("⚖️ نظارت حقوقی","oversight"),v5_btn("💰 خزانه و اقتصاد","treasury")],
          [v5_btn("📰 خبر رسمی","kingnews"),v5_btn("📜 قوانین","laws")],
          [v5_btn("📋 لاگ و حسابرسی","audit"),v5_btn("🎫 پشتیبانی","adminsupport")],
          [v5_btn("🌍 رویداد جهانی","worldadmin")],[v5_btn("↩️ خانه","home")]]
    await q.edit_message_text(f"👑 <b>پادشاه — مالک بازی</b>\n━━━━━━━━━━━━\nقدرت پادشاه مطلق است و کنترل فنی/اجرایی جهان را دارد.\n\n👥 کاربران: {users}\n⚖️ پرونده فعال: {cases}\n📋 رویدادهای ثبت‌شده: {audit}\n💰 خزانه: {n['treasury']:,}\n🇮🇷 رئیس‌جمهور: {n['president_id'] or 'ندارد'}\n\nتمام مداخلات مدیریتی در Audit ثبت می‌شوند تا تاریخچه جهان پاک نشود.",parse_mode="HTML",reply_markup=v5_kb(rows))


async def v5_country(q,uid):
    with v5_db() as c:n=c.execute("SELECT * FROM v3_country WHERE id=1").fetchone()
    rows=[[v5_btn("🏛️ رئیس‌جمهور","president")],[v5_btn("🏢 وزارتخانه‌ها","ministries")],[v5_btn("🗳 انتخابات","elections")],[v5_btn("📊 اقتصاد ملی","treasury")],[v5_btn("↩️ خانه","home")]]
    if v5_owner(uid): rows.insert(0,[v5_btn("👑 پنل پادشاه","king")])
    await q.edit_message_text(f"🇮🇷 <b>کشور</b>\n━━━━━━━━━━━━\n👑 پادشاه: {n['king_id'] or '—'}\n🏛 رئیس‌جمهور: {n['president_id'] or '—'}\n💰 خزانه: {n['treasury']:,}\n📈 GDP: {n['gdp']:,}\n💸 تورم: {n['inflation']:.1f}%\n⭐ رضایت: {n['approval']}%",parse_mode="HTML",reply_markup=v5_kb(rows))


async def v5_government(q,uid):
    role=v5_role(uid)["role"]
    if role not in {"president","king"} and not v5_admin(uid):return await q.answer("دسترسی دولت رد شد.",show_alert=True)
    with v5_db() as c:
        n=c.execute("SELECT * FROM v3_country WHERE id=1").fetchone(); ds=c.execute("SELECT * FROM v4_departments WHERE scope='national' ORDER BY id").fetchall()
    rows=[[v5_btn(f"🏢 {d['name']} | رئیس {d['chief_id'] or '—'}","dept|"+str(d['id']))] for d in ds]
    rows += [[v5_btn("📢 ایجاد آگهی استخدام","deptad")],[v5_btn("↩️ کشور","country")]]
    await q.edit_message_text("🏛️ <b>دولت</b>\nرئیس‌جمهور مسئول سیاست‌گذاری و بودجه است، اما اختیار پلیسی/قضایی مستقیم ندارد. هر تصمیم مالی در حسابداری جهان ثبت می‌شود.",parse_mode="HTML",reply_markup=v5_kb(rows))


async def v5_dept(q,uid,did):
    with v5_db() as c:d=c.execute("SELECT * FROM v4_departments WHERE id=?",(did,)).fetchone()
    role=v5_role(uid)["role"]
    if not d:return await q.answer("وزارتخانه نیست.",show_alert=True)
    if uid!=d["chief_id"] and role not in {"president","king"} and not v5_admin(uid):return await q.answer("فقط رئیس وزارتخانه یا مقام بالاتر.",show_alert=True)
    with v5_db() as c: jobs=c.execute("SELECT * FROM v5_dept_jobs WHERE department_id=? AND active=1",(did,)).fetchall()
    kb=[[v5_btn(f"📢 {j['title']} | مهارت {j['skill']} ≥ {j['min_skill']}",f"deptjob|{j['id']}")] for j in jobs]
    kb += [[v5_btn("➕ آگهی جدید","newdeptjob|"+str(did))],[v5_btn("↩️ دولت","government")]]
    await q.edit_message_text(f"🏢 <b>{d['name']}</b>\nبودجه: {d['budget']:,}\nحقوق رئیس: {d['salary']:,}\nوظیفه: {d['mission'] or '—'}\n\nآگهی‌ها:",parse_mode="HTML",reply_markup=v5_kb(kb))


async def v5_mayor(q,uid):
    chat=q.message.chat_id
    with v5_db() as c: city=c.execute("SELECT * FROM v3_cities WHERE chat_id=?",(chat,)).fetchone()
    if not city:return await q.answer("این گروه هنوز شهر نیست.",show_alert=True)
    if city["mayor_id"]!=uid and not v5_owner(uid) and not v5_admin(uid):return await q.answer("این پنل فقط برای شهردار همین شهر است.",show_alert=True)
    rows=[[v5_btn("💰 خزانه و درآمد","citymoney"),v5_btn("🏗 پروژه‌ها","cityproject")],
          [v5_btn("🏥 خدمات شهری","cityservices"),v5_btn("📢 استخدام","cityjobs")],
          [v5_btn("🗳 انتخابات شهرداری","cityelection")],[v5_btn("↩️ شهر","city")]]
    await q.edit_message_text(f"🏙️ <b>شهرداری</b>\nشهر: {city['name']}\n💰 خزانه: {city['treasury']:,}\n👥 جمعیت: {city['population']}\n📈 توسعه: {city['development']}\n⭐ رضایت: {city['approval']}%\n💸 مالیات: {city['tax']}%\n\nشهردار اداره خدمات و بودجه را انجام می‌دهد، نه بازداشت و صدور حکم.",parse_mode="HTML",reply_markup=v5_kb(rows))


async def v5_city(q,uid):
    chat=q.message.chat_id
    city=v5_ensure_city(chat,q.message.chat.title or "شهر جدید") if q.message.chat.type!="private" else None
    if not city:
        await q.edit_message_text("🏙️ برای ساخت شهر، بازی را در یک گروه اجرا کن. هر گروه می‌تواند یک شهر مستقل باشد.",reply_markup=v5_kb([[v5_btn("↩️ خانه","home")]]));return
    with v5_db() as c:
        active=c.execute("SELECT COUNT(*) n FROM v5_cases WHERE city_id=? AND status NOT IN ('closed','dismissed')",(str(chat),)).fetchone()["n"]
    rows=[[v5_btn("🏛 شهردار","mayor")],[v5_btn("🚔 پلیس شهر","police")],[v5_btn("⚖️ دادگاه شهر","law")],[v5_btn("🏢 شرکت‌ها","companies")],[v5_btn("🗳 انتخابات","cityelection")],[v5_btn("📰 اخبار شهر","news")],[v5_btn("↩️ خانه","home")]]
    await q.edit_message_text(f"🏙️ <b>{city['name']}</b>\n━━━━━━━━━━━━\n👥 جمعیت: {city['population']}\n💰 خزانه: {city['treasury']:,}\n📈 توسعه: {city['development']}\n⭐ رضایت: {city['approval']}%\n⚖️ پرونده فعال: {active}\n💸 مالیات: {city['tax']}%",parse_mode="HTML",reply_markup=v5_kb(rows))


async def v5_treasury(q,uid):
    with v5_db() as c:n=c.execute("SELECT * FROM v3_country WHERE id=1").fetchone(); rows=c.execute("SELECT * FROM v5_econ_ledger WHERE scope='national' ORDER BY id DESC LIMIT 12").fetchall()
    text=f"💰 <b>اقتصاد ملی</b>\nخزانه: {n['treasury']:,}\nGDP: {n['gdp']:,}\nتورم: {n['inflation']:.1f}%\n\nمنابع درآمد: مالیات شهرها، مالیات شرکت‌ها، عوارض، سود بنگاه‌های دولتی و رویدادهای اقتصادی.\n\nآخرین ثبت‌ها:\n"+"\n".join(f"• {r['kind']}: {r['amount']:,} — {r['detail']}" for r in rows)
    await q.edit_message_text(text[:3900],parse_mode="HTML",reply_markup=v5_kb([[v5_btn("↩️ کشور","country")],[v5_btn("👑 پادشاه","king")]] if v5_owner(uid) else [[v5_btn("↩️ کشور","country")]]))


async def v5_elections(q,uid):
    with v5_db() as c:
        es=c.execute("SELECT * FROM v4_elections WHERE status='open' ORDER BY id DESC").fetchall()
    rows=[[v5_btn(f"🗳 {e['office']} #{e['id']}",f"velection|{e['id']}")] for e in es]
    if v5_owner(uid): rows.append([v5_btn("➕ شروع انتخابات ملی","start_election")])
    rows.append([v5_btn("↩️ کشور","country")])
    await q.edit_message_text("🗳 <b>انتخابات</b>\nانتخابات خودکار طبق تقویم بازی انجام می‌شود و پادشاه می‌تواند انتخابات دستی را نیز آغاز/پایان دهد. رأی‌ها یک‌بار مصرف و ثبت‌شده‌اند.",parse_mode="HTML",reply_markup=v5_kb(rows))


async def v5_election(q,uid,eid):
    with v5_db() as c:
        e=c.execute("SELECT * FROM v4_elections WHERE id=?",(eid,)).fetchone(); cs=c.execute("SELECT * FROM v4_candidates WHERE election_id=?",(eid,)).fetchall(); vv=c.execute("SELECT candidate FROM v4_votes WHERE election_id=? AND voter=?",(eid,uid)).fetchone()
    if not e:return await q.answer("انتخابات نیست.",show_alert=True)
    rows=[[v5_btn(f"🗳 رأی به {c['user_id']}",f"vote|{eid}|{c['user_id']}")] for c in cs]
    if not vv: rows.append([v5_btn("✍️ نامزدی","candidate|"+str(eid))])
    rows.append([v5_btn("↩️ انتخابات","elections")])
    await q.edit_message_text(f"🗳 <b>{e['office']}</b>\nوضعیت: {e['status']}\nپایان: {datetime.fromtimestamp(e['ends']).strftime('%Y-%m-%d %H:%M') if e['ends'] else '—'}\n\nهر شهروند واجدشرایط یک رأی دارد.",parse_mode="HTML",reply_markup=v5_kb(rows))


async def v5_vote(q,uid,eid,candidate):
    with v5_db() as c:
        e=c.execute("SELECT * FROM v4_elections WHERE id=? AND status='open'",(eid,)).fetchone()
        if not e:return await q.answer("رأی‌گیری بسته است.",show_alert=True)
        if c.execute("SELECT 1 FROM v4_votes WHERE election_id=? AND voter=?",(eid,uid)).fetchone():return await q.answer("قبلاً رأی داده‌ای.",show_alert=True)
        if not c.execute("SELECT 1 FROM v4_candidates WHERE election_id=? AND user_id=?",(eid,candidate)).fetchone():return await q.answer("نامزد معتبر نیست.",show_alert=True)
        c.execute("INSERT INTO v4_votes(election_id,voter,candidate,created) VALUES(?,?,?,?)",(eid,uid,candidate,time.time()))
    v5_audit(uid,"cast_vote",candidate,entity=f"election:{eid}")
    await q.answer("رأی شما ثبت شد.")


async def v5_candidate(q,uid,eid):
    context_pending[(q.message.chat_id,uid)]={"v5":"candidate","eid":eid}
    await q.edit_message_text("✍️ بیانیه انتخاباتی خود را بفرست.")


async def v5_president(q,uid):
    with v5_db() as c:n=c.execute("SELECT president_id FROM v3_country WHERE id=1").fetchone()
    if n["president_id"]!=uid and not v5_owner(uid) and not v5_admin(uid):return await q.answer("فقط رئیس‌جمهور.",show_alert=True)
    rows=[[v5_btn("🏥 سلامت","policy|health"),v5_btn("🎓 آموزش","policy|education")],[v5_btn("🛡 امنیت","policy|security"),v5_btn("🛣 زیرساخت","policy|infra")],[v5_btn("🏛 وزارتخانه‌ها","ministries")],[v5_btn("↩️ کشور","country")]]
    await q.edit_message_text("🏛️ <b>رئیس‌جمهور</b>\nمسئول سیاست‌گذاری، بودجه و هماهنگی دولت است. اختیار مستقیم بازداشت یا صدور حکم ندارد.",parse_mode="HTML",reply_markup=v5_kb(rows))


async def v5_policy(q,uid,key):
    with v5_db() as c:n=c.execute("SELECT * FROM v3_country WHERE id=1").fetchone()
    if n["president_id"]!=uid and not v5_owner(uid):return await q.answer("دسترسی رد شد.",show_alert=True)
    cost={"health":1500000,"education":1500000,"security":1800000,"infra":2000000}[key]
    col={"health":"health","education":"education","security":"security","infra":"infrastructure"}[key]
    with v5_db() as c:
        if n["treasury"]<cost:return await q.answer("خزانه کافی نیست.",show_alert=True)
        c.execute(f"UPDATE v3_country SET treasury=treasury-?,{col}=MIN(100,{col}+5),approval=MIN(100,approval+1) WHERE id=1",(cost,))
        c.execute("INSERT INTO v5_econ_ledger(scope,scope_id,kind,amount,actor,detail,created) VALUES(?,?,?,?,?,?,?)",("national","1","policy",-cost,uid,key,time.time()))
    v5_audit(uid,"presidential_policy",0,cost,"country",key)
    await v5_president(q,uid)


async def v5_ministries(q,uid):
    with v5_db() as c:ds=c.execute("SELECT * FROM v4_departments WHERE scope='national'").fetchall()
    rows=[[v5_btn(f"{d['name']} — {d['chief_id'] or 'بدون رئیس'}",f"dept|{d['id']}")] for d in ds]
    rows.append([v5_btn("↩️ کشور","country")])
    await q.edit_message_text("🏢 <b>وزارتخانه‌ها</b>\nهر وزارتخانه رئیس، بودجه، مأموریت و آگهی استخدام تخصصی دارد.",parse_mode="HTML",reply_markup=v5_kb(rows))


async def v5_companies(q,uid):
    with v5_db() as c: cs=c.execute("SELECT * FROM v4_companies WHERE active=1 ORDER BY id DESC LIMIT 15").fetchall()
    rows=[[v5_btn(f"🏭 {c['name']} | سرمایه {c['capital']:,}",f"company|{c['id']}")] for c in cs]
    rows.append([v5_btn("➕ تأسیس شرکت","newcompany")]);rows.append([v5_btn("↩️ خانه","home")])
    await q.edit_message_text("🏭 <b>اقتصاد شرکت‌ها</b>\nشرکت‌ها درآمد، کارکنان، استخدام، هزینه و رشد دارند.",parse_mode="HTML",reply_markup=v5_kb(rows))


async def v5_company(q,uid,cid):
    with v5_db() as c: co=c.execute("SELECT * FROM v4_companies WHERE id=?",(cid,)).fetchone(); jobs=c.execute("SELECT * FROM v4_company_jobs WHERE company_id=? AND status='open'",(cid,)).fetchall()
    if not co:return await q.answer("شرکت نیست.",show_alert=True)
    rows=[[v5_btn(f"📋 {j['title']} — {j['salary']:,}",f"companyjob|{j['id']}")] for j in jobs]
    if co["owner"]==uid or v5_owner(uid):rows += [[v5_btn("➕ آگهی استخدام","companyad|"+str(cid))]]
    rows.append([v5_btn("↩️ شرکت‌ها","companies")])
    await q.edit_message_text(f"🏭 <b>{co['name']}</b>\nمالک: {co['owner']}\nبخش: {co['sector']}\nسرمایه: {co['capital']:,}\nدرآمد انباشته: {co['revenue']:,}\nکارکنان: {co['employees']}\nسطح: {co['level']}",parse_mode="HTML",reply_markup=v5_kb(rows))


async def v5_trade(q,uid):
    with v5_db() as c: rows=c.execute("SELECT * FROM v4_asset_market WHERE status='open' ORDER BY id DESC LIMIT 15").fetchall()
    kb=[[v5_btn(f"🔁 {r['asset_type']} #{r['asset_id']} — {r['price']:,}",f"buyasset|{r['id']}")] for r in rows]
    kb += [[v5_btn("📦 دارایی‌های من","assets")],[v5_btn("↩️ خانه","home")]]
    await q.edit_message_text("🤝 <b>بازار امن بازیکنان</b>\nخرید دارایی با escrow انجام می‌شود تا پول و مالکیت هم‌زمان منتقل شوند.",parse_mode="HTML",reply_markup=v5_kb(kb))


async def v5_assets(q,uid):
    with v5_db() as c:
        ps=c.execute("SELECT * FROM user_properties WHERE user_id=?",(uid,)).fetchall(); vs=c.execute("SELECT * FROM user_vehicles WHERE user_id=?",(uid,)).fetchall()
    text="🏠 <b>دارایی‌های من</b>\n\nاملاک:\n"+"\n".join(str(dict(x)) for x in ps[:5])+"\n\nخودروها:\n"+"\n".join(str(dict(x)) for x in vs[:5])
    await q.edit_message_text(text[:3900],parse_mode="HTML",reply_markup=v5_kb([[v5_btn("🤝 فروش در بازار","sellasset")],[v5_btn("↩️ خانه","home")]]))


async def v5_simple_action(q,uid,a):
    role=v5_role(uid)["role"]
    chat=q.message.chat_id
    if a=="citymoney":
        with v5_db() as c: city=c.execute("SELECT * FROM v3_cities WHERE chat_id=?",(chat,)).fetchone()
        if not city:return await q.answer("شهر پیدا نشد.",show_alert=True)
        await q.edit_message_text(f"💰 خزانه شهر: {city['treasury']:,}\nمالیات: {city['tax']}%\nدرآمد از مالیات و خدمات شهری به‌صورت دوره‌ای ثبت می‌شود.",reply_markup=v5_kb([[v5_btn("↩️ شهرداری","mayor")]])); return
    if a in {"cityproject","cityservices"}:
        if role not in {"mayor","king"} and not v5_admin(uid):return await q.answer("دسترسی رد شد.",show_alert=True)
        cost=500000 if a=="cityproject" else 300000
        with v5_db() as c:
            city=c.execute("SELECT * FROM v3_cities WHERE chat_id=?",(chat,)).fetchone()
            if not city or city["treasury"]<cost:return await q.answer("خزانه کافی نیست.",show_alert=True)
            c.execute("UPDATE v3_cities SET treasury=treasury-?,development=MIN(100,development+2),approval=MIN(100,approval+1) WHERE chat_id=?",(cost,chat))
            c.execute("INSERT INTO v5_econ_ledger(scope,scope_id,kind,amount,actor,detail,created) VALUES(?,?,?,?,?,?,?)",("city",str(chat),a,-cost,uid,"municipal spending",time.time()))
        v5_audit(uid,a,amount=cost,entity=f"city:{chat}"); await q.answer("اقدام شهری اجرا و در حسابداری ثبت شد."); await v5_mayor(q,uid); return
    if a=="cityjobs":
        await q.edit_message_text("📢 آگهی‌های استخدام شهری در همین سامانه منتشر می‌شوند. رئیس سازمان باید آگهی را با مهارت، حداقل مهارت، حقوق و وظیفه تعریف کند.",reply_markup=v5_kb([[v5_btn("💼 بازار کار","career")],[v5_btn("↩️ شهرداری","mayor")]])); return
    if a=="cities":
        with v5_db() as c: cities=c.execute("SELECT * FROM v3_cities ORDER BY name").fetchall()
        text="🏙️ شهرها\n\n"+"\n".join(f"• {x['name']} — شهردار {x['mayor_id'] or '—'} — خزانه {x['treasury']:,}" for x in cities[:30])
        await q.edit_message_text(text or "هنوز شهری ثبت نشده.",reply_markup=v5_kb([[v5_btn("↩️ پادشاه","king")]])); return
    if a=="oversight":
        with v5_db() as c: rows=c.execute("SELECT * FROM v5_disciplinary WHERE resolved=0 ORDER BY id DESC LIMIT 20").fetchall()
        await q.edit_message_text("⚖️ پرونده‌های انضباطی\n\n"+"\n".join(f"#{r['id']} user={r['user_id']} role={r['role']} — {r['reason']}" for r in rows) or "مورد انضباطی فعالی نیست.",reply_markup=v5_kb([[v5_btn("↩️ پادشاه","king")]])); return
    await q.answer("این بخش به هسته اصلی متصل است و از مسیر تخصصی آن استفاده می‌شود.")


async def v5_stocks(q,uid):
    # Keep the mature V4/V3 stock engine visible through a richer hub.
    try:
        with v5_db() as c: rows=c.execute("SELECT * FROM v3_stocks ORDER BY symbol").fetchall()
        text="📈 <b>بورس Life RP</b>\n━━━━━━━━━━━━\n"+"\n".join(f"{r['symbol']}: {r['price']:,}" for r in rows[:20])
    except Exception:text="📈 بورس در حال راه‌اندازی است."
    await q.edit_message_text(text,parse_mode="HTML",reply_markup=v5_kb([[v5_btn("↩️ خانه","home")]]))


async def v5_economy(q,uid):
    u=v4_user(uid)
    with v5_db() as c: tx=c.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 12",(uid,)).fetchall()
    text=f"💰 <b>اقتصاد شخصی</b>\nنقد: {u['cash']:,}\nبانک: {u['bank']:,}\nدارایی خالص: {net_worth(u):,}\nوام: {u['loan']:,}\n\nتراکنش‌های اخیر:\n"+"\n".join(f"• {t['kind']} {t['amount']:,} — {t['note']}" for t in tx)
    await q.edit_message_text(text[:3900],parse_mode="HTML",reply_markup=v5_kb([[v5_btn("🏦 بانک","bank")],[v5_btn("📈 بورس","stocks"),v5_btn("🤝 بازار","trade")],[v5_btn("↩️ خانه","home")]]))


async def v5_support(q,uid):
    await q.edit_message_text("🎫 <b>پشتیبانی</b>\nدسته را انتخاب کن:",parse_mode="HTML",reply_markup=v5_kb([[v5_btn("🐞 مشکل فنی","supportcat|bug"),v5_btn("⚖️ شکایت","supportcat|complaint")],[v5_btn("💰 اقتصاد","supportcat|economy"),v5_btn("🛡 امنیت","supportcat|security")],[v5_btn("📨 تیکت‌های من","mytickets")],[v5_btn("↩️ خانه","home")]]))


async def v5_supportcat(q,uid,cat):
    context_pending[(q.message.chat_id,uid)]={"v5":"support","cat":cat}
    await q.edit_message_text("✉️ پیام پشتیبانی را بفرست. متن، کپشن عکس یا فایل قابل ثبت است.")


async def v5_mytickets(q,uid):
    with v5_db() as c: rows=c.execute("SELECT * FROM v4_tickets WHERE user_id=? ORDER BY id DESC LIMIT 15",(uid,)).fetchall()
    await q.edit_message_text("🎫 تیکت‌های من\n\n"+"\n".join(f"#{r['id']} — {r['category']} — {r['status']}" for r in rows),reply_markup=v5_kb([[v5_btn("↩️ پشتیبانی","support")]]))


async def v5_news(q,uid):
    with v5_db() as c: rows=c.execute("SELECT * FROM v4_news ORDER BY id DESC LIMIT 15").fetchall()
    text="📰 <b>اخبار رسمی جهان</b>\n━━━━━━━━━━━━\n"+"\n\n".join(f"<b>{r['title']}</b>\n{r['body']}" for r in rows)
    await q.edit_message_text(text[:3900],parse_mode="HTML",reply_markup=v5_kb([[v5_btn("↩️ خانه","home")]]))


async def v5_admin_audit(q,uid):
    if not v5_owner(uid):return await q.answer("فقط پادشاه.",show_alert=True)
    with v5_db() as c: rows=c.execute("SELECT * FROM v5_audit ORDER BY id DESC LIMIT 25").fetchall()
    text="📋 <b>حسابرسی جهان</b>\n\n"+"\n".join(f"#{r['id']} {r['actor']} → {r['action']} {r['target']} {r['amount']:,} {r['entity']} {r['detail']}" for r in rows)
    await q.edit_message_text(text[:3900],parse_mode="HTML",reply_markup=v5_kb([[v5_btn("↩️ پادشاه","king")]]))


async def v5_appoint(q,uid):
    if not v5_owner(uid):return await q.answer("فقط پادشاه.",show_alert=True)
    context_pending[(q.message.chat_id,uid)]={"v5":"appoint"}
    await q.edit_message_text("👑 انتصاب:\n<code>role | user_id | scope | scope_id</code>\nنقش‌های نمونه: president, mayor, police_chief, judge, prosecutor, minister, army_commander",parse_mode="HTML")


async def v5_start_election(q,uid):
    if not v5_owner(uid):return await q.answer("فقط پادشاه.",show_alert=True)
    with v5_db() as c:
        c.execute("UPDATE v4_elections SET status='closed' WHERE scope='national' AND office='رئیس‌جمهور' AND status='open'")
        c.execute("INSERT INTO v4_elections(scope,scope_id,office,status,started,ends) VALUES('national','1','رئیس‌جمهور','open',?,?)",(time.time(),time.time()+86400))
    v5_audit(uid,"start_manual_election",entity="national_president")
    await v5_elections(q,uid)


async def v5_callback(update,context):
    q=update.callback_query
    if not q or not (q.data or "").startswith(V5_PREFIX): return False
    uid=q.from_user.id; chat=q.message.chat_id; p=(q.data or "").split("|"); a=p[1] if len(p)>1 else ""
    try:
        if a=="home": await v5_home(q,uid)
        elif a=="profile": await v5_profile(q,uid)
        elif a=="skills": await v5_skills(q,uid)
        elif a=="career": await v5_career(q,uid)
        elif a=="jobs": await v5_jobs(q,uid)
        elif a=="law": await v5_law(q,uid)
        elif a=="laws": await v5_laws(q,uid)
        elif a=="report": await v5_report(q,uid)
        elif a=="mycases": await v5_my_cases(q,uid)
        elif a=="case": await v5_case(q,uid,int(p[2]))
        elif a=="police": await v5_police(q,uid)
        elif a=="police_cases": await v5_police(q,uid)
        elif a=="judge_cases": await v5_police(q,uid)
        elif a=="reportcase": await v5_reportcase(q,uid,int(p[2]))
        elif a=="evidence": await v5_evidence(q,uid,int(p[2]))
        elif a=="arrest": await v5_arrest(q,uid,int(p[2]))
        elif a=="refer": await v5_refer(q,uid,int(p[2]))
        elif a=="schedule": await v5_schedule(q,uid,int(p[2]))
        elif a=="assignjudge": await v5_assignjudge(q,uid,int(p[2]))
        elif a=="join": await v5_join(q,uid,int(p[2]))
        elif a=="speak": await v5_speak(q,uid,int(p[2]))
        elif a=="verdict": await v5_verdict(q,uid,int(p[2]))
        elif a=="country": await v5_country(q,uid)
        elif a=="government": await v5_government(q,uid)
        elif a=="dept": await v5_dept(q,uid,int(p[2]))
        elif a=="ministries": await v5_ministries(q,uid)
        elif a=="president": await v5_president(q,uid)
        elif a=="policy": await v5_policy(q,uid,p[2])
        elif a=="mayor": await v5_mayor(q,uid)
        elif a=="city": await v5_city(q,uid)
        elif a=="treasury": await v5_treasury(q,uid)
        elif a=="elections": await v5_elections(q,uid)
        elif a=="velection": await v5_election(q,uid,int(p[2]))
        elif a=="vote": await v5_vote(q,uid,int(p[2]),int(p[3]))
        elif a=="candidate": await v5_candidate(q,uid,int(p[2]))
        elif a=="start_election": await v5_start_election(q,uid)
        elif a=="king": await v5_king(q,uid)
        elif a=="appoint": await v5_appoint(q,uid)
        elif a=="audit": await v5_admin_audit(q,uid)
        elif a=="companies": await v5_companies(q,uid)
        elif a=="company": await v5_company(q,uid,int(p[2]))
        elif a=="trade": await v5_trade(q,uid)
        elif a=="assets": await v5_assets(q,uid)
        elif a=="stocks": await v5_stocks(q,uid)
        elif a=="economy": await v5_economy(q,uid)
        elif a=="support": await v5_support(q,uid)
        elif a=="supportcat": await v5_supportcat(q,uid,p[2])
        elif a=="mytickets": await v5_mytickets(q,uid)
        elif a=="news": await v5_news(q,uid)
        elif a in {"cities","oversight","citymoney","cityproject","cityservices","cityjobs"}: await v5_simple_action(q,uid,a)
        elif a in {"records","life","citymoney","cityproject","cityservices","cityjobs","cityelection","worldadmin","adminsupport","kingnews","oversight","newcompany","sellasset","buyasset","companyjob","companyad","deptad","deptjob","newdeptjob","applyjob","applyad","train","bank"}:
            # Route mature V4 features when available; no dead buttons.
            if a=="bank": await v4_bank(q,uid)
            elif a=="train": await v4_train(q,uid)
            elif a=="applyad": await v4_apply(q,uid,int(p[2]))
            elif a=="companyjob": await q.answer("درخواست استخدام شرکت از پنل شرکت ثبت می‌شود.")
            elif a=="records":
                with v5_db() as c: rr=c.execute("SELECT * FROM judicial_records WHERE user_id=? ORDER BY id DESC LIMIT 15",(uid,)).fetchall()
                await q.edit_message_text("📋 سوابق:\n\n"+"\n".join(f"{r['kind']} — {r['reason']}" for r in rr) if rr else "📋 سابقه‌ای ثبت نشده.",reply_markup=v5_kb([[v5_btn("↩️ پروفایل","profile")]]))
            elif a=="life": await v4_missions(q,uid)
            elif a=="worldadmin":
                if not v5_owner(uid): return await q.answer("فقط پادشاه.",show_alert=True)
                context_pending[(chat,uid)]={"v5":"worldevent"}; await q.edit_message_text("رویداد جهانی را بفرست: عنوان | توضیح | اثر")
            elif a=="kingnews":
                if not v5_owner(uid): return await q.answer("فقط پادشاه.",show_alert=True)
                context_pending[(chat,uid)]={"v5":"kingnews"}; await q.edit_message_text("خبر رسمی را بفرست: عنوان | متن")
            elif a=="adminsupport":
                if not v5_owner(uid): return await q.answer("فقط پادشاه.",show_alert=True)
                await v3_ticket_admin(q,uid)
            elif a=="applyjob":
                context_pending[(chat,uid)]={"v5":"applyjob","jid":int(p[2])}; await q.edit_message_text("برای این شغل یک متن کوتاه معرفی و تجربه خودت را بفرست.")
            else: await q.answer("این بخش از هسته قدیمی بازی مدیریت می‌شود.")
        else: await q.answer("عملیات ناشناخته.",show_alert=True)
        try: await q.answer()
        except: pass
    except Exception as e:
        logger.exception("v5 callback: %s",e)
        try: await q.answer("⚠️ عملیات ناموفق بود.",show_alert=True)
        except: pass
    return True


async def v5_text_router(update,context):
    if not update.message:return False
    uid=update.effective_user.id; chat=update.effective_chat.id
    pend=context_pending.get((chat,uid))
    if not pend or pend.get("v5") is None:return False
    text=(update.message.text or update.message.caption or "").strip()
    kind=pend["v5"]
    try:
        if kind=="report":
            parts=[x.strip() for x in text.split("|",2)]
            if len(parts)!=3: raise ValueError()
            target=int(parts[0]) if parts[0].isdigit() else 0; cat,detail=parts[1],parts[2]
            with v5_db() as c:
                cur=c.execute("INSERT INTO v5_reports(reporter,target,city_id,category,text,created) VALUES(?,?,?,?,?,?)",(uid,target,str(chat),cat,detail,time.time()))
                rid=cur.lastrowid
            v5_audit(uid,"create_report",target,entity=f"report:{rid}")
            context_pending.pop((chat,uid),None); await update.message.reply_text(f"📝 گزارش #{rid} ثبت شد. پلیس باید آن را بررسی و مستندسازی کند."); return True
        if kind=="evidence":
            typ,detail=(text.split("|",1)+["مدرک"])[0:2] if "|" in text else ("text",text)
            with v5_db() as c:c.execute("INSERT INTO v5_case_evidence(case_id,submitted_by,kind,content,created) VALUES(?,?,?,?,?)",(pend["cid"],uid,typ,detail,time.time()))
            context_pending.pop((chat,uid),None); await update.message.reply_text("🔎 مدرک در پرونده ثبت شد."); return True
        if kind=="assignjudge":
            judge=int(text.strip())
            with v5_db() as c:
                rr=c.execute("SELECT * FROM v5_role_assignments WHERE user_id=? AND role='judge'",(judge,)).fetchone()
                if not rr and not v5_admin(judge): return await update.message.reply_text("این کاربر قاضی نیست.")
                c.execute("UPDATE v5_cases SET judge=?,status='referred',updated=? WHERE id=?",(judge,time.time(),pend["cid"]))
                c.execute("INSERT INTO v5_case_events(case_id,actor,event,detail,created) VALUES(?,?,?,?,?)",(pend["cid"],uid,"judge_assigned",str(judge),time.time()))
            v5_audit(uid,"assign_judge",judge,entity=f"case:{pend['cid']}")
            context_pending.pop((chat,uid),None); await update.message.reply_text("⚖️ قاضی پرونده تعیین شد."); return True
        if kind=="schedule":
            dt=datetime.strptime(text,"%Y-%m-%d %H:%M"); ts=dt.timestamp(); cid=pend["cid"]
            with v5_db() as c:
                case=c.execute("SELECT * FROM v5_cases WHERE id=?",(cid,)).fetchone()
                cur=c.execute("INSERT INTO v5_hearings(case_id,judge,scheduled,court_chat,created) VALUES(?,?,?,?,?)",(cid,case["judge"],ts,chat,time.time()))
                hid=cur.lastrowid;c.execute("UPDATE v5_cases SET status='hearing_scheduled',updated=? WHERE id=?",(time.time(),cid))
            if context.job_queue: context.job_queue.run_once(v5_hearing_job,when=max(1,ts-time.time()),data=hid)
            context_pending.pop((chat,uid),None); await update.message.reply_text(f"📅 جلسه برای {dt.strftime('%Y-%m-%d %H:%M')} تنظیم شد. ۵ دقیقه پس از شروع، عدم حضور ثبت می‌شود."); return True
        if kind=="speak":
            with v5_db() as c:
                h=c.execute("SELECT * FROM v5_hearings WHERE id=?",(pend["hid"],)).fetchone(); case=c.execute("SELECT * FROM v5_cases WHERE id=?",(h["case_id"],)).fetchone()
                role="judge" if uid==case["judge"] else "complainant" if uid==case["complainant"] else "defendant" if uid==case["defendant"] else "observer"
                c.execute("INSERT INTO v5_hearing_messages(hearing_id,sender,role,text,created) VALUES(?,?,?,?,?)",(pend["hid"],uid,role,text[:3500],time.time()))
            # Mirror the statement to all three courtroom participants so the hearing feels live.
            for participant in {case["judge"],case["complainant"],case["defendant"]}:
                if participant:
                    try: await context.bot.send_message(participant,f"⚖️ {role}:\n{text[:3500]}")
                    except Exception: pass
            context_pending.pop((chat,uid),None); await update.message.reply_text("💬 اظهارات در صورت‌جلسه ثبت شد و برای اعضای جلسه ارسال شد."); return True
        if kind=="verdict":
            parts=[x.strip() for x in text.split("|",3)];
            if len(parts)!=4: raise ValueError()
            outcome,detail,jail,fine=parts; jail=int(jail);fine=int(fine);cid=pend["cid"]
            with v5_db() as c:
                case=c.execute("SELECT * FROM v5_cases WHERE id=?",(cid,)).fetchone()
                c.execute("UPDATE v5_cases SET status='closed',outcome=?,verdict=?,sentence=?,closed=?,updated=? WHERE id=?",(outcome,detail,f"jail={jail};fine={fine}",time.time(),time.time(),cid))
                c.execute("INSERT INTO v5_case_events(case_id,actor,event,detail,created) VALUES(?,?,?,?,?)",(cid,uid,"verdict",detail,time.time()))
                c.execute("INSERT INTO judicial_records(user_id,kind,reason,detail,issuer_id,created_at) VALUES(?,?,?,?,?,?)",(case["defendant"],"verdict",outcome,detail,uid,time.time()))
                if fine>0:
                    c.execute("UPDATE users SET bank=MAX(0,bank-?) WHERE user_id=?",(fine,case["defendant"]))
                    c.execute("UPDATE v3_country SET treasury=treasury+? WHERE id=1",(fine,))
            v5_audit(uid,"verdict",case["defendant"],fine,entity=f"case:{cid}",detail=detail)
            context_pending.pop((chat,uid),None); await update.message.reply_text("📜 رأی ثبت و در سوابق قضایی ذخیره شد."); return True
        if kind=="candidate":
            with v5_db() as c:c.execute("INSERT OR REPLACE INTO v4_candidates(election_id,user_id,manifesto) VALUES(?,?,?)",(pend["eid"],uid,text[:1500]))
            context_pending.pop((chat,uid),None); await update.message.reply_text("✍️ نامزدی ثبت شد."); return True
        if kind=="support":
            with v5_db() as c:
                cur=c.execute("INSERT INTO v4_tickets(user_id,category,text,created) VALUES(?,?,?,?)",(uid,pend["cat"],text[:3500],time.time())); tid=cur.lastrowid
            context_pending.pop((chat,uid),None); await update.message.reply_text(f"🎫 تیکت #{tid} ثبت شد."); return True
        if kind=="appoint":
            role,target,scope,scope_id=[x.strip() for x in text.split("|",3)]; target=int(target)
            if not v5_owner(uid):return True
            with v5_db() as c:
                c.execute("INSERT OR REPLACE INTO v5_role_assignments(user_id,role,scope,scope_id,appointed_by,appointed) VALUES(?,?,?,?,?,?)",(target,role,scope,scope_id,uid,time.time()))
                if role=="president":c.execute("UPDATE v3_country SET president_id=? WHERE id=1",(target,))
            v5_audit(uid,"appoint_role",target,entity=role,detail=f"{scope}:{scope_id}")
            context_pending.pop((chat,uid),None); await update.message.reply_text("👑 انتصاب انجام شد."); return True
        if kind=="kingnews":
            title,body=text.split("|",1)
            await v4_send_news(context.bot,title,body,"king");v5_audit(uid,"publish_news",entity="national_news")
            context_pending.pop((chat,uid),None);await update.message.reply_text("📰 خبر رسمی منتشر شد.");return True
        if kind=="worldevent":
            title,desc,effect=[x.strip() for x in text.split("|",2)]
            with v5_db() as c:c.execute("INSERT INTO v5_world_events(title,description,effect,created) VALUES(?,?,?,?)",(title,desc,effect,time.time()))
            context_pending.pop((chat,uid),None);await update.message.reply_text("🌍 رویداد جهانی ثبت شد.");return True
        if kind=="applyjob":
            jid=pend["jid"]
            with v5_db() as c:
                j=c.execute("SELECT * FROM v5_dept_jobs WHERE id=? AND active=1",(jid,)).fetchone()
                # Skill is intentionally checked here, not merely on the button.
                sr=c.execute("SELECT level FROM user_skills WHERE user_id=? AND skill=?",(uid,j["skill"])).fetchone() if j else None
                val=int(sr["level"]) if sr else 0
                if not j:return await update.message.reply_text("آگهی بسته شده.")
                if val<j["min_skill"]:return await update.message.reply_text(f"مهارت {j['skill']} کافی نیست. حداقل {j['min_skill']} لازم است.")
                c.execute("INSERT INTO v5_job_apps(scope,scope_id,department_id,job_title,applicant,skill,skill_value,cover,created) VALUES(?,?,?,?,?,?,?,?,?)",("national","1",j["department_id"],j["title"],uid,j["skill"],val,text[:1500],time.time()))
            context_pending.pop((chat,uid),None);await update.message.reply_text("📨 درخواست استخدام ثبت شد و برای رئیس سازمان ارسال می‌شود.");return True
    except Exception as e:
        logger.exception("v5 text: %s",e); await update.message.reply_text("⚠️ فرمت نادرست است. عملیات ثبت نشد."); return True
    return False


async def v5_engine_tick(context):
    try:
        with v5_db() as c:
            # Needs and maintenance: the personal-life simulation continues.
            c.execute("UPDATE users SET hunger=MIN(100,hunger+2),sleep=MAX(0,sleep-1),energy=MAX(0,energy-1),stress=MIN(100,stress+0.5)")
            # National revenue: a transparent accounting layer over the existing city economy.
            total=0
            for city in c.execute("SELECT * FROM v3_cities").fetchall():
                pop=max(1,int(city["population"])); tax=max(0,int(city["tax"])); industry=max(1,int(city["industry"]))
                income=max(0,int(pop*tax*120*industry/50))
                c.execute("UPDATE v3_cities SET treasury=treasury+?,last_income=? WHERE chat_id=?",(income,time.time(),city["chat_id"]))
                total += income
                c.execute("INSERT INTO v5_econ_ledger(scope,scope_id,kind,amount,detail,created) VALUES(?,?,?,?,?,?)",("city",str(city["chat_id"]),"tax",income,"city taxation",time.time()))
            if total:
                share=int(total*.15);c.execute("UPDATE v3_country SET treasury=treasury+? WHERE id=1",(share,))
                c.execute("INSERT INTO v5_econ_ledger(scope,scope_id,kind,amount,detail,created) VALUES(?,?,?,?,?,?)",("national","1","city_share",share,"15% national share",time.time()))
            # Skill-based work outcomes for active V5 department hires.
            for j in c.execute("SELECT * FROM v5_job_apps WHERE status='accepted'").fetchall():
                skill=j["skill_value"]; bonus=max(0,min(200,skill*5))
                c.execute("UPDATE users SET bank=bank+? WHERE user_id=?",(max(1000,bonus*100),j["applicant"]))
            # Expire sessions.
            c.execute("DELETE FROM v4_sessions WHERE expires<?",(time.time(),))
    except Exception as e: logger.warning("v5 engine: %s",e)


async def v5_hearing_tick(context):
    try:
        now=time.time()
        with v5_db() as c:
            hs=c.execute("SELECT * FROM v5_hearings WHERE status='open' AND attendance_deadline<=?",(now,)).fetchall()
            for h in hs:
                missing=[]
                case=c.execute("SELECT * FROM v5_cases WHERE id=?",(h["case_id"],)).fetchone()
                for col,label in (("judge_joined","قاضی"),("complainant_joined","شاکی"),("defendant_joined","متهم")):
                    if not h[col]: missing.append((label,case["judge"] if col=="judge_joined" else case["complainant"] if col=="complainant_joined" else case["defendant"]))
                status="in_progress"
                c.execute("UPDATE v5_hearings SET status=? WHERE id=?",(status,h["id"]))
                for label,who in missing:
                    if who:c.execute("INSERT INTO v5_case_events(case_id,actor,event,detail,created) VALUES(?,?,?,?,?)",(case["id"],0,"no_show",label,time.time()))
                if not h["judge_joined"] and case["judge"]:
                    c.execute("INSERT INTO v5_disciplinary(user_id,role,reason,severity,related_case,created) VALUES(?,?,?,?,?,?)",(case["judge"],"judge","عدم حضور در جلسه مقرر",2,case["id"],time.time()))
                    c.execute("UPDATE v5_cases SET status='judge_absent',updated=? WHERE id=?",(time.time(),case["id"]))
                elif not h["defendant_joined"]:
                    c.execute("INSERT INTO v5_case_events(case_id,actor,event,detail,created) VALUES(?,?,?,?,?)",(case["id"],0,"default_judgment_allowed","defendant no-show after 5 minutes",time.time()))
        for h in hs:
            try: await context.bot.send_message(h["court_chat"],f"⚖️ مهلت حضور جلسه پرونده #{h['case_id']} تمام شد. عدم حضورها در صورت‌جلسه ثبت شد.")
            except: pass
    except Exception as e: logger.warning("hearing tick: %s",e)


async def v5_daily_tick(context):
    # Automatic elections and macro effects; manual elections never rewrite their history.
    try:
        with v5_db() as c:
            es=c.execute("SELECT * FROM v4_elections WHERE status='open' AND ends>0 AND ends<=?",(time.time(),)).fetchall()
            for e in es:
                w=c.execute("SELECT candidate,COUNT(*) n FROM v4_votes WHERE election_id=? GROUP BY candidate ORDER BY n DESC,candidate",(e["id"],)).fetchone()
                c.execute("UPDATE v4_elections SET status='closed',winner=? WHERE id=?",(w["candidate"] if w else None,e["id"]))
                if w:
                    if e["scope"]=="national": c.execute("UPDATE v3_country SET president_id=? WHERE id=1",(w["candidate"],))
                    elif e["scope"]=="city": c.execute("UPDATE v3_cities SET mayor_id=? WHERE chat_id=?",(w["candidate"],int(e["scope_id"])))
        for e in es:
            try: await v4_send_news(context.bot,"🗳 نتیجه انتخابات",f"انتخابات {e['office']} به پایان رسید. نتیجه در تاریخچه ثبت شد.","election")
            except: pass
    except Exception as e: logger.warning("election tick: %s",e)


def v5_register(app):
    v5_init_db()
    app.add_handler(CallbackQueryHandler(v5_callback,pattern=r"^life5\|"),group=-100)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND,v5_text_router),group=-100)
    app.add_handler(CommandHandler(["start","life","liferp","life5"],v5_command),group=-100)


async def v5_command(update,context):
    v5_init_db(); v4_user(update.effective_user.id)
    # Group menus are generated per click; the UI never trusts callback owner data.
    await update.message.reply_text("🌍 <b>Life RP</b>\nزندگی مجازی تو از اینجا شروع می‌شود.",parse_mode="HTML",reply_markup=v5_kb([[v5_btn("🚀 ورود به زندگی","home")]]))

def main_v4():
    # ONE unified Life RP bot. Legacy functions remain available as internal
    # building blocks, but are not registered as competing user interfaces.
    v4_init_db()
    token = os.environ.get("BOT_TOKEN", "6625504512:AAEmWjFSZ-qUbvIpiA7zIxNpX-HLxC2WFoo").strip()
    if not token:
        raise SystemExit("BOT_TOKEN را در Environment Variable قرار بده.")
    init_db()
    init_combined_db()
    v3_db_init()

    app = Application.builder().token(token).post_init(setup_bot_commands).build()

    # Only the unified V6 UI is registered.
    v5_register(app)

    if app.job_queue:
        app.job_queue.run_repeating(v5_engine_tick, interval=900, first=30)
        app.job_queue.run_repeating(v5_hearing_tick, interval=30, first=30)
        app.job_queue.run_repeating(v5_daily_tick, interval=300, first=90)

    logger.info("Life RP V6 unified started; owner=%s news=%s", V5_OWNER_ID, V5_NEWS_CHANNEL_ID)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__":
    main_v4()


def v6_world_principles_text():
    return (
        "🌍 <b>Life RP — یک جهان، یک ربات</b>\n\n"
        "هر قابلیت باید دلیل، کار، تصمیم، نتیجه و پیامد داشته باشد.\n"
        "قدرت مقام‌ها بر اساس وظیفه و نقش آن‌هاست.\n"
        "👑 پادشاه مالک بازی و دارای اختیار مطلق مدیریتی است.\n"
        "🏛 رئیس‌جمهور کشور را اداره می‌کند، نه دادگاه را.\n"
        "🏙 شهردار شهر را اداره می‌کند، نه دادگاه را.\n"
        "👮 پلیس تحقیق و اجرای قانون می‌کند و باید مبنای قانونی داشته باشد.\n"
        "⚖️ قاضی پرونده را رسیدگی و حکم صادر می‌کند.\n"
        "همه اقدامات مهم جهان بازی ثبت و قابل پیگیری هستند."
    )
