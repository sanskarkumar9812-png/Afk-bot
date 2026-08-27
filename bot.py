"""
AFK + Reminders + Quote of the Day + Memes Telegram Bot
--------------------------------------------------------
  - /afk [reason]          -> marks you AFK
  - any message you send   -> automatically clears your AFK status
  - someone mentions you or replies to you while you're AFK
                            -> bot tells them you're away, since when, and why
  - /remind <time> <text>  -> one-off reminder, e.g. /remind 30m stretch
  - /quote                 -> random quote right now
  - /qotd on HH:MM         -> auto-post a quote every day at HH:MM (UTC) in this chat
  - /qotd off              -> stop the daily quote in this chat
  - /meme                  -> random meme image

Built with python-telegram-bot v21 (async).
Data is stored in a local SQLite file so AFK status and daily-quote settings
survive restarts.
"""

import os
import re
import sqlite3
import time
from datetime import datetime, timezone, time as dtime

import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
DB_PATH = "afk.db"

QUOTE_API = "https://zenquotes.io/api/random"
MEME_API = "https://meme-api.com/gimme"


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS afk (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            reason TEXT,
            since REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS qotd (
            chat_id INTEGER PRIMARY KEY,
            hour INTEGER,
            minute INTEGER
        )
        """
    )
    conn.commit()
    conn.close()


def set_qotd(chat_id: int, hour: int, minute: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO qotd (chat_id, hour, minute) VALUES (?, ?, ?)",
        (chat_id, hour, minute),
    )
    conn.commit()
    conn.close()


def remove_qotd(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM qotd WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()


def get_all_qotd():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT chat_id, hour, minute FROM qotd").fetchall()
    conn.close()
    return rows


def set_afk(user_id: int, username: str, first_name: str, reason: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO afk (user_id, username, first_name, reason, since) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, username, first_name, reason, time.time()),
    )
    conn.commit()
    conn.close()


def get_afk(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT username, first_name, reason, since FROM afk WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return row  # None if not AFK


def clear_afk(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM afk WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_afk_by_username(username: str):
    """Look up AFK status by @username (used when someone @mentions a non-replied user)."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT user_id, first_name, reason, since FROM afk WHERE username = ?",
        (username.lower(),),
    ).fetchone()
    conn.close()
    return row


def human_since(ts: float) -> str:
    delta = time.time() - ts
    mins, sec = divmod(int(delta), 60)
    hrs, mins = divmod(mins, 60)
    days, hrs = divmod(hrs, 24)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hrs:
        parts.append(f"{hrs}h")
    if mins:
        parts.append(f"{mins}m")
    if not parts:
        parts.append(f"{sec}s")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------
async def is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """True if the sender is an admin/creator of the group, or this is a private chat."""
    chat = update.effective_chat
    user = update.effective_user
    if chat is None or user is None:
        return False
    if chat.type == "private":
        return True  # no concept of "admin" in a 1:1 chat
    member = await context.bot.get_chat_member(chat.id, user.id)
    return member.status in ("administrator", "creator")


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def afk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_group_admin(update, context):
        await update.message.reply_text("Only group admins can use /afk here.")
        return

    user = update.effective_user
    reason = " ".join(context.args) if context.args else "AFK"

    set_afk(user.id, (user.username or "").lower(), user.first_name, reason)

    await update.message.reply_text(
        f"*{user.first_name}* is now AFK.\n"
        f"Reason: {reason}\n\n"
        f"_Tip: I'll let others know when they mention you._",
        parse_mode=ParseMode.MARKDOWN,
    )


async def general_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs on every non-command text message in the chat."""
    message = update.effective_message
    sender = update.effective_user
    if message is None or sender is None:
        return

    # 1) If the sender was AFK, welcome them back and clear status.
    row = get_afk(sender.id)
    if row is not None:
        _, _, reason, since = row
        clear_afk(sender.id)
        await message.reply_text(
            f"Welcome back *{sender.first_name}*! I've removed your AFK status.",
            parse_mode=ParseMode.MARKDOWN,
        )

    # 2) If this message is a reply to an AFK user, tell the sender.
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        target_row = get_afk(target.id)
        if target_row is not None:
            _, first_name, reason, since = target_row
            await message.reply_text(
                f"*{first_name}* is AFK: {reason} ({human_since(since)} ago)",
                parse_mode=ParseMode.MARKDOWN,
            )
            return  # avoid double-notifying if also @mentioned below

    # 3) If the message @mentions an AFK user by username, tell the sender.
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":  # plain @username mention
                mention_text = message.text[entity.offset: entity.offset + entity.length]
                username = mention_text.lstrip("@")
                target_row = get_afk_by_username(username)
                if target_row is not None:
                    _, first_name, reason, since = target_row
                    await message.reply_text(
                        f"*{first_name}* is AFK: {reason} ({human_since(since)} ago)",
                        parse_mode=ParseMode.MARKDOWN,
                    )


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------
DURATION_RE = re.compile(r"^(\d+)([smhd])$", re.IGNORECASE)
DURATION_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(text: str):
    match = DURATION_RE.match(text.strip())
    if not match:
        return None
    value, unit = match.groups()
    return int(value) * DURATION_UNITS[unit.lower()]


async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_group_admin(update, context):
        await update.message.reply_text("Only group admins can use /remind here.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /remind <time> <message>\n"
            "Example: /remind 30m Take a break\n"
            "Time units: s (seconds), m (minutes), h (hours), d (days)"
        )
        return

    seconds = parse_duration(context.args[0])
    if seconds is None:
        await update.message.reply_text(
            "Couldn't parse that time. Try something like 10m, 2h, or 1d."
        )
        return

    reminder_text = " ".join(context.args[1:])
    user = update.effective_user
    chat_id = update.effective_chat.id

    context.job_queue.run_once(
        send_reminder,
        seconds,
        chat_id=chat_id,
        data={"user_mention": user.mention_html(), "text": reminder_text},
        name=f"reminder_{user.id}_{time.time()}",
    )

    await update.message.reply_text(
        f"Got it, {user.first_name} — I'll remind you in {context.args[0]}."
    )


async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    await context.bot.send_message(
        chat_id=job.chat_id,
        text=f"⏰ {job.data['user_mention']}, reminder: {job.data['text']}",
        parse_mode=ParseMode.HTML,
    )


# ---------------------------------------------------------------------------
# Quote of the day
# ---------------------------------------------------------------------------
async def fetch_quote() -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(QUOTE_API)
        r.raise_for_status()
        data = r.json()
    q = data[0]
    return f'"{q["q"]}"\n— {q["a"]}'


async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = await fetch_quote()
    except Exception:
        text = "Couldn't fetch a quote right now — try again in a bit."
    await update.message.reply_text(text)


TIME_HHMM_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


async def qotd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not context.args or context.args[0].lower() not in ("on", "off"):
        await update.message.reply_text(
            "Usage:\n"
            "/qotd on HH:MM  — daily quote at that UTC time (e.g. /qotd on 09:00)\n"
            "/qotd off       — stop the daily quote in this chat"
        )
        return

    mode = context.args[0].lower()

    if mode == "off":
        remove_qotd(chat_id)
        for job in context.job_queue.get_jobs_by_name(f"qotd_{chat_id}"):
            job.schedule_removal()
        await update.message.reply_text("Daily quote turned off for this chat.")
        return

    # mode == "on"
    if len(context.args) < 2 or not TIME_HHMM_RE.match(context.args[1]):
        await update.message.reply_text("Please give a time like: /qotd on 09:00 (UTC)")
        return

    hour, minute = map(int, context.args[1].split(":"))
    set_qotd(chat_id, hour, minute)

    for job in context.job_queue.get_jobs_by_name(f"qotd_{chat_id}"):
        job.schedule_removal()

    context.job_queue.run_daily(
        post_qotd,
        time=dtime(hour=hour, minute=minute, tzinfo=timezone.utc),
        chat_id=chat_id,
        name=f"qotd_{chat_id}",
    )

    await update.message.reply_text(
        f"Daily quote of the day set for {context.args[1]} UTC in this chat."
    )


async def post_qotd(context: ContextTypes.DEFAULT_TYPE):
    try:
        text = await fetch_quote()
    except Exception:
        return  # skip silently if the quote API is down for a scheduled post
    await context.bot.send_message(chat_id=context.job.chat_id, text=f"🌅 Quote of the day:\n{text}")


def restore_qotd_jobs(app: Application):
    """Reschedule daily quote jobs for all chats that had it configured before a restart."""
    for chat_id, hour, minute in get_all_qotd():
        app.job_queue.run_daily(
            post_qotd,
            time=dtime(hour=hour, minute=minute, tzinfo=timezone.utc),
            chat_id=chat_id,
            name=f"qotd_{chat_id}",
        )


# ---------------------------------------------------------------------------
# Random memes
# ---------------------------------------------------------------------------
async def meme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(MEME_API)
            r.raise_for_status()
            data = r.json()
        await update.message.reply_photo(photo=data["url"], caption=data.get("title", ""))
    except Exception:
        await update.message.reply_text("Couldn't fetch a meme right now — try again in a bit.")


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
def main():
    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        raise SystemExit(
            "No bot token found. Set the BOT_TOKEN environment variable "
            "(locally in a .env/export, or in Railway's Variables tab)."
        )

    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("afk", afk_command))
    app.add_handler(CommandHandler("remind", remind_command))
    app.add_handler(CommandHandler("quote", quote_command))
    app.add_handler(CommandHandler("qotd", qotd_command))
    app.add_handler(CommandHandler("meme", meme_command))
    # Catch every other text message (groups + private chats)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, general_message))

    restore_qotd_jobs(app)

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
