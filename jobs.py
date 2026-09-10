"""
Background jobs:
  - Weekly reset: every Sunday, announce a "Champion of the Week" per chat
    and clear the weekly leaderboard for the next round.
  - Startup restore: re-arm any auto-quiz jobs that were running before a
    bot restart (persisted in chat_settings).
"""

import datetime
import logging

from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes

import database as db
import trivia_handlers

logger = logging.getLogger(__name__)

WEEKLY_RESET_TIME = datetime.time(hour=20, minute=0)  # 20:00 UTC every Sunday


async def weekly_reset_job(context: ContextTypes.DEFAULT_TYPE):
    for chat_id in db.get_all_chats_with_scores():
        rows = db.get_weekly_leaderboard(chat_id, limit=3)
        if rows and rows[0]["points"] > 0:
            medals = ["🥇", "🥈", "🥉"]
            lines = ["🏆 *Champion of the Week!* 🏆\n"]
            for i, row in enumerate(rows):
                name = row["first_name"] or row["username"] or f"User {row['user_id']}"
                lines.append(f"{medals[i]} *{name}* — {row['points']} pts")
            lines.append("\nThe weekly board resets now — good luck next week! 🏁")
            try:
                await context.bot.send_message(
                    chat_id=chat_id, text="\n".join(lines), parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.warning("Couldn't send weekly reset message to %s: %s", chat_id, e)
        db.reset_weekly_scores(chat_id)


async def restore_autoquiz_jobs(application: Application):
    for chat_id, minutes in db.get_all_auto_chats():
        application.job_queue.run_repeating(
            trivia_handlers._autoquiz_job_callback,
            interval=minutes * 60,
            first=10,
            chat_id=chat_id,
            name=trivia_handlers._autoquiz_job_name(chat_id),
        )
        logger.info("Restored auto-quiz for chat %s every %s minutes", chat_id, minutes)


def schedule_recurring_jobs(application: Application):
    # days=(6,) -> Sunday. python-telegram-bot's JobQueue follows Python's
    # datetime.date.weekday() convention: Monday=0 ... Sunday=6.
    application.job_queue.run_daily(
        weekly_reset_job,
        time=WEEKLY_RESET_TIME,
        days=(6,),
        name="weekly_reset",
    )
