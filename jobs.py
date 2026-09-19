"""
Background jobs:
  - Weekly reset: every Sunday, announce a "Champion of the Week" per chat
    and clear the weekly leaderboard.
  - Startup restore: re-arm auto-quiz jobs that were running before a restart.
  - Prediction automation: for any chat that has used a prediction command,
    automatically open a round for the next real GP, lock it on race day,
    and fetch the real result to auto-score it once the race is over.
"""

import datetime
import logging

from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes

import database as db
import prediction_handlers
import race_calendar
import results_api
import trivia_handlers
import ui

logger = logging.getLogger(__name__)

WEEKLY_RESET_TIME = datetime.time(hour=20, minute=0)  # 20:00 UTC every Sunday
PREDICTION_CHECK_INTERVAL_MINUTES = 60
AUTO_OPEN_DAYS_BEFORE = 5
LOCK_HOUR_UTC = 11  # predictions auto-lock at 11:00 UTC on race day


async def weekly_reset_job(context: ContextTypes.DEFAULT_TYPE):
    for chat_id in db.get_all_chats_with_scores():
        rows = db.get_weekly_leaderboard(chat_id, limit=3)
        if rows and rows[0]["points"] > 0:
            lines = []
            for i, row in enumerate(rows):
                name = row["first_name"] or row["username"] or f"User {row['user_id']}"
                lines.append(ui.rank_line(i, name, f"{row['points']} pts"))
            text = ui.section("Champion of the Week", lines)
            text += "\n\nThe weekly board resets now."
            try:
                await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
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


async def prediction_maintenance_job(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.utcnow()
    today = now.date()
    race = race_calendar.get_next_race(today)

    for chat_id in db.get_prediction_enabled_chats():
        existing = db.get_scoreable_round(chat_id)

        if existing:
            existing_race = race_calendar.get_race_by_name(existing["gp_name"])

            if existing["status"] == "open":
                if existing_race and now >= datetime.datetime.combine(
                    existing_race.race_date, datetime.time(hour=LOCK_HOUR_UTC)
                ):
                    db.lock_round(existing["round_id"])
                    try:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"Locked — {existing['gp_name']} predictions are closed. Results incoming after the race.",
                        )
                    except Exception as e:
                        logger.warning("Couldn't announce auto-lock in %s: %s", chat_id, e)

            elif existing["status"] == "locked" and existing_race:
                top3 = results_api.get_top3_for_round(existing_race.race_date.year, existing_race.round)
                if top3:
                    try:
                        await prediction_handlers.finalize_round(chat_id, existing, top3, context)
                    except Exception as e:
                        logger.warning("Auto-scoring failed in %s: %s", chat_id, e)
                # else: result not published yet (or API hiccup) — retry next cycle;
                # an admin can always /setresult manually in the meantime.

            continue  # never open a new round while one is unresolved

        if race and race_calendar.days_until(race, today) <= AUTO_OPEN_DAYS_BEFORE:
            round_id = db.create_prediction_round(chat_id, race.name, created_by=None)
            lines = [
                "Submit your podium with:",
                "`/pick Driver1, Driver2, Driver3`",
                f"Round #{round_id}",
            ]
            text = ui.section(f"Prediction Round Open — {race.name}", lines)
            try:
                await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                logger.warning("Couldn't announce auto-open in %s: %s", chat_id, e)


def schedule_recurring_jobs(application: Application):
    # days=(6,) -> Sunday. PTB's JobQueue follows datetime.date.weekday():
    # Monday=0 ... Sunday=6.
    application.job_queue.run_daily(
        weekly_reset_job,
        time=WEEKLY_RESET_TIME,
        days=(6,),
        name="weekly_reset",
    )
    application.job_queue.run_repeating(
        prediction_maintenance_job,
        interval=PREDICTION_CHECK_INTERVAL_MINUTES * 60,
        first=30,
        name="prediction_maintenance",
    )
