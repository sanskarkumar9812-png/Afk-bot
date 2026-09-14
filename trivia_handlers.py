"""
Handlers for the core trivia game: asking questions (via quiz_engine),
leaderboards, personal stats, daily streaks, achievements, and auto-quiz.
"""

import hashlib
import logging
import random

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

import config
import database as db
import quiz_engine
import ui
from questions import QUESTIONS

logger = logging.getLogger(__name__)

OPEN_PERIOD_SECONDS = 25
MIN_AUTOQUIZ_MINUTES = 1
MAX_AUTOQUIZ_MINUTES = 24 * 60


def _question_key(q: dict) -> str:
    return hashlib.md5(q["question"].encode("utf-8")).hexdigest()[:12]


def _pick_question(chat_id: int) -> dict:
    """Avoids repeating a question until most of the pool has been used."""
    total = len(QUESTIONS)
    keep_last = max(1, min(total - 5, int(total * 0.85)))
    recent = db.get_recently_asked(chat_id, keep_last)

    candidates = [q for q in QUESTIONS if _question_key(q) not in recent]
    if not candidates:
        candidates = QUESTIONS  # pool exhausted, allow a full reset

    q = random.choice(candidates)
    db.record_asked(chat_id, _question_key(q), keep_last)
    return q


async def send_random_question(chat_id: int, context: ContextTypes.DEFAULT_TYPE, label: str = None):
    q = _pick_question(chat_id)
    points = config.POINTS_BY_DIFFICULTY.get(q["difficulty"], 10)

    session_id = await quiz_engine.send_quiz_message(
        chat_id=chat_id, question=q, points=points, context=context,
        kind="trivia", header_label=label,
    )
    context.job_queue.run_once(
        _close_quiz_job, when=OPEN_PERIOD_SECONDS, data=session_id, chat_id=chat_id,
        name=f"close_quiz_{session_id}",
    )


async def _close_quiz_job(context: ContextTypes.DEFAULT_TYPE):
    await quiz_engine.close_quiz_session(context.job.data, context)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

async def quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cooldown = db.get_quiz_cooldown(chat_id)
    allowed, remaining = db.check_and_apply_cooldown(chat_id, "quiz", cooldown)

    if not allowed:
        await update.message.reply_text(f"Slow down — try again in {remaining}s.")
        return

    try:
        await send_random_question(chat_id, context)
    except TelegramError:
        await update.message.reply_text(
            "Couldn't send a question just now (Telegram rate limit or a temporary error). "
            "Please try again in a moment."
        )


async def daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Daily Challenge — answer correctly to extend your streak.")
    try:
        await send_random_question(update.effective_chat.id, context, label="Daily")
    except TelegramError:
        await update.message.reply_text("Couldn't send the daily question — please try again shortly.")


async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows = db.get_leaderboard(chat_id, limit=10)

    if not rows:
        await update.message.reply_text("No scores yet in this chat. Run /quiz to get started.")
        return

    lines = []
    for i, row in enumerate(rows):
        name = row["first_name"] or row["username"] or f"User {row['user_id']}"
        rank = config.get_rank(row["points"])
        lines.append(ui.rank_line(i, name, f"{row['points']} pts ({rank})"))

    text = ui.section("Leaderboard — All Time", lines)
    text += "\n\n/weekly for this week's board · /mystats for your own numbers"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def weekly_leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows = db.get_weekly_leaderboard(chat_id, limit=10)

    if not rows:
        await update.message.reply_text("No points scored this week yet. Run /quiz to get started.")
        return

    lines = []
    for i, row in enumerate(rows):
        name = row["first_name"] or row["username"] or f"User {row['user_id']}"
        lines.append(ui.rank_line(i, name, f"{row['points']} pts, {row['correct']} correct"))

    text = ui.section("Leaderboard — This Week", lines)
    text += "\n\nResets every Sunday."
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def mystats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    stats = db.get_user_stats(chat_id, user.id)

    if not stats:
        await update.message.reply_text("No stats yet in this chat. Try /quiz to get started.")
        return

    total = stats["correct"] + stats["wrong"]
    accuracy = (stats["correct"] / total * 100) if total else 0
    rank = config.get_rank(stats["points"])
    next_info = config.next_rank_info(stats["points"])
    next_line = f"{next_info[0]} pts to {next_info[1]}" if next_info else "Top rank reached"

    badges = db.get_unlocked_badges(chat_id, user.id)
    all_ach = config.ACHIEVEMENTS + config.PREDICTION_ACHIEVEMENTS + config.DUEL_ACHIEVEMENTS
    badge_names = [b["name"] for b in all_ach if b["key"] in badges]
    badge_line = ", ".join(badge_names) if badge_names else "None yet"

    pred_summary = db.get_user_prediction_summary(chat_id, user.id)

    lines = [
        f"Rank: {rank}  ({next_line})",
        "",
        f"Points: {stats['points']}",
        f"Correct / Wrong: {stats['correct']} / {stats['wrong']} ({accuracy:.0f}%)",
        f"Streak: {stats['streak']} (best {stats['best_streak']})",
        f"Daily streak: {stats['daily_streak']} days (best {stats['best_daily_streak']})",
        f"Duels: {stats['duel_wins']}W – {stats['duel_losses']}L",
        f"Predictions: {pred_summary['total_points']} pts across {pred_summary['rounds_played']} round(s)",
        "",
        f"Badges: {badge_line}",
    ]
    text = ui.section("Your Profile", lines)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


def _autoquiz_job_name(chat_id: int) -> str:
    return f"autoquiz_{chat_id}"


async def _autoquiz_job_callback(context: ContextTypes.DEFAULT_TYPE):
    try:
        await send_random_question(context.job.chat_id, context)
    except TelegramError as e:
        logger.warning("Autoquiz send failed in %s: %s", context.job.chat_id, e)


async def autoquiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("Usage: /autoquiz <minutes>  e.g. /autoquiz 30")
        return

    try:
        minutes = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a whole number of minutes, e.g. /autoquiz 30")
        return

    if not (MIN_AUTOQUIZ_MINUTES <= minutes <= MAX_AUTOQUIZ_MINUTES):
        await update.message.reply_text(
            f"Choose a value between {MIN_AUTOQUIZ_MINUTES} and {MAX_AUTOQUIZ_MINUTES} minutes."
        )
        return

    for job in context.job_queue.get_jobs_by_name(_autoquiz_job_name(chat_id)):
        job.schedule_removal()

    context.job_queue.run_repeating(
        _autoquiz_job_callback,
        interval=minutes * 60,
        first=10,
        chat_id=chat_id,
        name=_autoquiz_job_name(chat_id),
    )
    db.set_auto_interval(chat_id, minutes)

    await update.message.reply_text(
        f"Auto-quiz enabled — a question every {minutes} minute(s). Use /stopquiz to disable."
    )


async def stopquiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(_autoquiz_job_name(chat_id))

    if not jobs:
        await update.message.reply_text("Auto-quiz isn't running in this chat.")
        return

    for job in jobs:
        job.schedule_removal()
    db.set_auto_interval(chat_id, 0)

    await update.message.reply_text("Auto-quiz stopped.")


# --------------------------------------------------------------------------
# Achievement checking (called after any correct trivia answer)
# --------------------------------------------------------------------------

async def check_and_announce_achievements(chat_id: int, user, stats: dict, context: ContextTypes.DEFAULT_TYPE):
    already = db.get_unlocked_badges(chat_id, user.id)
    newly_unlocked = config.check_trivia_achievements(stats, already)

    for ach in newly_unlocked:
        if db.unlock_badge(chat_id, user.id, ach["key"]):
            name = user.first_name or user.username or "A player"
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"Badge unlocked — {name}: *{ach['name']}*\n{ach['desc']}",
                    parse_mode=ParseMode.MARKDOWN,
                )
            except TelegramError as e:
                logger.warning("Couldn't announce badge in %s: %s", chat_id, e)
