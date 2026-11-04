import os
import re
import json
import random
import sqlite3
import logging
import asyncio
from contextlib import closing
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ChatType
from telegram.error import TelegramError, RetryAfter, Conflict
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ============================================================
# MEOWIE BOT - Virtual points only / cPanel friendly
# ============================================================
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

DB_PATH = os.getenv("DB_PATH", os.path.join(DATA_DIR, "meowie.sqlite3"))
TOKEN = os.getenv("BOT_TOKEN", "6625504512:AAHbru5G5Yc97C-OQ5_kbI--8VADbXUrzD0").strip()
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "5888377320"))
except ValueError:
    raise RuntimeError("ADMIN_ID must be numeric")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID is not set")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler(os.path.join(LOG_DIR, "bot.log"), encoding="utf-8"), logging.StreamHandler()],
)
logger = logging.getLogger("meowie")

# Single-instance protection for cPanel/Linux.
LOCK_PATH = os.path.join(BASE_DIR, ".meowbet.lock")
_LOCK_FILE = None

def acquire_single_instance():
    global _LOCK_FILE
    try:
        import fcntl
        _LOCK_FILE = open(LOCK_PATH, "w")
        fcntl.flock(_LOCK_FILE.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _LOCK_FILE.write(str(os.getpid()))
        _LOCK_FILE.flush()
        return True
    except (ImportError, BlockingIOError, OSError):
        return False

# Game/economy settings. All currency is virtual "میو".
MIN_GAME = 20_000
MAX_GAME = 15_000_000
DICE_TIMEOUT = 60
DICE_PENALTY = 0.50
DAILY_BONUS = 5_000
REFERRAL_BONUS = 10_000
POOP_MULTIPLIERS = [1.2, 1.4, 1.6, 2.0, 3.0]
POOP_COUNTS = [1, 1, 2, 2, 3]
POOP_ROWS = 5
POOP_COLS = 4
PAGE_SIZE = 8

ADMIN_BALANCE, ADMIN_CHANNEL, ADMIN_BROADCAST, ADMIN_USER_SEARCH = 10, 11, 12, 13
PAYMENT_CARD = "760188800770"


def utc_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def format_mio(n: int) -> str:
    return f"{int(n):,}"


def parse_amount(text: str) -> int:
    """Parse Latin/Persian game amounts such as 50000, 50k, 50کی, 50کا, 50ک."""
    if not text:
        return 0
    t = str(text).strip().lower()
    t = t.translate(str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    ))
    t = t.replace(",", "").replace("٬", "").replace("،", "").replace(" ", "")

    multiplier = 1
    if re.search(r"(?:میلیون|مگ|mn|million|m)$", t):
        multiplier = 1_000_000
        t = re.sub(r"(?:میلیون|مگ|mn|million|m)$", "", t)
    elif re.search(r"(?:هزار|کی|کا|ک|k|thousand)$", t):
        multiplier = 1_000
        t = re.sub(r"(?:هزار|کی|کا|ک|k|thousand)$", "", t)

    m = re.search(r"\d+(?:\.\d+)?", t)
    if not m:
        return 0
    try:
        return int(float(m.group(0)) * multiplier)
    except (ValueError, OverflowError):
        return 0


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db() -> None:
    with closing(db()) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT NOT NULL,
            balance INTEGER NOT NULL DEFAULT 0 CHECK(balance >= 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_daily REAL NOT NULL DEFAULT 0,
            referral_by INTEGER,
            referral_rewarded INTEGER NOT NULL DEFAULT 0,
            games_count INTEGER NOT NULL DEFAULT 0,
            wins_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        CREATE TABLE IF NOT EXISTS transactions(
            tx_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('deposit','withdraw','admin')),
            amount INTEGER NOT NULL,
            status TEXT NOT NULL,
            receipt TEXT,
            card TEXT,
            admin_id INTEGER,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_tx_status ON transactions(status);
        CREATE TABLE IF NOT EXISTS ledger(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            delta INTEGER NOT NULL,
            reason TEXT NOT NULL,
            ref_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
        CREATE TABLE IF NOT EXISTS dice_bets(
            user_id INTEGER PRIMARY KEY,
            target TEXT NOT NULL,
            amount INTEGER NOT NULL,
            dices TEXT NOT NULL DEFAULT '[]',
            chat_id INTEGER NOT NULL,
            message_id INTEGER,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS poop_games(
            user_id INTEGER PRIMARY KEY,
            amount INTEGER NOT NULL,
            step INTEGER NOT NULL DEFAULT 0,
            poops TEXT NOT NULL,
            history TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            message_id INTEGER,
            config TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS game_stats(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            game TEXT NOT NULL,
            amount INTEGER NOT NULL,
            result TEXT NOT NULL,
            payout INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_game_user ON game_stats(user_id);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS gift_links(
            code TEXT PRIMARY KEY,
            owner_id INTEGER NOT NULL,
            amount_per_user INTEGER NOT NULL,
            capacity INTEGER NOT NULL,
            claimed_count INTEGER NOT NULL DEFAULT 0,
            remaining_balance INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(owner_id) REFERENCES users(user_id)
        );
        CREATE TABLE IF NOT EXISTS gift_claims(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(code,user_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
        CREATE TABLE IF NOT EXISTS required_chats(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL DEFAULT '',
            username TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL DEFAULT '',
            chat_type TEXT NOT NULL DEFAULT 'channel',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS dart_bets(
            user_id INTEGER PRIMARY KEY,
            target TEXT NOT NULL,
            amount INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS football_games(
            user_id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            message_id INTEGER,
            shots INTEGER NOT NULL DEFAULT 0,
            goals INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS group_chats(
            chat_id INTEGER PRIMARY KEY, title TEXT NOT NULL DEFAULT '', username TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS active_questions(
            chat_id INTEGER PRIMARY KEY, question_id TEXT NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL,
            prize INTEGER NOT NULL, created_at REAL NOT NULL
        );
        """)
        # Backward-compatible schema migration for databases created by older bot versions.
        # CREATE TABLE IF NOT EXISTS does not add newly introduced columns, so add them safely here.
        migrations = {
            "gift_links": {
                "owner_id": "INTEGER NOT NULL DEFAULT 0",
                "amount_per_user": "INTEGER NOT NULL DEFAULT 0",
                "capacity": "INTEGER NOT NULL DEFAULT 0",
                "claimed_count": "INTEGER NOT NULL DEFAULT 0",
                "remaining_balance": "INTEGER NOT NULL DEFAULT 0",
                "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
                "active": "INTEGER NOT NULL DEFAULT 1",
            },
            "gift_claims": {
                "code": "TEXT NOT NULL DEFAULT ''",
                "user_id": "INTEGER NOT NULL DEFAULT 0",
                "amount": "INTEGER NOT NULL DEFAULT 0",
                "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
            },
            "poop_games": {
                "config": "TEXT NOT NULL DEFAULT '{}'",
            },
            "transactions": {
                "admin_id": "INTEGER",
                "note": "TEXT",
                "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
            },
        }
        for table, columns in migrations.items():
            existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            for col, definition in columns.items():
                if col not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")

        # Repair rows produced by an older gift schema.
        conn.execute("UPDATE gift_links SET claimed_count=0 WHERE claimed_count IS NULL")
        conn.execute("UPDATE gift_links SET active=1 WHERE active IS NULL")
        conn.execute("UPDATE gift_links SET remaining_balance=amount_per_user*capacity WHERE remaining_balance IS NULL OR remaining_balance=0")

        defaults = {
            "required_channel": os.getenv("REQUIRED_CHANNEL", "").strip(),
            "required_channel_url": os.getenv("REQUIRED_CHANNEL_URL", "").strip(),
        }
        for k, v in defaults.items():
            conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", ("dice_mult", "1.5"))
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", ("poop_rows", str(POOP_ROWS)))
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", ("poop_cols", str(POOP_COLS)))
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", ("poop_counts", ",".join(map(str, POOP_COUNTS))))
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", ("poop_mults", ",".join(map(str, POOP_MULTIPLIERS))))
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", ("football_goal_values", "4,5"))
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", ("football_shots", "3"))
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", ("leaderboard_reward_count", "0"))
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", ("leaderboard_rewards", "{}"))
        for k,v in {
            "referrer_bonus":"100000", "referred_bonus":"50000",
            "dart_amount":"20000", "dart_multiplier":"2.0",
            "dart_white_values":"1,3,5", "dart_red_values":"2,4,6",
            "quiz_enabled":"1", "quiz_interval_minutes":"10", "quiz_prize":"50000", "quiz_timeout_seconds":"120",
            "daily_bonus":"5000"
        }.items():
            conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k,v))
        old_channel = defaults.get("required_channel", "")
        old_url = defaults.get("required_channel_url", "")
        if old_channel:
            conn.execute(
                """INSERT OR IGNORE INTO required_chats(chat_id,title,username,url,chat_type)
                   VALUES(?,?,?,?,?)""",
                (old_channel, old_channel, old_channel if old_channel.startswith("@") else "", old_url, "channel"),
            )


def setting(key: str, default: str = "") -> str:
    with closing(db()) as conn:
        r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default


def set_setting(key: str, value: str) -> None:
    with closing(db()) as conn:
        conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def ensure_user(u, referral_by: Optional[int] = None) -> sqlite3.Row:
    with closing(db()) as conn:
        conn.execute("""
            INSERT INTO users(user_id,username,first_name,referral_by)
            VALUES(?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                updated_at=CURRENT_TIMESTAMP
        """, (u.id, u.username or "", u.first_name or "کاربر", referral_by if referral_by and referral_by != u.id else None))
        return conn.execute("SELECT * FROM users WHERE user_id=?", (u.id,)).fetchone()


def get_user(user_id: int) -> sqlite3.Row:
    with closing(db()) as conn:
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def get_balance(user_id: int) -> int:
    r = get_user(user_id)
    return int(r["balance"]) if r else 0


def atomic_balance(user_id: int, delta: int, reason: str, ref_id: Optional[str] = None) -> int:
    """Atomic balance update + ledger entry. Never allows a negative balance."""
    with closing(db()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            conn.rollback()
            raise ValueError("کاربر پیدا نشد")
        new_balance = int(row["balance"]) + int(delta)
        if new_balance < 0:
            conn.rollback()
            raise ValueError("موجودی کافی نیست")
        conn.execute("UPDATE users SET balance=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (new_balance, user_id))
        conn.execute("INSERT INTO ledger(user_id,delta,reason,ref_id) VALUES(?,?,?,?)", (user_id, delta, reason, ref_id))
        conn.commit()
        return new_balance


def log_game(user_id: int, game: str, amount: int, result: str, payout: int = 0) -> None:
    with closing(db()) as conn:
        conn.execute("INSERT INTO game_stats(user_id,game,amount,result,payout) VALUES(?,?,?,?,?)", (user_id, game, amount, result, payout))
        conn.execute("UPDATE users SET games_count=games_count+1, wins_count=wins_count+? WHERE user_id=?", (1 if result in ("win", "cashout") else 0, user_id))


def main_keyboard(user_id: Optional[int] = None) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton("💰 موجودی"), KeyboardButton("➕ واریز")],
        [KeyboardButton("➖ برداشت"), KeyboardButton("🎁 لینک هدیه")],
        [KeyboardButton("👥 دعوت دوستان"), KeyboardButton("🎁 جایزه روزانه")],
        [KeyboardButton("🎮 بازی‌ها")],
        [KeyboardButton("🏆 جدول برترین‌ها"), KeyboardButton("📜 تاریخچه")],
        [KeyboardButton("❓ راهنما"), KeyboardButton("➕ افزودن ربات به گروه")],
    ]
    if user_id == ADMIN_ID:
        rows.append([KeyboardButton("🛠 پنل مدیریت")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def help_text() -> str:
    return (
        "╭━━━「 🎰 MEOWBET | میوبت 」━━━╮\n"
        "│ 🐾 راهنمای کامل ربات\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "💰 «حساب و کیف پول»\n"
        "• 💰 موجودی — مشاهده موجودی لحظه‌ای\n"
        "• ➕ واریز — ثبت درخواست شارژ حساب و ارسال رسید\n"
        "• ➖ برداشت — ثبت درخواست برداشت و پیگیری وضعیت\n"
        "• 📜 تاریخچه — مشاهده سوابق بازی‌های شما\n\n"
        "🎮 «بازی‌ها»\n"
        "• 🎲 #زوج مبلغ — بازی زوج\n"
        "• 🎲 #فرد مبلغ — بازی فرد\n"
        "• 💩 #پوپ مبلغ — بازی پوپ و انتخاب خانه‌ها\n"
        "• 🎯 #سفید مبلغ — دارت سفید\n"
        "• 🎯 #قرمز مبلغ — دارت قرمز\n"
        "• ⚽ #فوتبال — بازی فوتبال؛ سپس شوت‌های ⚽ را بفرست\n\n"
        "🎯 دارت: بعد از ثبت بازی، دقیقاً یک دارت 🎯 در همان گروه ارسال کن؛ نتیجه بر اساس تنظیمات مالک محاسبه می‌شود.\n"
        "⚽ فوتبال: با #فوتبال شروع کن و سپس توپ ⚽ بفرست؛ تعداد شوت و اعداد گل از پنل مدیریت قابل تنظیم است.\n\n"
        "🎁 «هدیه و دعوت»\n"
        "• 🎁 لینک هدیه — ساخت لینک هدیه با ظرفیت و مبلغ دلخواه\n"
        "• 👥 دعوت دوستان — لینک دعوت اختصاصی و دریافت پاداش\n"
        "• 🎁 جایزه روزانه — دریافت پاداش روزانه در صورت آماده بودن زمان دریافت\n\n"
        "🧠 «چالش گروهی»\n"
        "هر چند دقیقه یک سؤال رندوم ریاضی یا اطلاعات عمومی در گروه‌های فعال ارسال می‌شود. نفر اول با پاسخ صحیح جایزه می‌گیرد.\n\n"
        "📌 بازی‌ها و چالش‌ها در گروه انجام می‌شوند. برای استفاده از عضویت اجباری، ابتدا در کانال‌ها/گروه‌های تعیین‌شده عضو شوید.\n"
        "⚙️ مبالغ جایزه، ضرایب و تنظیمات اصلی توسط مالک از پنل مدیریت قابل تغییر است.\n\n"
        "❤️ موفق باشی و با دقت بازی کن!"
    )


async def get_required_chats():
    with closing(db()) as conn:
        return conn.execute(
            "SELECT * FROM required_chats WHERE enabled=1 ORDER BY id"
        ).fetchall()


async def is_joined(bot, user_id: int) -> bool:
    chats = await get_required_chats()
    if not chats:
        return True
    for chat in chats:
        try:
            m = await bot.get_chat_member(chat["chat_id"], user_id)
            if not (
                m.status in ("creator", "administrator", "member")
                or (m.status == "restricted" and getattr(m, "is_member", False))
            ):
                return False
        except TelegramError:
            logger.exception("membership check failed chat=%s user=%s", chat["chat_id"], user_id)
            return False
    return True


async def require_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chats = await get_required_chats()
    if not chats:
        return True
    u = update.effective_user
    if not u or await is_joined(context.bot, u.id):
        return True

    buttons = []
    for i, chat in enumerate(chats, 1):
        url = chat["url"]
        if not url and chat["username"].startswith("@"):
            url = f"https://t.me/{chat['username'][1:]}"
        if url:
            label = f"📢 عضویت {i}: {chat['title'] or chat['username'] or chat['chat_id']}"
            buttons.append([InlineKeyboardButton(label[:60], url=url)])

    buttons.append([InlineKeyboardButton("✅ بررسی عضویت همه", callback_data="check_join")])
    text = (
        "🔒 برای استفاده از میوبت باید در همه کانال‌ها/گروه‌های اجباری عضو باشی.\n"
        "بعد از عضویت، «بررسی عضویت همه» را بزن."
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(buttons)
        )
    elif update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    referral = None
    if context.args:
        arg = context.args[0]
        gm = re.fullmatch(r"gift_([a-f0-9]+)", arg, re.I)
        if gm:
            ensure_user(u)
            if not await require_join(update, context):
                return
            await gift_claim(update, context, gm.group(1))
            return
        m = re.fullmatch(r"ref_(\d+)", arg)
        if m:
            referral = int(m.group(1))
    before = get_user(u.id)
    ensure_user(u, referral if before is None else None)
    if not await require_join(update, context):
        return
    referral_result=(False,0,0)
    row_now=get_user(u.id)
    if row_now and row_now['referral_by'] and not int(row_now['referral_rewarded']):
        referral_result=process_referral(u.id,int(row_now['referral_by']))
    text = (
        "╭━━━「 🎰 MEOWBET | میوبت 」━━━╮\n"
        "│ 🐾 خوش اومدی به میوبت!\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "🎮 بازی‌ها داخل گروه انجام می‌شن.\n"
        "⚽ برای فوتبال از #فوتبال استفاده کن و سپس شوت ⚽ بفرست.\n\n"
        f"🪙 موجودی شما: {format_mio(get_balance(u.id))} میو\n\n"
        "از منوی زیر استفاده کن 👇"
    )
    await update.message.reply_text(text, reply_markup=main_keyboard(u.id))
    if referral_result[0]:
        await update.message.reply_text(f"🎉 پاداش دعوت فعال شد!\n+{format_mio(referral_result[2])} میو به شما رسید.")
        try: await context.bot.send_message(referral,f"🎉 کاربر جدید با لینک شما وارد شد! +{format_mio(referral_result[1])} میو")
        except TelegramError: pass


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    ensure_user(u)
    await update.message.reply_text(f"💰 موجودی لحظه‌ای شما: {format_mio(get_balance(u.id))} میو", reply_to_message_id=update.message.message_id)


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(help_text(), reply_to_message_id=update.message.message_id)


async def games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 بازی‌های MEOWBET\n\n🎲 #زوج 20کی | #فرد 20کی\n💩 #پوپ 20کی\n🎯 #سفید 20کی | #قرمز 20کی\n⚽ #فوتبال\n\n"
        "🎯 برای دارت، بعد از ثبت بازی دقیقاً یک دارت 🎯 در همان گروه بفرست.\n"
        "⚽ برای فوتبال، بعد از #فوتبال شوت ⚽ بفرست؛ تعداد شوت‌ها و اعداد گل از پنل مالک قابل تنظیم است.\n"
        "📌 بازی فوتبال بدون مبلغ‌گذاری و شرط انجام می‌شود."
    )

async def add_group_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    me = await context.bot.get_me()
    url = f"https://t.me/{me.username}?startgroup=true"
    await update.message.reply_text("➕ برای افزودن MEOWBET به گروه روی دکمه زیر بزن:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ افزودن ربات به گروه", url=url)]]))


# --------------------------- Daily / leaderboard / history ---------------------------
async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    ensure_user(u)
    now = utc_ts()
    with closing(db()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT last_daily FROM users WHERE user_id=?", (u.id,)).fetchone()
        last = float(row["last_daily"])
        if now - last < 86400:
            remain = int(86400 - (now - last))
            h, rem = divmod(remain, 3600); m, _ = divmod(rem, 60)
            conn.rollback()
            await update.message.reply_text(f"⏳ جایزه روزانه‌ات قبلاً دریافت شده. حدود {h} ساعت و {m} دقیقه دیگه دوباره بیا.")
            return
        daily_reward = max(0, int(setting("daily_bonus", str(DAILY_BONUS))))
        conn.execute("UPDATE users SET last_daily=?, balance=balance+?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (now, daily_reward, u.id))
        conn.execute("INSERT INTO ledger(user_id,delta,reason) VALUES(?,?,?)", (u.id, daily_reward, "daily_bonus"))
        conn.commit()
    await update.message.reply_text(f"🎁 جایزه روزانه دریافت شد!\n+{format_mio(daily_reward)} میو\n💰 موجودی: {format_mio(get_balance(u.id))} میو")


def get_leaderboard_rewards():
    try: count=min(max(int(setting("leaderboard_reward_count","0")),0),100)
    except (TypeError,ValueError): count=0
    try: raw=json.loads(setting("leaderboard_rewards","{}")); raw=raw if isinstance(raw,dict) else {}
    except (TypeError,ValueError,json.JSONDecodeError): raw={}
    return count,{i:int(raw.get(str(i),0)) for i in range(1,count+1) if str(raw.get(str(i),"0")).isdigit() and int(raw.get(str(i),0))>0}

async def leaderboard(update,context):
    count,rewards=get_leaderboard_rewards(); limit=max(10,count)
    with closing(db()) as conn: rows=conn.execute("SELECT username,first_name,balance FROM users ORDER BY balance DESC,user_id ASC LIMIT ?",(limit,)).fetchall()
    lines=["🏆 <b>جدول برترین‌ها</b>",""]
    for i,r in enumerate(rows,1):
        name=f"@{r['username']}" if r["username"] else r["first_name"]; extra=f" | 🎁 جایزه: {format_mio(rewards[i])} میو" if i in rewards else ""; lines.append(f"{i}. {name} — {format_mio(r['balance'])} میو{extra}")
    if not rows: lines.append("هنوز کاربری ثبت نشده است.")
    await update.message.reply_text("\n".join(lines),parse_mode="HTML")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    with closing(db()) as conn:
        rows = conn.execute("SELECT game,amount,result,payout,created_at FROM game_stats WHERE user_id=? ORDER BY id DESC LIMIT 10", (u.id,)).fetchall()
    if not rows:
        await update.message.reply_text("📜 هنوز بازی ثبت‌شده‌ای نداری.")
        return
    lines = ["📜 آخرین بازی‌های شما\n"]
    for r in rows:
        g = (
            "🎲 تاس" if r["game"] == "dice"
            else "💩 پوپ" if r["game"] == "poop"
            else "🎯 دارت" if r["game"] == "dart"
            else "🧠 چالش"
        )
        result = "برد" if r["result"] == "win" else "کش‌اوت" if r["result"] == "cashout" else "باخت" if r["result"] == "loss" else r["result"]
        lines.append(f"{g} | {format_mio(r['amount'])} | {result} | پرداخت: {format_mio(r['payout'])}")
    await update.message.reply_text("\n".join(lines))



# --------------------------- Referral ---------------------------
def referral_link(bot_username: str, user_id: int) -> str:
    return f"https://t.me/{bot_username}?start=ref_{user_id}"

async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; ensure_user(u); me=await context.bot.get_me()
    with closing(db()) as conn:
        invited=conn.execute("SELECT COUNT(*) c FROM users WHERE referral_by=?",(u.id,)).fetchone()["c"]
    link=referral_link(me.username,u.id) if me.username else ""
    await update.message.reply_text(f"👥 <b>دعوت دوستان</b>\n\n🔗 لینک شما:\n<code>{link}</code>\n\n🎁 دعوت‌کننده: {format_mio(int(setting('referrer_bonus','100000')))} میو\n🎁 دعوت‌شده: {format_mio(int(setting('referred_bonus','50000')))} میو\n👥 تعداد دعوت‌ها: {invited}",parse_mode="HTML")

def process_referral(user_id:int, inviter_id:Optional[int]):
    if not inviter_id or inviter_id==user_id: return False,0,0
    rb=int(setting('referrer_bonus','100000')); nb=int(setting('referred_bonus','50000'))
    with closing(db()) as conn:
        conn.execute('BEGIN IMMEDIATE')
        u=conn.execute('SELECT referral_by,referral_rewarded FROM users WHERE user_id=?',(user_id,)).fetchone()
        inv=conn.execute('SELECT user_id FROM users WHERE user_id=?',(inviter_id,)).fetchone()
        if not u or not inv or int(u['referral_rewarded']): conn.rollback(); return False,0,0
        if u['referral_by'] not in (None,inviter_id): conn.rollback(); return False,0,0
        conn.execute('UPDATE users SET referral_by=?,referral_rewarded=1 WHERE user_id=?',(inviter_id,user_id))
        conn.execute('UPDATE users SET balance=balance+?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?',(rb,inviter_id))
        conn.execute('UPDATE users SET balance=balance+?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?',(nb,user_id))
        conn.execute('INSERT INTO ledger(user_id,delta,reason,ref_id) VALUES(?,?,?,?)',(inviter_id,rb,'referral_bonus',str(user_id)))
        conn.execute('INSERT INTO ledger(user_id,delta,reason,ref_id) VALUES(?,?,?,?)',(user_id,nb,'referred_bonus',str(inviter_id)))
        conn.commit()
    return True,rb,nb


# --------------------------- Finance / Gift ---------------------------
async def deposit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context): return
    context.user_data["finance_action"] = "deposit"
    await update.message.reply_text(
        "➕ <b>واریز میو</b>\n\n"
        "مبلغ موردنظر را به صورت عدد وارد کن.\n"
        "مثال: 50000 یا 50k\n\n"
        f"💳 کارت پرداخت:\n<code>{PAYMENT_CARD}</code>\n\n"
        "بعد از انتقال، رسید/کد پیگیری را در پیام بعدی ارسال کن.",
        parse_mode="HTML"
    )

async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context): return
    context.user_data["finance_action"] = "withdraw"
    await update.message.reply_text(
        "➖ <b>برداشت میو</b>\n\n"
        "مبلغ موردنظر برای برداشت را وارد کن.\n"
        "مثال: 50000 یا 50k\n\n"
        "بعد از آن اطلاعات مقصد/شماره کارت را ارسال کن."
        , parse_mode="HTML"
    )

async def gift_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_join(update, context):
        return
    context.user_data.clear()
    context.user_data["flow"] = "gift"
    context.user_data["gift_step"] = "capacity"
    await update.message.reply_text(
        "🎁 تعداد نفرات لینک هدیه را وارد کن.\n"
        "مثال: 10\n\n"
        "برای لغو /cancel را بفرست."
    )

async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("✅ عملیات لغو شد.", reply_markup=main_keyboard(update.effective_user.id))

async def finance_and_gift_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u or not update.message:
        return
    text = (update.message.text or "").strip()

    # Admin workflow belongs to admin_text and is private-chat only.
    # Never let the finance/gift state machine react to unrelated admin messages.
    if u.id == ADMIN_ID and context.user_data.get("admin_action"):
        if update.effective_chat and update.effective_chat.type != ChatType.PRIVATE:
            return
        return

    flow = context.user_data.get("flow")
    action = context.user_data.get("finance_action")
    gift_step = context.user_data.get("gift_step")

    if flow == "gift" and gift_step == "capacity":
        try:
            capacity = int(text.replace(",", "").replace("٬", ""))
        except (TypeError, ValueError):
            capacity = 0
        if not 1 <= capacity <= 100000:
            await update.message.reply_text("❌ ظرفیت باید یک عدد بین 1 تا 100000 باشد.")
            return
        context.user_data["gift_capacity"] = capacity
        context.user_data["gift_step"] = "amount"
        await update.message.reply_text(
            "💰 مبلغ هدیه برای هر نفر را وارد کن.\n"
            "مثال: 50000 یا 50k"
        )
        return

    if flow == "gift" and gift_step == "amount":
        amount = parse_amount(text)
        capacity = int(context.user_data.get("gift_capacity", 0))
        if amount <= 0:
            await update.message.reply_text("❌ مبلغ نامعتبر است. مثال: 50000")
            return
        if capacity <= 0:
            context.user_data.clear()
            await update.message.reply_text("❌ اطلاعات لینک منقضی شد؛ دوباره «لینک هدیه» را بزن.")
            return
        total = amount * capacity
        balance = get_balance(u.id)
        if total > balance:
            await update.message.reply_text(
                f"❌ موجودی کافی نیست.\n"
                f"💰 نیاز: {format_mio(total)} میو\n"
                f"💳 موجودی: {format_mio(balance)} میو"
            )
            context.user_data.clear()
            return

        try:
            me = await context.bot.get_me()
            if not me.username: raise RuntimeError("Bot username is unavailable")
            bot_username=me.username
        except Exception:
            logger.exception("gift_link_build_failed_before_reserve user=%s",u.id)
            context.user_data.clear(); await update.message.reply_text("❌ ساخت لینک ممکن نشد؛ هیچ مبلغی از موجودی کم نشد."); return
        code=os.urandom(12).hex()
        try:
            with closing(db()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                row=conn.execute("SELECT balance FROM users WHERE user_id=?",(u.id,)).fetchone()
                if not row or int(row["balance"])<total:
                    conn.rollback(); context.user_data.clear(); await update.message.reply_text("❌ موجودی در همین لحظه کافی نیست."); return
                cur=conn.execute("UPDATE users SET balance=balance-?,updated_at=CURRENT_TIMESTAMP WHERE user_id=? AND balance>=?",(total,u.id,total))
                if cur.rowcount!=1: conn.rollback(); context.user_data.clear(); await update.message.reply_text("❌ موجودی در همین لحظه کافی نیست."); return
                conn.execute("INSERT INTO ledger(user_id,delta,reason,ref_id) VALUES(?,?,?,?)",(u.id,-total,"gift_reserve",code))
                conn.execute("INSERT INTO gift_links(code,owner_id,amount_per_user,capacity,claimed_count,remaining_balance,active) VALUES(?,?,?,?,?,?,1)",(code,u.id,amount,capacity,0,total))
                conn.commit()
        except Exception:
            logger.exception("gift_create_failed user=%s amount=%s capacity=%s total=%s db=%s",u.id,amount,capacity,total,DB_PATH)
            context.user_data.clear(); await update.message.reply_text("❌ خطا هنگام ثبت لینک هدیه بود؛ موجودی تغییر نکرد."); return
        link=f"https://t.me/{bot_username}?start=gift_{code}"

        context.user_data.clear()
        safe_link = link.replace("&", "&amp;")
        await update.message.reply_text(
            f"🎁 <b>لینک هدیه ساخته شد!</b>\n\n"
            f"👥 ظرفیت: {capacity} نفر\n"
            f"💰 هدیه هر نفر: {format_mio(amount)} میو\n"
            f"💳 مبلغ رزروشده: {format_mio(total)} میو\n\n"
            f"🔗 <a href=\"{safe_link}\">باز کردن لینک هدیه</a>\n"
            f"<code>{link}</code>\n\n"
            "هر کاربر فقط یک بار می‌تواند از این لینک استفاده کند.",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return

    if action == "deposit":
        amount = parse_amount(text)
        if amount <= 0:
            await update.message.reply_text("❌ مبلغ نامعتبر است. مثال: 50000")
            return
        context.user_data["deposit_amount"] = amount
        context.user_data["finance_action"] = "deposit_receipt"
        await update.message.reply_text(
            f"💳 مبلغ: {format_mio(amount)} میو\n"
            f"شماره کارت: <code>{PAYMENT_CARD}</code>\n\n"
            "بعد از انتقال، متن رسید یا کد پیگیری را ارسال کن.",
            parse_mode="HTML"
        )
        return

    if action == "deposit_receipt":
        amount = int(context.user_data.get("deposit_amount", 0))
        if amount <= 0:
            context.user_data.clear()
            await update.message.reply_text("❌ درخواست واریز منقضی شد؛ دوباره واریز را بزن.")
            return
        tx = os.urandom(8).hex()
        try:
            with closing(db()) as conn:
                conn.execute(
                    "INSERT INTO transactions(tx_id,user_id,kind,amount,status,receipt,card) VALUES(?,?,?,?,?,?,?)",
                    (tx, u.id, "deposit", amount, "pending", text, PAYMENT_CARD)
                )
            context.user_data.clear()
            await update.message.reply_text("✅ درخواست واریز ثبت شد و برای مالک ارسال شد.")
            name = f"@{u.username}" if u.username else u.first_name
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ تأیید", callback_data=f"fin:approve:{tx}"),
                InlineKeyboardButton("❌ رد", callback_data=f"fin:reject:{tx}")
            ]])
            await context.bot.send_message(
                ADMIN_ID,
                f"💳 <b>درخواست واریز</b>\n\n🆔 {u.id}\n👤 {name}\n💰 {format_mio(amount)} میو\n🧾 رسید: {text}\n🔖 {tx}",
                parse_mode="HTML", reply_markup=kb
            )
        except Exception:
            logger.exception("deposit_request_failed user=%s", u.id)
            context.user_data.clear()
            await update.message.reply_text("❌ ثبت درخواست واریز ناموفق بود. دوباره تلاش کن.")
        return

    if action == "withdraw":
        amount = parse_amount(text)
        if amount <= 0:
            await update.message.reply_text("❌ مبلغ نامعتبر است. مثال: 50000")
            return
        if amount > get_balance(u.id):
            await update.message.reply_text(f"❌ موجودی کافی نیست: {format_mio(get_balance(u.id))} میو")
            context.user_data.clear()
            return
        try:
            atomic_balance(u.id, -amount, "withdraw_reserve")
        except ValueError:
            await update.message.reply_text("❌ موجودی کافی نیست.")
            context.user_data.clear()
            return
        context.user_data["withdraw_amount"] = amount
        context.user_data["finance_action"] = "withdraw_card"
        await update.message.reply_text("💳 شماره کارت مقصد را ارسال کن.")
        return

    if action == "withdraw_card":
        amount = int(context.user_data.get("withdraw_amount", 0))
        if amount <= 0:
            context.user_data.clear()
            await update.message.reply_text("❌ درخواست برداشت منقضی شد؛ دوباره برداشت را بزن.")
            return
        card = text
        if len(re.sub(r"\D", "", card)) < 10:
            await update.message.reply_text("❌ شماره کارت نامعتبر است؛ شماره کارت را کامل ارسال کن.")
            return
        tx = os.urandom(8).hex()
        try:
            with closing(db()) as conn:
                conn.execute(
                    "INSERT INTO transactions(tx_id,user_id,kind,amount,status,receipt,card) VALUES(?,?,?,?,?,?,?)",
                    (tx, u.id, "withdraw", amount, "pending", "", card)
                )
            context.user_data.clear()
            await update.message.reply_text("✅ درخواست برداشت ثبت شد و برای مالک ارسال شد.")
            name = f"@{u.username}" if u.username else u.first_name
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ تأیید", callback_data=f"fin:approve:{tx}"),
                InlineKeyboardButton("❌ رد", callback_data=f"fin:reject:{tx}")
            ]])
            await context.bot.send_message(
                ADMIN_ID,
                f"💸 <b>درخواست برداشت</b>\n\n🆔 {u.id}\n👤 {name}\n💰 {format_mio(amount)} میو\n💳 کارت مقصد: <code>{card}</code>\n🔖 {tx}",
                parse_mode="HTML", reply_markup=kb
            )
        except Exception:
            logger.exception("withdraw_request_failed user=%s", u.id)
            # The amount was reserved; return it if request creation failed.
            try:
                atomic_balance(u.id, amount, "withdraw_request_refund", tx)
            except Exception:
                logger.exception("withdraw_request_refund_failed user=%s", u.id)
            context.user_data.clear()
            await update.message.reply_text("❌ ثبت درخواست برداشت ناموفق بود؛ مبلغ رزروشده برگشت داده شد.")
        return

async def gift_claim(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
    u = update.effective_user
    ensure_user(u)
    with closing(db()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        gift = conn.execute("SELECT * FROM gift_links WHERE code=? AND active=1", (code,)).fetchone()
        if not gift or int(gift["claimed_count"]) >= int(gift["capacity"]):
            conn.rollback()
            await update.message.reply_text("❌ این لینک هدیه تمام شده یا نامعتبر است.")
            return
        if int(gift["owner_id"]) == u.id:
            conn.rollback()
            await update.message.reply_text("❌ سازنده لینک نمی‌تواند هدیه خودش را دریافت کند.")
            return
        exists = conn.execute("SELECT 1 FROM gift_claims WHERE code=? AND user_id=?", (code,u.id)).fetchone()
        if exists:
            conn.rollback()
            await update.message.reply_text("❌ تو قبلاً از این لینک هدیه استفاده کرده‌ای.")
            return
        amount=int(gift["amount_per_user"]); capacity=int(gift["capacity"]); claimed=int(gift["claimed_count"]); remaining=int(gift["remaining_balance"])
        if amount<=0 or capacity<=0 or claimed>=capacity or remaining<amount:
            conn.rollback(); await update.message.reply_text("❌ این لینک هدیه وضعیت معتبری ندارد."); return
        conn.execute("INSERT INTO gift_claims(code,user_id,amount) VALUES(?,?,?)",(code,u.id,amount))
        new_count=claimed+1; new_remaining=remaining-amount; active=0 if new_count>=capacity else 1
        cur=conn.execute("UPDATE gift_links SET claimed_count=?,remaining_balance=?,active=? WHERE code=? AND active=1 AND claimed_count=? AND remaining_balance>=?",(new_count,new_remaining,active,code,claimed,amount))
        if cur.rowcount!=1:
            conn.rollback(); await update.message.reply_text("❌ وضعیت لینک تغییر کرده؛ دوباره تلاش کن."); return
        conn.execute("UPDATE users SET balance=balance+?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",(amount,u.id))
        conn.execute("INSERT INTO ledger(user_id,delta,reason,ref_id) VALUES(?,?,?,?)", (u.id,amount,"gift_claim",code))
        conn.commit()
    await update.message.reply_text(
        f"🎁 <b>هدیه دریافت شد!</b>\n\n💰 +{format_mio(amount)} میو\n💳 موجودی: {format_mio(get_balance(u.id))} میو",
        parse_mode="HTML"
    )

async def finance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        await q.answer("دسترسی ندارید", show_alert=True)
        return
    _, action, tx = q.data.split(":", 2)
    with closing(db()) as conn:
        row = conn.execute("SELECT * FROM transactions WHERE tx_id=?", (tx,)).fetchone()
        if not row or row["status"] != "pending":
            await q.answer("این درخواست قبلاً بررسی شده.", show_alert=True)
            return
        uid, amount, kind = int(row["user_id"]), int(row["amount"]), row["kind"]
        conn.execute("BEGIN IMMEDIATE")
        if action == "approve":
            conn.execute("UPDATE transactions SET status='approved',admin_id=?,updated_at=CURRENT_TIMESTAMP WHERE tx_id=?", (ADMIN_ID,tx))
            if kind == "deposit":
                conn.execute("UPDATE users SET balance=balance+?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (amount,uid))
                conn.execute("INSERT INTO ledger(user_id,delta,reason,ref_id) VALUES(?,?,?,?)", (uid,amount,"deposit_approved",tx))
            conn.commit()
            msg = "تأیید شد"
        else:
            conn.execute("UPDATE transactions SET status='rejected',admin_id=?,updated_at=CURRENT_TIMESTAMP WHERE tx_id=?", (ADMIN_ID,tx))
            if kind == "withdraw":
                conn.execute("UPDATE users SET balance=balance+?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (amount,uid))
                conn.execute("INSERT INTO ledger(user_id,delta,reason,ref_id) VALUES(?,?,?,?)", (uid,amount,"withdraw_rejected_refund",tx))
            conn.commit()
            msg = "رد شد"
    await q.answer(msg)
    await q.edit_message_reply_markup(reply_markup=None)
    try:
        await context.bot.send_message(uid, f"📋 درخواست {('واریز' if kind=='deposit' else 'برداشت')} شما {msg}.")
    except TelegramError:
        pass

# --------------------------- Dart ---------------------------
async def start_dart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in (ChatType.GROUP,ChatType.SUPERGROUP): return
    remember_group(update)
    if not await require_join(update,context): return
    m=re.match(r"^#(سفید|قرمز)\s+(.+)$",(update.message.text or '').strip())
    if not m: return
    u=update.effective_user; ensure_user(u); target=m.group(1); amount=parse_amount(m.group(2))
    if amount<MIN_GAME or amount>MAX_GAME:
        await update.message.reply_text(f"❌ مبلغ باید بین {format_mio(MIN_GAME)} و {format_mio(MAX_GAME)} باشد."); return
    if amount>get_balance(u.id):
        await update.message.reply_text(f"❌ موجودی کافی نیست. {format_mio(get_balance(u.id))} میو"); return
    with closing(db()) as conn:
        if conn.execute("SELECT 1 FROM dart_bets WHERE user_id=?",(u.id,)).fetchone() or conn.execute("SELECT 1 FROM dice_bets WHERE user_id=?",(u.id,)).fetchone() or conn.execute("SELECT 1 FROM poop_games WHERE user_id=?",(u.id,)).fetchone():
            await update.message.reply_text("⚠️ یک بازی فعال داری."); return
    try: atomic_balance(u.id,-amount,'dart_bet')
    except ValueError: return
    with closing(db()) as conn: conn.execute("INSERT INTO dart_bets(user_id,target,amount,chat_id,created_at) VALUES(?,?,?,?,?)",(u.id,target,amount,update.effective_chat.id,utc_ts()))
    await update.message.reply_text(f"🎯 <b>شرط دارت ثبت شد</b>\n🎯 هدف: {target}\n💰 مبلغ: {format_mio(amount)} میو\n\nیک دارت 🎯 همین‌جا در گروه بفرست.",parse_mode='HTML')

async def handle_dart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.dice or update.message.dice.emoji!='🎯': return
    if update.effective_chat.type not in (ChatType.GROUP,ChatType.SUPERGROUP): return
    u=update.effective_user
    with closing(db()) as conn: bet=conn.execute("SELECT * FROM dart_bets WHERE user_id=?",(u.id,)).fetchone()
    if not bet or int(bet['chat_id'])!=int(update.effective_chat.id): return
    value=int(update.message.dice.value); white={int(x) for x in setting('dart_white_values','1,3,5').split(',') if x.strip().isdigit()}
    color='سفید' if value in white else 'قرمز'; won=color==bet['target']; mult=float(setting('dart_multiplier','2.0')); prize=int(bet['amount']*mult) if won else 0
    with closing(db()) as conn:
        conn.execute('BEGIN IMMEDIATE'); conn.execute('DELETE FROM dart_bets WHERE user_id=?',(u.id,))
        if won:
            conn.execute('UPDATE users SET balance=balance+?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?',(prize,u.id)); conn.execute('INSERT INTO ledger(user_id,delta,reason) VALUES(?,?,?)',(u.id,prize,'dart_win'))
        conn.commit()
    log_game(u.id,'dart',bet['amount'],'win' if won else 'loss',prize)
    if won: await update.message.reply_text(f"🎯🎉 بردی! نتیجه: {color}\n💰 جایزه: {format_mio(prize)} میو",reply_to_message_id=update.message.message_id)
    else: await update.message.reply_text(f"🎯💥 باختی! نتیجه: {color}\n💰 {format_mio(bet['amount'])} میو از دست رفت.",reply_to_message_id=update.message.message_id)


# --------------------------- Dice ---------------------------
async def start_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP): return
    if not await require_join(update, context): return
    m=re.match(r"^#(زوج|فرد)\s+(.+)$",(update.message.text or "").strip())
    if not m: return
    u=update.effective_user; ensure_user(u)
    amount=parse_amount(m.group(2)); target=m.group(1)
    if amount<MIN_GAME:
        await update.message.reply_text(f"❌ حداقل بازی {format_mio(MIN_GAME)} میو است."); return
    if amount>MAX_GAME:
        await update.message.reply_text(f"❌ حداکثر هر بازی {format_mio(MAX_GAME)} میو است."); return
    if amount>get_balance(u.id):
        await update.message.reply_text(f"❌ موجودی کافی نیست. موجودی: {format_mio(get_balance(u.id))} میو"); return
    with closing(db()) as conn:
        if conn.execute("SELECT 1 FROM dice_bets WHERE user_id=?",(u.id,)).fetchone() or conn.execute("SELECT 1 FROM poop_games WHERE user_id=?",(u.id,)).fetchone():
            await update.message.reply_text("⚠️ یک بازی فعال داری؛ اول همان را تمام کن."); return
    try: atomic_balance(u.id,-amount,"dice_bet")
    except ValueError: return
    with closing(db()) as conn:
        conn.execute("INSERT INTO dice_bets(user_id,target,amount,dices,chat_id,created_at) VALUES(?,?,?,?,?,?)",(u.id,target,amount, "[]", update.effective_chat.id, utc_ts()))
    name=f"@{u.username}" if u.username else u.first_name
    msg=await update.message.reply_text(f"🎲 <b>بازی تاس شروع شد</b>\n\n👤 کاربر {name}\n🎯 شرط: {target}\n💰 مبلغ: {format_mio(amount)} میو\n\n🎲 دقیقاً ۳ تاس واقعی تلگرام بفرست.\n🚫 تاس فورواردشده حساب نمی‌شود.\n⏱️ ۶۰ ثانیه فرصت داری؛ بعد از آن ۵۰٪ مبلغ جریمه می‌شود.",parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو شرط",callback_data=f"cancel_dice:{u.id}")]]))
    with closing(db()) as conn: conn.execute("UPDATE dice_bets SET message_id=? WHERE user_id=?",(msg.message_id,u.id))
    asyncio.create_task(dice_timeout(u.id,context.bot))


async def dice_timeout(user_id:int,bot):
    await asyncio.sleep(DICE_TIMEOUT)
    with closing(db()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        bet=conn.execute("SELECT * FROM dice_bets WHERE user_id=?",(user_id,)).fetchone()
        if not bet: conn.rollback(); return
        refund=bet["amount"]-int(bet["amount"]*DICE_PENALTY)
        conn.execute("DELETE FROM dice_bets WHERE user_id=?",(user_id,))
        conn.execute("UPDATE users SET balance=balance+?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",(refund,user_id))
        conn.execute("INSERT INTO ledger(user_id,delta,reason) VALUES(?,?,?)",(user_id,refund,"dice_timeout_refund"))
        conn.commit()
    log_game(user_id,"dice",bet["amount"],"timeout",refund)
    try: await bot.send_message(bet["chat_id"],f"⚠️ زمان تاس تمام شد.\n💥 جریمه: {format_mio(bet['amount']-refund)} میو\n↩️ برگشت: {format_mio(refund)} میو\n💰 موجودی: {format_mio(get_balance(user_id))} میو")
    except TelegramError: pass


async def handle_dice_or_dart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dispatch Telegram dice messages without relying on filters.Dice.DART,
    which is unavailable in some python-telegram-bot versions."""
    if not update.message or not update.message.dice:
        return
    if update.message.dice.emoji == "🎯":
        await handle_dart(update, context)
    elif update.message.dice.emoji == "🎲":
        await handle_dice(update, context)
    elif update.message.dice.emoji == "⚽":
        await handle_football(update, context)


async def handle_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.dice or update.message.dice.emoji != "🎲":
        return
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    u = update.effective_user
    if not u:
        return

    with closing(db()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        bet = conn.execute("SELECT * FROM dice_bets WHERE user_id=?", (u.id,)).fetchone()
        if not bet:
            conn.rollback(); return
        if int(bet["chat_id"]) != int(update.effective_chat.id):
            conn.rollback(); return
        if getattr(update.message, "forward_origin", None) is not None or getattr(update.message, "forward_date", None) is not None:
            conn.rollback()
            await update.message.reply_text(f"⚠️ @{u.username or u.first_name} این تاس فوروارد شده است و ثبت نمی‌شود.", reply_to_message_id=update.message.message_id)
            return
        dices = json.loads(bet["dices"])
        if len(dices) >= 3:
            conn.rollback(); return
        dices.append(int(update.message.dice.value))
        conn.execute("UPDATE dice_bets SET dices=? WHERE user_id=?", (json.dumps(dices), u.id))
        if len(dices) < 3:
            conn.commit()
            await update.message.reply_text(f"🎲 {len(dices)} از ۳ تاس ثبت شد؛ {3-len(dices)} تاس دیگر بفرست.", reply_to_message_id=update.message.message_id)
            return
        total=sum(dices); even=total%2==0
        won=(bet["target"]=="زوج" and even) or (bet["target"]=="فرد" and not even)
        mult=float(setting("dice_mult","1.5")); prize=int(bet["amount"]*mult) if won else 0
        conn.execute("DELETE FROM dice_bets WHERE user_id=?", (u.id,))
        if won:
            conn.execute("UPDATE users SET balance=balance+?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (prize,u.id))
            conn.execute("INSERT INTO ledger(user_id,delta,reason) VALUES(?,?,?)", (u.id,prize,"dice_win"))
        conn.commit()
    log_game(u.id,"dice",bet["amount"],"win" if won else "loss",prize)
    outcome="زوج" if even else "فرد"; dice_text=" + ".join(map(str,dices))
    if won:
        text=(f"🎉 <b>بردیییی!</b>\n\n👤 @{u.username or u.first_name}\n🎲 {dice_text} = {total}\n📌 نتیجه: {outcome}\n🎯 شرط: {bet['target']}\n🪙 جایزه (×{mult:g}): {format_mio(prize)} میو\n💰 موجودی: {format_mio(get_balance(u.id))} میو")
    else:
        text=(f"💥 <b>باختیییی!</b>\n\n👤 @{u.username or u.first_name}\n🎲 {dice_text} = {total}\n📌 نتیجه: {outcome}\n🎯 شرط: {bet['target']}\n💰 مبلغ شرط: {format_mio(bet['amount'])} میو از دست رفت.\n💰 موجودی: {format_mio(get_balance(u.id))} میو")
    await update.message.reply_text(text,parse_mode="HTML",reply_to_message_id=update.message.message_id)


async def cancel_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; uid=q.from_user.id
    with closing(db()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        bet=conn.execute("SELECT * FROM dice_bets WHERE user_id=?",(uid,)).fetchone()
        if not bet or json.loads(bet["dices"]): conn.rollback(); await q.answer("بعد از اولین تاس لغو ممکن نیست.",show_alert=True); return
        conn.execute("DELETE FROM dice_bets WHERE user_id=?",(uid,))
        conn.execute("UPDATE users SET balance=balance+?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",(bet["amount"],uid))
        conn.execute("INSERT INTO ledger(user_id,delta,reason) VALUES(?,?,?)",(uid,bet["amount"],"dice_cancel")); conn.commit()
    await q.answer("لغو شد")
    await q.edit_message_text(f"❌ شرط لغو شد.\n💰 {format_mio(bet['amount'])} میو برگشت.\n💰 موجودی: {format_mio(get_balance(uid))} میو")


# --------------------------- Football ---------------------------
def football_config():
    raw = setting("football_goal_values", "4,5")
    try:
        goals = sorted({int(x.strip()) for x in raw.split(",") if x.strip()})
    except ValueError:
        goals = [4, 5]
    goals = [x for x in goals if 1 <= x <= 5] or [4, 5]
    try:
        shots = int(setting("football_shots", "3"))
    except ValueError:
        shots = 3
    return shots if 1 <= shots <= 10 else 3, goals


def load_football(uid):
    with closing(db()) as conn:
        r = conn.execute("SELECT * FROM football_games WHERE user_id=?", (uid,)).fetchone()
    if not r:
        return None
    return dict(r)


def save_football(uid, game):
    with closing(db()) as conn:
        conn.execute("""INSERT INTO football_games(user_id,chat_id,message_id,shots,goals,created_at)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET chat_id=excluded.chat_id,message_id=excluded.message_id,
            shots=excluded.shots,goals=excluded.goals,created_at=excluded.created_at""",
            (uid, game["chat_id"], game.get("message_id"), game["shots"], game["goals"], utc_ts()))


async def start_football(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if not await require_join(update, context):
        return
    if not re.fullmatch(r"#فوتبال(?:\u200c)?", (update.message.text or "").strip()):
        return
    u = update.effective_user
    if not u:
        return
    ensure_user(u)
    if load_football(u.id):
        await update.message.reply_text("⚠️ یک بازی فوتبال فعال داری؛ اول شوت‌های باقی‌مانده را بفرست.", reply_to_message_id=update.message.message_id)
        return
    shots, goal_values = football_config()
    save_football(u.id, {"chat_id": update.effective_chat.id, "message_id": update.message.message_id, "shots": 0, "goals": 0})
    await update.message.reply_text(
        f"⚽ <b>بازی فوتبال شروع شد!</b>\n\n🎯 تعداد شوت: {shots}\n"
        "⚽ هر بار یک توپ فوتبال بفرست.\n"
        f"🥅 اعداد گل تنظیم‌شده: {', '.join(map(str, goal_values))}",
        parse_mode="HTML", reply_to_message_id=update.message.message_id
    )


async def handle_football(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.dice or update.message.dice.emoji != "⚽":
        return
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    u = update.effective_user
    if not u:
        return
    game = load_football(u.id)
    if not game or int(game["chat_id"]) != int(update.effective_chat.id):
        return
    max_shots, goal_values = football_config()
    shots = int(game["shots"]) + 1
    goals = int(game["goals"]) + (1 if int(update.message.dice.value) in goal_values else 0)
    if shots >= max_shots:
        with closing(db()) as conn:
            conn.execute("DELETE FROM football_games WHERE user_id=?", (u.id,))
        outcome = "🥅 گل!" if int(update.message.dice.value) in goal_values else "🧤 مهار شد!"
        await update.message.reply_text(
            f"⚽ <b>بازی تمام شد</b>\n\n{outcome}\n"
            f"🎯 شوت: {shots}/{max_shots}\n"
            f"🥅 گل‌های ثبت‌شده: {goals}",
            parse_mode="HTML", reply_to_message_id=update.message.message_id
        )
        return
    save_football(u.id, {**game, "shots": shots, "goals": goals})
    outcome = "🥅 گل!" if int(update.message.dice.value) in goal_values else "🧤 مهار شد!"
    await update.message.reply_text(
        f"⚽ {outcome}\n🎯 شوت {shots}/{max_shots}\n🥅 گل‌ها: {goals}",
        reply_to_message_id=update.message.message_id
    )


# --------------------------- Poop ---------------------------
def poop_config():
    try: rows=max(1,int(setting("poop_rows",str(POOP_ROWS))))
    except (TypeError,ValueError): rows=POOP_ROWS
    try: cols=max(1,int(setting("poop_cols",str(POOP_COLS))))
    except (TypeError,ValueError): cols=POOP_COLS
    try: raw_counts=[int(x.strip()) for x in setting("poop_counts",",".join(map(str,POOP_COUNTS))).split(",") if x.strip()]
    except (TypeError,ValueError): raw_counts=list(POOP_COUNTS)
    try: raw_mults=[float(x.strip()) for x in setting("poop_mults",",".join(map(str,POOP_MULTIPLIERS))).split(",") if x.strip()]
    except (TypeError,ValueError): raw_mults=list(POOP_MULTIPLIERS)
    counts = (raw_counts + [0] * rows)[:rows]
    counts = [min(max(0, n), cols) for n in counts]
    mults = (raw_mults + [raw_mults[-1] if raw_mults else 1.0] * rows)[:rows]
    return rows, cols, counts, mults

def make_poops():
    rows, cols, counts, mults = poop_config()
    return [sorted(random.sample(range(cols), n)) for n in counts]


def load_poop(uid):
    with closing(db()) as conn: r=conn.execute("SELECT * FROM poop_games WHERE user_id=?",(uid,)).fetchone()
    if not r: return None
    return {"amount":r["amount"],"step":r["step"],"poops":json.loads(r["poops"]),"history":json.loads(r["history"]),"chat_id":r["chat_id"],"message_id":r["message_id"],"config":json.loads(r["config"] or "{}")}


def save_poop(uid,game):
    with closing(db()) as conn:
        conn.execute("""INSERT INTO poop_games(user_id,amount,step,poops,history,chat_id,message_id,config,created_at) VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET amount=excluded.amount,step=excluded.step,poops=excluded.poops,history=excluded.history,chat_id=excluded.chat_id,message_id=excluded.message_id,config=excluded.config""",
                     (uid,game["amount"],game["step"],json.dumps(game["poops"]),json.dumps(game["history"]),game["chat_id"],game.get("message_id"),json.dumps(game.get("config",{})),utc_ts()))


def poop_keyboard(game):
    step=game["step"]; history=game["history"]; buttons=[]
    cfg=game.get("config") or {}
    try: rows,cols,counts,mults=int(cfg["rows"]),int(cfg["cols"]),cfg["counts"],cfg["mults"]
    except (KeyError,TypeError,ValueError): rows,cols,counts,mults=poop_config()
    for row in range(rows):
        rb=[]
        for col in range(cols):
            if row<step: rb.append(InlineKeyboardButton(history[row][col],callback_data="poop_noop"))
            elif row==step: rb.append(InlineKeyboardButton("⚪️",callback_data=f"poop_play:{row}:{col}"))
            else: rb.append(InlineKeyboardButton("🔒",callback_data="poop_noop"))
        buttons.append(rb)
    if step>0: buttons.append([InlineKeyboardButton(f"💰 برداشت {format_mio(int(game['amount']*poop_config()[3][step-1]))} میو",callback_data="poop_cashout")])
    return InlineKeyboardMarkup(buttons)


async def start_poop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if not await require_join(update, context):
        return
    m = re.match(r"^#پوپ(?:\u200c)?\s+(.+?)\s*$", (update.message.text or "").strip())
    if not m:
        return
    u = update.effective_user
    ensure_user(u)
    if load_poop(u.id):
        await update.message.reply_text("⚠️ یک بازی پوپ فعال داری.")
        return
    amount = parse_amount(m.group(1))
    if amount < MIN_GAME:
        await update.message.reply_text(f"❌ حداقل بازی {format_mio(MIN_GAME)} میو است.")
        return
    if amount > MAX_GAME:
        await update.message.reply_text(f"❌ حداکثر هر بازی {format_mio(MAX_GAME)} میو است.")
        return
    if amount > get_balance(u.id):
        await update.message.reply_text(f"❌ موجودی کافی نیست. موجودی: {format_mio(get_balance(u.id))} میو")
        return
    with closing(db()) as conn:
        if conn.execute("SELECT 1 FROM dice_bets WHERE user_id=?", (u.id,)).fetchone():
            await update.message.reply_text("⚠️ یک بازی تاس فعال داری.")
            return

    context.user_data["poop_pending_amount"] = amount
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ شروع بازی", callback_data="poop_confirm_start"),
            InlineKeyboardButton("❌ لغو", callback_data="poop_confirm_cancel"),
        ]
    ])
    await update.message.reply_text(
        "💩 <b>تأیید شروع بازی پوپ</b>\n\n"
        f"🪙 مبلغ: {format_mio(amount)} میو\n"
        f"🎯 {poop_config()[0]} ردیف و {poop_config()[1]} خانه\n"
        f"💩 تعداد پوپ‌ها: {' / '.join(map(str, poop_config()[2]))}\n"
        f"📈 ضرایب: {' / '.join('×'+str(x) for x in poop_config()[3])}\n\n"
        "مطمئن هستی می‌خواهی بازی را شروع کنی؟",
        parse_mode="HTML",
        reply_markup=kb,
    )

async def poop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; uid=q.from_user.id; data=q.data
    if data=="poop_noop":
        await q.answer()
        return
    if data=="poop_confirm_cancel":
        context.user_data.pop("poop_pending_amount", None)
        await q.answer("لغو شد")
        await q.edit_message_text("❌ شروع بازی لغو شد.")
        return
    if data=="poop_confirm_start":
        amount = int(context.user_data.get("poop_pending_amount", 0))
        if amount <= 0:
            await q.answer("درخواست شروع منقضی شده؛ دوباره #پوپ را بزن.", show_alert=True)
            return
        if load_poop(uid):
            await q.answer("یک بازی پوپ فعال داری.", show_alert=True)
            return
        if amount > get_balance(uid):
            await q.answer("موجودی کافی نیست.", show_alert=True)
            return
        try:
            atomic_balance(uid, -amount, "poop_bet")
        except ValueError:
            await q.answer("موجودی کافی نیست.", show_alert=True)
            return
        game = {
            "amount": amount,
            "step": 0,
            "poops": make_poops(),
            "history": [["⚪️"] * poop_config()[1] for _ in range(poop_config()[0])],
            "chat_id": q.message.chat_id,
            "message_id": q.message.message_id,
        }
        save_poop(uid, game)
        context.user_data.pop("poop_pending_amount", None)
        await q.answer("بازی شروع شد!")
        rows, cols, counts, poop_mults = poop_config()
        board = "\n".join(
            ("⚪️" * cols) if r == 0 else ("🔒" * cols)
            for r in range(rows)
        )
        first_mult = poop_mults[0] if poop_mults else 1.0
        await q.edit_message_text(
            "💩 <b>بازی پوپ</b>\n\n"
            f"{board}\n\n"
            f"🎮 مرحله ۱ از {rows}\n"
            f"📈 ضریب: ×{first_mult:g}\n"
            f"🪙 شرط: {format_mio(amount)} میو",
            parse_mode="HTML",
            reply_markup=poop_keyboard(game),
        )
        return
    game=load_poop(uid)
    if not game:
        await q.answer("بازی فعالی پیدا نشد.",show_alert=True); return
    if int(game["chat_id"]) != int(q.message.chat_id):
        await q.answer("این بازی مربوط به گروه دیگری است.", show_alert=True); return
    if not await require_join(update,context): return
    if data=="poop_cashout":
        if game["step"]<=0: await q.answer("هنوز مرحله‌ای رد نشده.",show_alert=True); return
        _, _, _, poop_mults = poop_config()
        prize=int(game["amount"]*poop_mults[game["step"]-1])
        with closing(db()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM poop_games WHERE user_id=?",(uid,))
            conn.execute("UPDATE users SET balance=balance+?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",(prize,uid))
            conn.execute("INSERT INTO ledger(user_id,delta,reason) VALUES(?,?,?)",(uid,prize,"poop_cashout")); conn.commit()
        log_game(uid,"poop",game["amount"],"cashout",prize)
        await q.answer("برداشت شد")
        await q.edit_message_text(f"💰 <b>برداشت موفق</b>\n\n🎮 مرحله {game['step']} از {poop_config()[0]}\n💰 دریافتی: {format_mio(prize)} میو\n💰 موجودی: {format_mio(get_balance(uid))} میو",parse_mode="HTML"); return
    if data.startswith("poop_play:"):
        _,rs,cs=data.split(":"); row,col=int(rs),int(cs)
        if row!=game["step"]: await q.answer("این ردیف باز نیست.",show_alert=True); return
        safe=col not in game["poops"][row]
        rows, cols, counts, poop_mults = poop_config()
        for c in range(cols):
            game["history"][row][c] = "💩" if c in game["poops"][row] else "🟢"
        if not safe:
            with closing(db()) as conn: conn.execute("DELETE FROM poop_games WHERE user_id=?",(uid,))
            log_game(uid,"poop",game["amount"],"loss",0)
            await q.answer("💩 پوپ بود!")
            await q.edit_message_text("💥 <b>متأسفانه باختی 🤦‍♂️</b> 💩\n\nگوهی شدی 💩\n\n"+"".join(game["history"][row])+f"\n\n🪙 مبلغ شرط: {format_mio(game['amount'])} میو از دست رفت.",parse_mode="HTML"); return
        game["step"]+=1
        rows, cols, counts, poop_mults = poop_config()
        if game["step"]==rows:
            prize=int(game["amount"]*poop_mults[-1])
            with closing(db()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM poop_games WHERE user_id=?",(uid,))
                conn.execute("UPDATE users SET balance=balance+?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",(prize,uid))
                conn.execute("INSERT INTO ledger(user_id,delta,reason) VALUES(?,?,?)",(uid,prize,"poop_win")); conn.commit()
            log_game(uid,"poop",game["amount"],"win",prize)
            await q.answer("🏆 کامل شد!")
            await q.edit_message_text(
                f"🏆 <b>{rows} مرحله رو کامل کردی!</b>\n\n"
                f"💰 جایزه نهایی: {format_mio(prize)} میو\n"
                f"💰 موجودی: {format_mio(get_balance(uid))} میو",
                parse_mode="HTML",
            )
            return
        save_poop(uid,game)
        _, _, _, poop_mults = poop_config()
        current=int(game["amount"]*poop_mults[game["step"]-1])
        next_mult=poop_mults[game["step"]]
        await q.answer("🟢 امن! ردیف بعد باز شد.")
        board_parts = ["".join(r) for r in game["history"][:game["step"]]]
        board_parts.append("⚪️" * cols)
        board_parts.extend("🔒" * cols for _ in range(rows - game["step"] - 1))
        board = "\n".join(board_parts)
        await q.edit_message_text(
            "💩 <b>پوپ</b>\n\n"
            f"{board}\n\n"
            f"🎮 مرحله {game['step']+1} از {rows}\n"
            f"📈 ضریب بعدی: ×{next_mult:g}\n"
            f"💰 برداشت فعلی: {format_mio(current)} میو",
            parse_mode="HTML",
            reply_markup=poop_keyboard(game),
        )

# --------------------------- Group Quiz ---------------------------
QUIZ_BANK = [
    ("ریاضی: 12 + 18 چند می‌شود؟", "30"),
    ("ریاضی: 9 × 7 چند می‌شود؟", "63"),
    ("ریاضی: 100 ÷ 4 چند می‌شود؟", "25"),
    ("ریاضی: 15 درصد 200 چند است؟", "30"),
    ("ریاضی: 48 ÷ 6 + 4 چند می‌شود؟", "12"),
    ("ریاضی: 17 + 25 چند می‌شود؟", "42"),
    ("ریاضی: 8 × 8 - 12 چند می‌شود؟", "52"),
    ("ریاضی: 150 ÷ 5 چند می‌شود؟", "30"),
    ("ریاضی: 7 × 9 + 3 چند می‌شود؟", "66"),
    ("پایتخت ایران چیست؟", "تهران"),
    ("بزرگ‌ترین سیاره منظومه شمسی چیست؟", "مشتری"),
    ("آب در فشار معمولی چند درجه می‌جوشد؟", "100"),
    ("تعداد قاره‌های زمین چند تاست؟", "7"),
    ("سریع‌ترین حیوان خشکی چیست؟", "یوزپلنگ"),
    ("ترکیب آبی و زرد چه رنگی می‌شود؟", "سبز"),
    ("بزرگ‌ترین اقیانوس جهان چیست؟", "اقیانوس آرام"),
    ("سیاره سرخ کدام است؟", "مریخ"),
    ("چند روز در یک هفته وجود دارد؟", "7"),
    ("نماد شیمیایی آب چیست؟", "H2O"),
    ("اولین ماه سال شمسی چیست؟", "فروردین"),
]
def normalize_answer(text): return re.sub(r"\s+","",(text or '').strip().lower().replace('ي','ی').replace('ك','ک'))
def remember_group(update):
    c=update.effective_chat
    if not c or c.type not in (ChatType.GROUP,ChatType.SUPERGROUP): return
    with closing(db()) as conn: conn.execute("INSERT INTO group_chats(chat_id,title,username,enabled) VALUES(?,?,?,1) ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title,username=excluded.username,enabled=1,updated_at=CURRENT_TIMESTAMP",(c.id,c.title or '',getattr(c,'username','') or ''))
async def track_group_message(update, context):
    remember_group(update)


async def send_group_quizzes(context):
    if setting('quiz_enabled','1')!='1': return
    with closing(db()) as conn: groups=conn.execute('SELECT chat_id FROM group_chats WHERE enabled=1').fetchall()
    for g in groups:
        cid=int(g['chat_id'])
        with closing(db()) as conn: active=conn.execute('SELECT 1 FROM active_questions WHERE chat_id=?',(cid,)).fetchone()
        if active: continue
        q,a=random.choice(QUIZ_BANK); qid=os.urandom(6).hex(); prize=int(setting('quiz_prize','50000'))
        with closing(db()) as conn: conn.execute('INSERT OR REPLACE INTO active_questions(chat_id,question_id,question,answer,prize,created_at) VALUES(?,?,?,?,?,?)',(cid,qid,q,a,prize,utc_ts()))
        try: await context.bot.send_message(cid,f"🧠 <b>چالش رندوم میوبت</b>\n\n❓ {q}\n\n💰 جایزه نفر اول: {format_mio(prize)} میو\n⏱️ مهلت: {setting('quiz_timeout_seconds','120')} ثانیه\n✍️ جواب را همین‌جا بفرست.",parse_mode='HTML')
        except TelegramError:
            with closing(db()) as conn: conn.execute('DELETE FROM active_questions WHERE chat_id=?',(cid,))
async def handle_group_quiz_answer(update,context):
    if not update.message or update.effective_chat.type not in (ChatType.GROUP,ChatType.SUPERGROUP): return
    remember_group(update); text=(update.message.text or '').strip()
    if not text: return
    with closing(db()) as conn: q=conn.execute('SELECT * FROM active_questions WHERE chat_id=?',(update.effective_chat.id,)).fetchone()
    if not q or utc_ts()-float(q['created_at'])>int(setting('quiz_timeout_seconds','120')): return
    if normalize_answer(text)!=normalize_answer(q['answer']): return
    u=update.effective_user; ensure_user(u)
    with closing(db()) as conn:
        conn.execute('BEGIN IMMEDIATE'); cur=conn.execute('SELECT * FROM active_questions WHERE chat_id=?',(update.effective_chat.id,)).fetchone()
        if not cur: conn.rollback(); return
        conn.execute('DELETE FROM active_questions WHERE chat_id=?',(update.effective_chat.id,)); prize=int(cur['prize'])
        conn.execute('UPDATE users SET balance=balance+?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?',(prize,u.id)); conn.execute('INSERT INTO ledger(user_id,delta,reason,ref_id) VALUES(?,?,?,?)',(u.id,prize,'group_quiz',cur['question_id'])); conn.commit()
    log_game(u.id, "quiz", 0, "win", prize)
    await update.message.reply_text(
        f"🎉 پاسخ درست بود! +{format_mio(prize)} میو",
        reply_to_message_id=update.message.message_id
    )
async def quiz_loop(context):
    while True:
        try:
            await send_group_quizzes(context)
        except Exception:
            logger.exception("quiz loop error")
        try:
            interval = max(1, int(setting("quiz_interval_minutes", "10")))
        except (TypeError, ValueError):
            interval = 10
        await asyncio.sleep(interval * 60)


# --------------------------- Join callback ---------------------------
async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if await is_joined(context.bot, q.from_user.id):
        await q.answer("عضویت تأیید شد ✅")
        u = q.from_user
        ensure_user(u)
        ref_row=get_user(u.id)
        if ref_row and ref_row['referral_by'] and not int(ref_row['referral_rewarded']):
            process_referral(u.id,int(ref_row['referral_by']))
        await q.edit_message_text(
            "╭━━━「 🎰 MEOWBET | میوبت 」━━━╮\n"
            "│ 🐾 عضویت تأیید شد! خوش اومدی\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "🎮 بازی‌ها داخل گروه انجام می‌شن.\n\n"
            f"🪙 موجودی شما: {format_mio(get_balance(u.id))} میو\n\n"
            "از منوی زیر استفاده کن 👇",
            reply_markup=main_keyboard(u.id),
        )
    else:
        await q.answer("هنوز عضو کانال نیستی. بعد از عضویت دوباره بررسی کن.", show_alert=True)


# --------------------------- Admin panel ---------------------------
def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 داشبورد", callback_data="adm:stats"),
         InlineKeyboardButton("👥 کاربران", callback_data="adm:users:0")],
        [InlineKeyboardButton("🎮 آمار بازی", callback_data="adm:gamestats"),
         InlineKeyboardButton("⚙️ تنظیمات بازی", callback_data="adm:gamesettings")],
        [InlineKeyboardButton("🎁 تنظیمات پاداش", callback_data="adm:rewards"),
         InlineKeyboardButton("🎁 تنظیم جوایز لیدربورد", callback_data="adm:leaderboard_rewards")],
        [InlineKeyboardButton("🧠 تنظیمات چالش", callback_data="adm:quizsettings")],
        [InlineKeyboardButton("📈 گزارش مالی", callback_data="adm:finance"),
         InlineKeyboardButton("💳 درخواست‌های مالی", callback_data="adm:pending_finance")],
        [InlineKeyboardButton("➕➖ مدیریت میو", callback_data="adm:balance"),
         InlineKeyboardButton("🔎 جستجوی کاربر", callback_data="adm:search")],
        [InlineKeyboardButton("📢 عضویت‌های اجباری", callback_data="adm:channels"),
         InlineKeyboardButton("📣 پیام همگانی", callback_data="adm:broadcast")],
    ])


def back_admin(): return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ برگشت",callback_data="adm:home")]])


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:return
    if update.effective_chat.type!=ChatType.PRIVATE:
        await update.message.reply_text("🔐 پنل مدیریت فقط در پیوی ادمین باز می‌شود."); return
    context.user_data.clear(); await update.message.reply_text("🛠 <b>پنل مدیریت میوبت</b>",parse_mode="HTML",reply_markup=admin_menu())


async def admin_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    if q.from_user.id!=ADMIN_ID: await q.answer("دسترسی ندارید",show_alert=True); return
    d=q.data
    if d=="adm:home": await q.answer(); await q.edit_message_text("🛠 پنل مدیریت",reply_markup=admin_menu()); return
    if d=="adm:stats":
        with closing(db()) as conn:
            vals={
                "users":conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],
                "balance":conn.execute("SELECT COALESCE(SUM(balance),0) s FROM users").fetchone()["s"],
                "games":conn.execute("SELECT COUNT(*) c FROM game_stats").fetchone()["c"],
                "wagered":conn.execute("SELECT COALESCE(SUM(amount),0) s FROM game_stats").fetchone()["s"],
                "payout":conn.execute("SELECT COALESCE(SUM(payout),0) s FROM game_stats").fetchone()["s"],
            }
        txt=(f"📊 <b>داشبورد</b>\n\n👥 کاربران: {vals['users']}\n💰 مجموع موجودی: {format_mio(vals['balance'])}\n"
             f"🎮 بازی ثبت‌شده: {vals['games']}\n🎯 مجموع شرط‌ها: {format_mio(vals['wagered'])}\n💸 مجموع پرداخت بازی: {format_mio(vals['payout'])}")
        await q.answer(); await q.edit_message_text(txt,parse_mode="HTML",reply_markup=back_admin()); return
    if d=="adm:gamestats":
        with closing(db()) as conn:
            rows=conn.execute("SELECT game,COUNT(*) c,SUM(amount) wager,SUM(payout) pay FROM game_stats GROUP BY game").fetchall()
        lines=["🎮 آمار بازی‌ها\n"]
        for r in rows: lines.append(f"{'🎲 تاس' if r['game']=='dice' else '💩 پوپ' if r['game']=='poop' else '🎯 دارت'}: {r['c']} بازی | شرط {format_mio(r['wager'] or 0)} | پرداخت {format_mio(r['pay'] or 0)}")
        await q.answer(); await q.edit_message_text("\n".join(lines) if len(lines)>1 else "هنوز بازی‌ای ثبت نشده.",reply_markup=back_admin()); return
    if d.startswith("adm:users:"):
        page=int(d.rsplit(":",1)[1])
        with closing(db()) as conn:
            rows=conn.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",(PAGE_SIZE,page*PAGE_SIZE)).fetchall(); total=conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        lines=[f"👥 کاربران | صفحه {page+1}\n"]
        for r in rows: lines.append(f"🆔 {r['user_id']} | @{r['username'] or '-'} | 💰 {format_mio(r['balance'])}")
        nav=[]
        if page>0:nav.append(InlineKeyboardButton("⬅️ قبلی",callback_data=f"adm:users:{page-1}"))
        if (page+1)*PAGE_SIZE<total:nav.append(InlineKeyboardButton("بعدی ➡️",callback_data=f"adm:users:{page+1}"))
        kb=[nav] if nav else []; kb.append([InlineKeyboardButton("⬅️ برگشت",callback_data="adm:home")])
        await q.answer(); await q.edit_message_text("\n".join(lines),reply_markup=InlineKeyboardMarkup(kb)); return
    if d=="adm:balance":
        context.user_data["admin_action"]="balance"; await q.answer(); await q.edit_message_text("➕➖ تغییر موجودی\n\nفرمت:\nآیدی مقدار\nمثال افزایش:\n123456789 50000\nمثال کاهش:\n123456789 -20000",reply_markup=back_admin()); return
    if d=="adm:search":
        context.user_data["admin_action"]="search"; await q.answer(); await q.edit_message_text("🔎 آیدی عددی یا username را بفرست.",reply_markup=back_admin()); return
    if d=="adm:channels":
        rows = await get_required_chats()
        lines = ["📢 <b>عضویت‌های اجباری</b>", "", "هر تعداد کانال یا گروه که لازم داری می‌توانی اضافه کنی."]
        kb = []
        for i, r in enumerate(rows, 1):
            icon = "📢" if r["chat_type"] == "channel" else "👥"
            name = r["title"] or r["username"] or r["chat_id"]
            lines.append(f"{i}. {icon} {name}")
            kb.append([InlineKeyboardButton(f"❌ حذف {i}", callback_data=f"adm:channel_del:{r['id']}")])
        if not rows:
            lines.append("— هیچ عضویت اجباری فعالی وجود ندارد.")
        kb.append([InlineKeyboardButton("➕ افزودن کانال/گروه", callback_data="adm:channel_add")])
        kb.append([InlineKeyboardButton("🗑 حذف همه", callback_data="adm:channel_clear")])
        kb.append([InlineKeyboardButton("⬅️ برگشت", callback_data="adm:home")])
        await q.answer()
        await q.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
        return

    if d=="adm:channel_add":
        context.user_data["admin_action"]="channel_add"
        await q.answer()
        await q.edit_message_text(
            "➕ <b>افزودن کانال یا گروه اجباری</b>\n\n"
            "یکی از این‌ها را ارسال کن:\n"
            "• @username\n• لینک t.me\n• آیدی عددی مثل -1001234567890\n\n"
            "ربات باید داخل کانال/گروه دسترسی لازم برای بررسی عضویت را داشته باشد.",
            parse_mode="HTML", reply_markup=back_admin()
        )
        return

    if d.startswith("adm:channel_del:"):
        cid=int(d.rsplit(":",1)[1])
        with closing(db()) as conn:
            conn.execute("DELETE FROM required_chats WHERE id=?", (cid,))
        await q.answer("حذف شد ✅")
        await q.edit_message_text("✅ مورد حذف شد.", reply_markup=admin_menu())
        return

    if d=="adm:channel_clear":
        with closing(db()) as conn:
            conn.execute("DELETE FROM required_chats")
        await q.answer("همه حذف شدند")
        await q.edit_message_text("🗑 همه عضویت‌های اجباری حذف شدند.", reply_markup=admin_menu())
        return

    if d=="adm:finance":
        with closing(db()) as conn:
            dep=conn.execute("SELECT COALESCE(SUM(amount),0) v FROM transactions WHERE kind='deposit' AND status='approved'").fetchone()["v"]
            wd=conn.execute("SELECT COALESCE(SUM(amount),0) v FROM transactions WHERE kind='withdraw' AND status='approved'").fetchone()["v"]
            led=conn.execute("SELECT COALESCE(SUM(delta),0) v FROM ledger").fetchone()["v"]
        txt=(f"📈 <b>گزارش مالی</b>\n\n"
             f"💳 واریز تأییدشده: {format_mio(dep)}\n"
             f"💸 برداشت تأییدشده: {format_mio(wd)}\n"
             f"📒 خالص تغییرات دفترکل: {format_mio(led)}")
        await q.answer(); await q.edit_message_text(txt,parse_mode="HTML",reply_markup=back_admin()); return

    if d=="adm:gamesettings":
        txt=(
            "⚙️ <b>تنظیمات بازی</b>\n\n"
            f"🎲 ضریب تاس: ×{setting('dice_mult','1.5')}\n"
            f"💩 ردیف‌های پوپ: {setting('poop_rows',str(POOP_ROWS))}\n"
            f"💩 خانه‌های هر ردیف: {setting('poop_cols',str(POOP_COLS))}\n"
            f"💩 پوپ‌ها در ردیف‌ها: {setting('poop_counts','1,1,2,2,3')}\n"
            f"📈 ضرایب پوپ: {setting('poop_mults','1.2,1.4,1.6,2,3')}\n🎯 دارت: سفید= {setting('dart_white_values','1,3,5')} | قرمز= {setting('dart_red_values','2,4,6')}\n"
            f"⚽ فوتبال: اعداد گل= {setting('football_goal_values','4,5')} | تعداد شوت= {setting('football_shots','3')}\n\n"
            "برای تغییر، یکی از فرمت‌ها را ارسال کن:\n"
            "dice 1.7\nrows 5\ncols 4\npoops 1,1,2,2,3\nmults 1.2,1.5,2,2.5,3\nfootball_goals 4,5\nfootball_shots 3"
        )
        context.user_data["admin_action"]="game_settings"
        await q.answer(); await q.edit_message_text(txt,parse_mode="HTML",reply_markup=back_admin()); return
    if d=="adm:rewards":
        txt=(f"🎁 <b>تنظیمات پاداش</b>\n\n👥 دعوت‌کننده: {format_mio(int(setting('referrer_bonus','100000')))}\n👤 دعوت‌شده: {format_mio(int(setting('referred_bonus','50000')))}\n🎯 مبلغ دارت: {format_mio(int(setting('dart_amount','20000')))}\n🎯 ضریب دارت: ×{setting('dart_multiplier','2.0')}\n🧠 جایزه چالش: {format_mio(int(setting('quiz_prize','50000')))}\n\nفرمت: referrer 100000 | referred 50000 | dart_amount 20000 | dart_mult 2 | dart_white 1,3,5 | dart_red 2,4,6 | quiz_prize 50000")
        context.user_data['admin_action']='reward_settings'; await q.answer(); await q.edit_message_text(txt,parse_mode='HTML',reply_markup=back_admin()); return
    if d=="adm:leaderboard_rewards":
        count,rewards=get_leaderboard_rewards(); lines=["🎁 <b>تنظیم جوایز لیدربورد</b>","",f"🏆 تعداد رتبه‌های جایزه‌دار: {count}",""]
        for rank in range(1,count+1): lines.append(f"🏆 رتبه {rank}: {format_mio(rewards.get(rank,0))} میو" if rewards.get(rank,0) else f"▫️ رتبه {rank}: بدون جایزه")
        lines += ["","فرمت:","count 3","rank 1 1000000","rank 2 500000","rank 3 250000"]
        context.user_data["admin_action"]="leaderboard_rewards"; await q.answer(); await q.edit_message_text("\n".join(lines),parse_mode="HTML",reply_markup=back_admin()); return
    if d=="adm:quizsettings":
        txt=(f"🧠 <b>تنظیمات چالش گروه</b>\n\n🔘 وضعیت: {'فعال' if setting('quiz_enabled','1')=='1' else 'خاموش'}\n⏱️ فاصله: {setting('quiz_interval_minutes','10')} دقیقه\n💰 جایزه: {format_mio(int(setting('quiz_prize','50000')))}\n⌛ مهلت پاسخ: {setting('quiz_timeout_seconds','120')} ثانیه\n\nفرمت: enable 1 | interval 10 | prize 50000 | timeout 120")
        context.user_data['admin_action']='quiz_settings'; await q.answer(); await q.edit_message_text(txt,parse_mode='HTML',reply_markup=back_admin()); return
    if d=="adm:pending_finance":
        with closing(db()) as conn:
            rows=conn.execute("SELECT * FROM transactions WHERE status='pending' ORDER BY created_at DESC LIMIT 20").fetchall()
        if not rows:
            await q.answer(); await q.edit_message_text("💳 درخواست مالی در انتظار وجود ندارد.",reply_markup=back_admin()); return
        kb=[]
        lines=["💳 <b>درخواست‌های مالی</b>",""]
        for r in rows:
            icon="➕" if r["kind"]=="deposit" else "➖"
            lines.append(f"{icon} {r['tx_id']} | {r['user_id']} | {format_mio(r['amount'])} میو")
            kb.append([
                InlineKeyboardButton(f"✅ {r['tx_id']}",callback_data=f"fin:approve:{r['tx_id']}"),
                InlineKeyboardButton("❌",callback_data=f"fin:reject:{r['tx_id']}")
            ])
        kb.append([InlineKeyboardButton("⬅️ برگشت",callback_data="adm:home")])
        await q.answer(); await q.edit_message_text("\n".join(lines),parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb)); return

    if d=="adm:broadcast":
        context.user_data["admin_action"]="broadcast"
        await q.answer()
        await q.edit_message_text(
            "📣 <b>پیام همگانی</b>\n\nمتن پیام را بفرست.\n"
            "پیام برای کاربران ثبت‌شده ارسال می‌شود.",
            parse_mode="HTML", reply_markup=back_admin()
        )
        return



async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Admin input is intentionally handled ONLY in private chat.
    # Without this guard, an active admin_action could catch every ordinary
    # group message from the owner and reply with "فرمت نامعتبر" repeatedly.
    if not update.effective_user or update.effective_user.id != ADMIN_ID:
        return
    if not update.effective_chat or update.effective_chat.type != ChatType.PRIVATE:
        return
    if not update.message or not update.message.text:
        return
    action=context.user_data.get("admin_action")
    if not action:
        return
    text=(update.message.text or "").strip()
    if action=="balance":
        m=re.fullmatch(r"(\d+)\s+([+-]?\d+)",text)
        if not m: await update.message.reply_text("❌ فرمت: آیدی مقدار");return
        uid,delta=int(m.group(1)),int(m.group(2))
        if not get_user(uid): await update.message.reply_text("❌ کاربر پیدا نشد.");return
        try:new=atomic_balance(uid,delta,"admin_balance_change")
        except ValueError as e:await update.message.reply_text(f"❌ {e}");return
        context.user_data.clear(); await update.message.reply_text(f"✅ انجام شد.\n🆔 {uid}\n💰 تغییر: {delta:+,}\n💰 موجودی: {format_mio(new)}",reply_markup=admin_menu())
        try:await context.bot.send_message(uid,f"🛠 تغییر موجودی توسط ادمین\n💰 تغییر: {delta:+,} میو\n💰 موجودی: {format_mio(new)} میو")
        except TelegramError:pass
    elif action=="search":
        key=text.lstrip("@");
        with closing(db()) as conn:
            r=conn.execute("SELECT * FROM users WHERE user_id=? OR username=? LIMIT 1",(int(key) if key.isdigit() else -1,key)).fetchone()
        context.user_data.clear()
        if not r: await update.message.reply_text("❌ پیدا نشد.",reply_markup=admin_menu());return
        await update.message.reply_text(f"👤 پروفایل\n\n🆔 {r['user_id']}\n🔗 @{r['username'] or '-'}\n👤 {r['first_name']}\n💰 {format_mio(r['balance'])} میو\n🎮 بازی: {r['games_count']}\n🏆 برد: {r['wins_count']}",reply_markup=admin_menu())
    elif action=="channel_add":
        raw=text.strip()
        if raw.lower()=="لغو":
            context.user_data.clear()
            await update.message.reply_text("❌ لغو شد.", reply_markup=admin_menu())
            return
        chat_id=raw
        username=""
        url=""
        if raw.startswith("https://t.me/") or raw.startswith("http://t.me/"):
            username="@"+raw.rstrip("/").split("/")[-1].split("?")[0]
            chat_id=username
            url=f"https://t.me/{username[1:]}"
        elif raw.startswith("@"):
            username=raw
            chat_id=raw
            url=f"https://t.me/{raw[1:]}"
        try:
            chat=await context.bot.get_chat(chat_id)
            title=chat.title or getattr(chat, "first_name", "") or chat_id
            ctype="channel" if chat.type=="channel" else "group"
            actual_id=str(chat.id)
            with closing(db()) as conn:
                conn.execute(
                    """INSERT INTO required_chats(chat_id,title,username,url,chat_type)
                       VALUES(?,?,?,?,?)
                       ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title,
                       username=excluded.username,url=excluded.url,chat_type=excluded.chat_type,enabled=1""",
                    (actual_id,title,getattr(chat,"username","") and "@"+chat.username or username,url,ctype)
                )
            context.user_data.clear()
            await update.message.reply_text(
                f"✅ {('کانال' if ctype=='channel' else 'گروه')} اجباری اضافه شد.\n"
                f"📌 {title}\n🆔 {actual_id}\n"
                "⚠️ برای بررسی عضویت، ربات باید در آن عضو/ادمین باشد.",
                reply_markup=admin_menu()
            )
        except TelegramError as e:
            await update.message.reply_text(
                "❌ این کانال/گروه پیدا نشد یا ربات به آن دسترسی ندارد.\n"
                "آیدی، @username یا لینک را بررسی کن."
            )
    elif action=="game_settings":
        m=re.fullmatch(r"(dice|rows|cols|poops|mults|football_goals|football_shots)\s+(.+)",text,re.I)
        if not m:
            await update.message.reply_text("❌ فرمت نامعتبر."); return
        key,val=m.group(1).lower(),m.group(2).strip()
        try:
            if key=="dice":
                x=float(val)
                if not 1.0 <= x <= 10.0: raise ValueError
                set_setting("dice_mult",str(x))
            elif key=="rows":
                x=int(val)
                if not 1 <= x <= 20: raise ValueError
                set_setting("poop_rows",str(x))
            elif key=="cols":
                x=int(val)
                if not 1 <= x <= 10: raise ValueError
                set_setting("poop_cols",str(x))
            elif key=="poops":
                xs=[int(v.strip()) for v in val.split(",")]
                if not xs or len(xs)!=int(setting("poop_rows",str(POOP_ROWS))) or any(x<0 or x>=int(setting("poop_cols",str(POOP_COLS))) for x in xs): raise ValueError
                set_setting("poop_counts",",".join(map(str,xs)))
            elif key=="mults":
                xs=[float(v.strip()) for v in val.split(",")]
                if not xs or len(xs)!=int(setting("poop_rows",str(POOP_ROWS))) or any(x<=0 for x in xs): raise ValueError
                set_setting("poop_mults",",".join(map(str,xs)))
            elif key=="football_goals":
                xs=sorted({int(v.strip()) for v in val.split(",") if v.strip()})
                if not xs or any(x<1 or x>5 for x in xs): raise ValueError
                set_setting("football_goal_values",",".join(map(str,xs)))
            elif key=="football_shots":
                x=int(val)
                if not 1 <= x <= 10: raise ValueError
                set_setting("football_shots",str(x))
        except ValueError:
            await update.message.reply_text("❌ مقدار نامعتبر یا خارج از محدوده."); return
        context.user_data.clear()
        await update.message.reply_text("✅ تنظیم ذخیره شد.",reply_markup=admin_menu())
    elif action=="reward_settings":
        m=re.fullmatch(r"(referrer|referred|dart_amount|dart_mult|dart_white|dart_red|quiz_prize|daily_bonus)\s+(.+)",text,re.I)
        if not m: await update.message.reply_text('❌ فرمت نامعتبر.'); return
        k,v=m.group(1).lower(),m.group(2).strip()
        try:
            if k=='dart_mult':
                x=float(v); key='dart_multiplier'
                if x<=0 or x>20: raise ValueError
                set_setting(key,str(x))
            elif k in ('dart_white','dart_red'):
                vals=[int(z.strip()) for z in v.split(',') if z.strip().isdigit()]
                if not vals or any(z<1 or z>6 for z in vals): raise ValueError
                set_setting('dart_white_values' if k=='dart_white' else 'dart_red_values',','.join(map(str,vals)))
            else:
                x=parse_amount(v); key={'referrer':'referrer_bonus','referred':'referred_bonus','dart_amount':'dart_amount','quiz_prize':'quiz_prize','daily_bonus':'daily_bonus'}[k]
                if x<=0: raise ValueError
                set_setting(key,str(x))
        except Exception: await update.message.reply_text('❌ مقدار نامعتبر.'); return
        context.user_data.clear(); await update.message.reply_text('✅ تنظیم پاداش ذخیره شد.',reply_markup=admin_menu())
    elif action=="leaderboard_rewards":
        m=re.fullmatch(r"(count|rank)\s+(.+)",text,re.I)
        if not m: await update.message.reply_text("❌ فرمت نامعتبر. مثال: count 3 یا rank 1 1000000"); return
        try:
            cmd,args=m.group(1).lower(),m.group(2).strip()
            if cmd=="count":
                count=int(args)
                if not 0<=count<=100: raise ValueError
                raw=json.loads(setting("leaderboard_rewards","{}")); raw=raw if isinstance(raw,dict) else {}
                raw={str(k):int(v) for k,v in raw.items() if str(k).isdigit() and 1<=int(k)<=count and int(v)>0}
                with closing(db()) as conn:
                    conn.execute("BEGIN IMMEDIATE"); conn.execute("INSERT INTO settings(key,value) VALUES('leaderboard_reward_count',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(count),)); conn.execute("INSERT INTO settings(key,value) VALUES('leaderboard_rewards',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(raw,ensure_ascii=False),)); conn.commit()
            else:
                parts=args.split();
                if len(parts)!=2: raise ValueError
                rank=int(parts[0]); amount=parse_amount(parts[1]); count,_=get_leaderboard_rewards()
                if count<1 or not 1<=rank<=count or amount<=0: raise ValueError
                raw=json.loads(setting("leaderboard_rewards","{}")); raw=raw if isinstance(raw,dict) else {}; raw[str(rank)]=amount; set_setting("leaderboard_rewards",json.dumps(raw,ensure_ascii=False))
            context.user_data.clear(); await update.message.reply_text("✅ تنظیم جوایز لیدربورد ذخیره شد.",reply_markup=admin_menu())
        except (TypeError,ValueError,json.JSONDecodeError): await update.message.reply_text("❌ مقدار نامعتبر یا خارج از محدوده.")
        return
    elif action=="quiz_settings":
        m=re.fullmatch(r"(enable|interval|prize|timeout)\s+(.+)",text,re.I)
        if not m: await update.message.reply_text('❌ فرمت نامعتبر.'); return
        k,v=m.group(1).lower(),m.group(2).strip()
        try:
            if k=='enable': x=int(v); key='quiz_enabled'; ok=x in (0,1)
            elif k=='interval': x=int(v); key='quiz_interval_minutes'; ok=1<=x<=1440
            elif k=='prize': x=parse_amount(v); key='quiz_prize'; ok=x>0
            else: x=int(v); key='quiz_timeout_seconds'; ok=15<=x<=3600
            if not ok: raise ValueError
            set_setting(key,str(x))
        except Exception: await update.message.reply_text('❌ مقدار نامعتبر یا خارج از محدوده.'); return
        context.user_data.clear(); await update.message.reply_text('✅ تنظیم چالش ذخیره شد.',reply_markup=admin_menu())
    elif action=="broadcast":
        context.user_data.clear()
        with closing(db()) as conn: ids=[r["user_id"] for r in conn.execute("SELECT user_id FROM users").fetchall()]
        sent=0
        for uid in ids:
            try:
                await context.bot.send_message(uid,text)
                sent+=1
                await asyncio.sleep(0.05)
            except RetryAfter as e: await asyncio.sleep(e.retry_after)
            except TelegramError: pass
        await update.message.reply_text(f"📣 ارسال همگانی تمام شد.\n✅ ارسال موفق: {sent}\n👥 کل: {len(ids)}",reply_markup=admin_menu())


# --------------------------- Error handling ---------------------------
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error

    if isinstance(err, Conflict):
        logger.error("Telegram polling conflict: another instance may be running: %s", err)
        return

    if isinstance(err, RetryAfter):
        logger.warning("RetryAfter: %s", err)
        return

    logger.error("Unhandled bot error: %r", err, exc_info=err)

    now = utc_ts()
    last = context.application.bot_data.get("last_error_notice", 0.0)
    if now - last < 600:
        return
    context.application.bot_data["last_error_notice"] = now

    try:
        await context.bot.send_message(
            ADMIN_ID,
            "⚠️ خطای داخلی ربات ثبت شد. جزئیات در logs/bot.log ذخیره شده است."
        )
    except Exception:
        pass

# --------------------------- Main ---------------------------
async def post_init(app):
    task = app.bot_data.get("quiz_task")
    if task and not task.done():
        return
    class QuizContext:
        def __init__(self, bot):
            self.bot = bot
    app.bot_data["quiz_task"] = asyncio.create_task(quiz_loop(QuizContext(app.bot)))
    logger.info("Group quiz scheduler started")

async def post_shutdown(app):
    task = app.bot_data.get('quiz_task')
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

def main():
    if not acquire_single_instance():
        logger.error("Another MEOWBET instance is already running. Exiting.")
        return

    init_db()
    app=Application.builder().token(TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()

    # Group tracking runs first so active groups are available to the quiz scheduler.
    app.add_handler(MessageHandler(filters.ALL, track_group_message), group=-10)

    # Commands / admin entry points.
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel_flow))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("help", show_help), group=-2)

    # Main menu MUST be before broad text handlers.
    app.add_handler(MessageHandler(filters.Regex(r"^🛠 پنل مدیریت$"), admin_cmd, ), group=-2)
    app.add_handler(MessageHandler(filters.Regex(r"^➕ افزودن ربات به گروه$"), add_group_button), group=-2)
    app.add_handler(MessageHandler(filters.Regex(r"^➕ واریز$"), deposit_start), group=-2)
    app.add_handler(MessageHandler(filters.Regex(r"^➖ برداشت$"), withdraw_start), group=-2)
    app.add_handler(MessageHandler(filters.Regex(r"^(🎁 ?لینک هدیه|لینک هدیه 🎁)$"), gift_start), group=-2)
    app.add_handler(MessageHandler(filters.Regex(r"^👥 دعوت دوستان$"), referral_menu), group=-2)
    app.add_handler(MessageHandler(filters.Regex(r"^💰 موجودی$"), show_balance), group=-2)
    app.add_handler(MessageHandler(filters.Regex(r"^🎮 بازی‌ها$"), games_menu), group=-2)
    app.add_handler(MessageHandler(filters.Regex(r"^🎁 جایزه روزانه$"), daily_bonus), group=-2)
    app.add_handler(MessageHandler(filters.Regex(r"^🏆 جدول برترین‌ها$"), leaderboard), group=-2)
    app.add_handler(MessageHandler(filters.Regex(r"^📜 تاریخچه$"), history), group=-2)
    app.add_handler(MessageHandler(filters.Regex(r"^(راهنما|❓ راهنما)$"), show_help), group=-2)

    # Game commands have priority over the general group-quiz text handler.
    app.add_handler(MessageHandler(filters.Regex(r"^#(سفید|قرمز)\s+"), start_dart), group=-1)
    app.add_handler(MessageHandler(filters.Regex(r"^#(زوج|فرد)\s+"), start_dice), group=-1)
    # Diagnostic-only POOP handler: confirms receipt without changing balance,
    # creating a bet, or writing a financial transaction.
    async def poop_diagnostic(update, context):
        if not update.effective_message:
            return
        text = update.effective_message.text or ""
        await update.effective_message.reply_text(
            f"✅ POOP HANDLER RECEIVED\ntext={text!r}"
        )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^#پوپ(?:\u200c)?\s+"),
            poop_diagnostic,
        ),
        group=-1,
    )
    app.add_handler(MessageHandler(filters.Regex(r"^#فوتبال(?:\u200c)?$"), start_football), group=-1)

    # One compatible dice handler dispatches 🎯, 🎲 and ⚽ by emoji.
    # This avoids filters.Dice.DART, which does not exist in some PTB versions.
    app.add_handler(MessageHandler(filters.Dice.ALL, handle_dice_or_dart), group=-1)

    # Group quiz answers only run after game-command handlers.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_quiz_answer), group=0)

    # User finance/gift state machine.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, finance_and_gift_text), group=1)

    # Admin text input is private-only inside admin_text itself.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, admin_text), group=2)

    # Inline callbacks.
    app.add_handler(CallbackQueryHandler(admin_router, pattern=r"^adm:"))
    app.add_handler(CallbackQueryHandler(finance_callback, pattern=r"^fin:"))
    app.add_handler(CallbackQueryHandler(check_join, pattern=r"^check_join$"))
    app.add_handler(CallbackQueryHandler(cancel_dice, pattern=r"^cancel_dice:"))
    app.add_handler(CallbackQueryHandler(poop_callback, pattern=r"^poop_"))

    app.add_error_handler(on_error)

    logger.info("MEOWBET V5 started DB=%s", DB_PATH)
    app.run_polling(allowed_updates=Update.ALL_TYPES,drop_pending_updates=True)

if __name__=="__main__": main()
