"""
/cooldown — lets an admin set a per-chat cooldown between manual /quiz
requests, so a chat can't be spammed into hitting Telegram's flood limits.
Accepts combined units: "10m 5s", "10m5s", "90s", "2m", or a bare number
of seconds. /cooldown off (or /cooldown 0) disables it.

Only /quiz respects this (see trivia_handlers.quiz_cmd) — autoquiz and
duels run on their own separate timers and aren't affected.
"""

import re

from telegram import Update
from telegram.ext import ContextTypes

import database as db

_UNIT_PATTERN = re.compile(r"(\d+)\s*(h|m|s)", re.IGNORECASE)


def parse_duration(text: str):
    """Parses '10m 5s', '10m5s', '90s', '2m', or a bare integer into total
    seconds. Returns None if nothing valid was found."""
    text = text.strip().lower()
    if text in ("off", "none", "disable", "0"):
        return 0

    if text.isdigit():
        return int(text)

    matches = _UNIT_PATTERN.findall(text)
    if not matches:
        return None

    total = 0
    for value, unit in matches:
        value = int(value)
        if unit == "h":
            total += value * 3600
        elif unit == "m":
            total += value * 60
        elif unit == "s":
            total += value
    return total


async def _is_chat_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    if chat.type == "private":
        return True
    member = await context.bot.get_chat_member(chat.id, update.effective_user.id)
    return member.status in ("administrator", "creator")


async def cooldown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not context.args:
        current = db.get_quiz_cooldown(chat_id)
        if current <= 0:
            await update.message.reply_text(
                "No cooldown set for /quiz. Set one with /cooldown 10m 5s (admin only)."
            )
        else:
            await update.message.reply_text(f"Current /quiz cooldown: {current}s.")
        return

    if not await _is_chat_admin(update, context):
        await update.message.reply_text("Only chat admins can change the cooldown.")
        return

    text = " ".join(context.args)
    seconds = parse_duration(text)

    if seconds is None:
        await update.message.reply_text(
            "Couldn't parse that. Try /cooldown 10m 5s, /cooldown 30s, or /cooldown off."
        )
        return

    db.set_quiz_cooldown(chat_id, seconds)

    if seconds == 0:
        await update.message.reply_text("Cooldown disabled — /quiz has no wait time.")
    else:
        await update.message.reply_text(f"/quiz cooldown set to {seconds}s.")
