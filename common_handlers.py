"""/start and /help commands."""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏁 *Welcome to the F1 Trivia Bot!*\n\n"
        "I ask random Formula 1 questions — history, records, drivers, teams, "
        "rules and iconic memes — track a leaderboard, hand out badges, run "
        "1v1 duels, and let you predict race podiums for bonus points.\n\n"
        "Add me to a group and try /quiz to get started, or /help to see "
        "everything I can do.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*🎮 Trivia*\n"
        "/quiz — ask one random F1 question now\n"
        "/daily — today's daily challenge (keep your daily streak alive!)\n"
        "/leaderboard — this chat's all-time top scorers\n"
        "/weekly — this week's leaderboard (resets Sundays)\n"
        "/mystats — your rank, points, streaks and badges\n"
        "/autoquiz <minutes> — auto-post a question every N minutes\n"
        "/stopquiz — stop auto-quiz\n\n"
        "*⚔️ Duels*\n"
        "Reply to someone's message with /challenge to start a 5-question 1v1\n"
        "/duelstats — your duel win/loss record\n\n"
        "*🔮 Race Predictions*\n"
        "/predict <GP name> — start a podium prediction round\n"
        "/pick Driver1, Driver2, Driver3 — submit your P1/P2/P3 guess\n"
        "/predictions — see who's picked so far (picks stay hidden)\n"
        "/lockpredictions — (admin) close entries before the race\n"
        "/setresult Driver1, Driver2, Driver3 — (admin) enter real results & score everyone\n"
        "/predictionboard — all-time prediction game leaderboard\n\n"
        "/help — this message",
        parse_mode=ParseMode.MARKDOWN,
    )
