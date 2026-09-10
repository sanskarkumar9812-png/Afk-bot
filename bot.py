"""
F1 Trivia, Duels & Predictions Bot for Telegram
=================================================
See README.md for full setup instructions.

Quick start:
    pip install -r requirements.txt
    export BOT_TOKEN="123456:ABC-your-token-here"
    python bot.py
"""

import logging
import os

from telegram import Update
from telegram.ext import Application, CommandHandler, PollAnswerHandler

import common_handlers
import database as db
import duel_handlers
import jobs
import prediction_handlers
import trivia_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def _post_init(application: Application):
    await jobs.restore_autoquiz_jobs(application)
    jobs.schedule_recurring_jobs(application)


def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit(
            "Set the BOT_TOKEN environment variable with your token from @BotFather.\n"
            "Example: export BOT_TOKEN='123456:ABC-your-token-here'"
        )

    db.init_db()

    application = Application.builder().token(token).post_init(_post_init).build()

    # Core / help
    application.add_handler(CommandHandler("start", common_handlers.start_cmd))
    application.add_handler(CommandHandler("help", common_handlers.help_cmd))

    # Trivia
    application.add_handler(CommandHandler("quiz", trivia_handlers.quiz_cmd))
    application.add_handler(CommandHandler("daily", trivia_handlers.daily_cmd))
    application.add_handler(CommandHandler("leaderboard", trivia_handlers.leaderboard_cmd))
    application.add_handler(CommandHandler("weekly", trivia_handlers.weekly_leaderboard_cmd))
    application.add_handler(CommandHandler("mystats", trivia_handlers.mystats_cmd))
    application.add_handler(CommandHandler("autoquiz", trivia_handlers.autoquiz_cmd))
    application.add_handler(CommandHandler("stopquiz", trivia_handlers.stopquiz_cmd))

    # Duels
    application.add_handler(CommandHandler("challenge", duel_handlers.challenge_cmd))
    application.add_handler(CommandHandler("duelstats", duel_handlers.duelstats_cmd))

    # Predictions
    application.add_handler(CommandHandler("predict", prediction_handlers.predict_cmd))
    application.add_handler(CommandHandler("pick", prediction_handlers.pick_cmd))
    application.add_handler(CommandHandler("predictions", prediction_handlers.predictions_status_cmd))
    application.add_handler(CommandHandler("lockpredictions", prediction_handlers.lockpredictions_cmd))
    application.add_handler(CommandHandler("setresult", prediction_handlers.setresult_cmd))
    application.add_handler(CommandHandler("predictionboard", prediction_handlers.predictionboard_cmd))

    # All poll answers (trivia + duel) route through one handler that dispatches
    application.add_handler(PollAnswerHandler(trivia_handlers.handle_poll_answer))

    logger.info("F1 Quiz Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
