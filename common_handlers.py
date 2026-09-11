"""/start and /help commands."""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import ui


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [
        "Trivia across F1 history, records, drivers, teams, rules and iconic",
        "moments. Points, ranks, badges, 1v1 duels, and a podium prediction",
        "game tied to the real race calendar.",
        "",
        "Start with /quiz. See /help for everything else.",
    ]
    text = ui.section("F1 Trivia Bot", lines)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [
        "*Trivia*",
        "/quiz — random F1 question",
        "/daily — daily challenge",
        "/leaderboard — all-time top scorers",
        "/weekly — this week's board (resets Sundays)",
        "/mystats — your rank, points, streaks, badges",
        "/autoquiz <minutes> — auto-post questions",
        "/stopquiz — stop auto-quiz",
        "",
        "*Duels*",
        "Reply to a message with /challenge for a 5-question 1v1",
        "/duelstats — your duel record",
        "",
        "*Predictions*",
        "/nextrace — the real next race on the calendar",
        "/predict — open a podium round for it (auto-detected)",
        "/pick Driver1, Driver2, Driver3 — submit your podium",
        "/predictions — who's entered so far",
        "/lockpredictions — (admin) close entries",
        "/setresult Driver1, Driver2, Driver3 — (admin) manual scoring fallback",
        "/predictionboard — prediction game leaderboard",
        "",
        "Rounds normally open, lock, and score themselves automatically",
        "based on the real F1 calendar and race results.",
    ]
    text = "\n".join(lines)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
