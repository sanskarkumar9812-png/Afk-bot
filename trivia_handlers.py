"""
Handlers for the core trivia game: asking questions, grading poll answers,
leaderboards, personal stats, daily streaks, achievements, and auto-quiz.
"""

import logging
import random

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
import database as db
from questions import QUESTIONS

logger = logging.getLogger(__name__)

OPEN_PERIOD_SECONDS = 25
MIN_AUTOQUIZ_MINUTES = 1
MAX_AUTOQUIZ_MINUTES = 24 * 60

CATEGORY_TAGS = {
    "history": "🏛 History",
    "records": "📊 Records",
    "drivers": "🏎 Drivers",
    "teams": "🔧 Teams",
    "rules": "📜 Rules",
    "meme": "😂 Meme/Iconic",
}


async def send_random_question(chat_id: int, context: ContextTypes.DEFAULT_TYPE, label: str = None):
    q = random.choice(QUESTIONS)
    tag = CATEGORY_TAGS.get(q["category"], "🏁 F1")
    points = config.POINTS_BY_DIFFICULTY.get(q["difficulty"], 10)
    diff_emoji = {"easy": "⭐", "medium": "⭐⭐", "hard": "⭐⭐⭐"}.get(q["difficulty"], "⭐⭐")

    prefix = f"{label} " if label else ""
    message = await context.bot.send_poll(
        chat_id=chat_id,
        question=f"{prefix}[{tag} {diff_emoji}] {q['question']}",
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct"],
        explanation=f"{q['explanation']} (+{points} pts)",
        is_anonymous=False,
        open_period=OPEN_PERIOD_SECONDS,
    )
    db.save_active_poll(
        poll_id=message.poll.id,
        chat_id=chat_id,
        correct_option=q["correct"],
        points=points,
        kind="trivia",
    )


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

async def quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_random_question(update.effective_chat.id, context)


async def daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌅 *Today's Daily Challenge!* Answer correctly to keep your streak alive.",
                                     parse_mode=ParseMode.MARKDOWN)
    await send_random_question(update.effective_chat.id, context, label="🌅 DAILY")


async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows = db.get_leaderboard(chat_id, limit=10)

    if not rows:
        await update.message.reply_text(
            "No scores yet in this chat! Run /quiz to get the first question out."
        )
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 *All-Time F1 Trivia Leaderboard*\n"]
    for i, row in enumerate(rows):
        name = row["first_name"] or row["username"] or f"User {row['user_id']}"
        prefix = medals[i] if i < 3 else f"{i + 1}."
        rank = config.get_rank(row["points"])
        lines.append(f"{prefix} *{name}* — {row['points']} pts ({rank})")

    lines.append("\nUse /weekly for this week's board, /mystats for your own numbers.")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def weekly_leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows = db.get_weekly_leaderboard(chat_id, limit=10)

    if not rows:
        await update.message.reply_text(
            "No points scored yet this week. Get in there with /quiz!"
        )
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["📅 *This Week's Leaderboard*\n"]
    for i, row in enumerate(rows):
        name = row["first_name"] or row["username"] or f"User {row['user_id']}"
        prefix = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{prefix} *{name}* — {row['points']} pts ({row['correct']} correct)")
    lines.append("\n🏆 Resets every Sunday — top scorer gets crowned Champion of the Week!")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def mystats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    stats = db.get_user_stats(chat_id, user.id)

    if not stats:
        await update.message.reply_text(
            "You haven't answered any questions in this chat yet. Try /quiz!"
        )
        return

    total = stats["correct"] + stats["wrong"]
    accuracy = (stats["correct"] / total * 100) if total else 0
    rank = config.get_rank(stats["points"])
    next_info = config.next_rank_info(stats["points"])
    next_line = (
        f"\n➡️ {next_info[0]} pts to *{next_info[1]}*" if next_info else "\n🏁 You've hit the top rank!"
    )

    badges = db.get_unlocked_badges(chat_id, user.id)
    badge_line = ", ".join(
        b["name"] for b in config.ACHIEVEMENTS + config.PREDICTION_ACHIEVEMENTS + config.DUEL_ACHIEVEMENTS
        if b["key"] in badges
    ) or "None yet — go answer some questions!"

    await update.message.reply_text(
        f"📊 *Your stats in this chat*\n"
        f"Rank: *{rank}*{next_line}\n\n"
        f"✅ Correct: {stats['correct']}  |  ❌ Wrong: {stats['wrong']}\n"
        f"🎯 Accuracy: {accuracy:.0f}%\n"
        f"🔥 Current streak: {stats['streak']}  |  🏅 Best streak: {stats['best_streak']}\n"
        f"📅 Daily streak: {stats['daily_streak']} days (best {stats['best_daily_streak']})\n"
        f"⚔️ Duels: {stats['duel_wins']}W-{stats['duel_losses']}L\n"
        f"💰 Total points: {stats['points']}\n\n"
        f"🎖 *Badges:* {badge_line}",
        parse_mode=ParseMode.MARKDOWN,
    )


def _autoquiz_job_name(chat_id: int) -> str:
    return f"autoquiz_{chat_id}"


async def _autoquiz_job_callback(context: ContextTypes.DEFAULT_TYPE):
    await send_random_question(context.job.chat_id, context)


async def autoquiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text(
            "Usage: /autoquiz <minutes>  (e.g. /autoquiz 30 for a question every 30 minutes)"
        )
        return

    try:
        minutes = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please give a whole number of minutes, e.g. /autoquiz 30")
        return

    if not (MIN_AUTOQUIZ_MINUTES <= minutes <= MAX_AUTOQUIZ_MINUTES):
        await update.message.reply_text(
            f"Please choose between {MIN_AUTOQUIZ_MINUTES} and {MAX_AUTOQUIZ_MINUTES} minutes."
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
        f"✅ Auto-quiz enabled! I'll post a random F1 question every {minutes} minute(s). "
        f"Use /stopquiz to turn this off."
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

    await update.message.reply_text("🛑 Auto-quiz stopped for this chat.")


# --------------------------------------------------------------------------
# Achievement checking (called after any correct trivia answer)
# --------------------------------------------------------------------------

async def check_and_announce_achievements(chat_id: int, user, stats: dict, context: ContextTypes.DEFAULT_TYPE):
    already = db.get_unlocked_badges(chat_id, user.id)
    newly_unlocked = config.check_trivia_achievements(stats, already)

    for ach in newly_unlocked:
        if db.unlock_badge(chat_id, user.id, ach["key"]):
            name = user.first_name or user.username or "Someone"
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🎖 *{name}* just unlocked *{ach['name']}*!\n_{ach['desc']}_",
                parse_mode=ParseMode.MARKDOWN,
            )


# --------------------------------------------------------------------------
# Poll answer grading (routes trivia vs duel polls)
# --------------------------------------------------------------------------

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    poll = db.get_active_poll(answer.poll_id)
    if poll is None or not answer.option_ids:
        return

    chosen = answer.option_ids[0]
    is_correct = chosen == poll["correct_option"]
    user = answer.user

    if poll["kind"] == "duel":
        # Duel polls are graded by duel_handlers; import locally to avoid a cycle.
        import duel_handlers
        await duel_handlers.handle_duel_answer(poll, user, is_correct, context)
        return

    stats = db.record_answer(
        chat_id=poll["chat_id"],
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        is_correct=is_correct,
        points=poll["points"],
    )

    if is_correct:
        await check_and_announce_achievements(poll["chat_id"], user, stats, context)
