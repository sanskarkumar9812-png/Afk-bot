"""
GP podium prediction game — now calendar-aware.

/predict with no arguments automatically targets the real next (or
currently in-progress) race weekend from `race_calendar.py`. A round for
that GP can also be opened/locked/scored automatically by the maintenance
job in `jobs.py`; the commands below remain available for manual control
and as a fallback if the automatic result fetch ever fails.

Scoring (per predicted slot):
  - Exact position match            -> +10 pts
  - Right driver, wrong slot        -> +4 pts
  - Perfect podium (all 3 exact)    -> +15 bonus on top
Points also count toward the user's overall rank/leaderboard.
"""

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
import database as db
import race_calendar
import ui

logger = logging.getLogger(__name__)


async def _is_chat_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    if chat.type == "private":
        return True
    member = await context.bot.get_chat_member(chat.id, update.effective_user.id)
    return member.status in ("administrator", "creator")


def _parse_three(text: str):
    parts = [p.strip() for p in text.split(",") if p.strip()]
    return parts if len(parts) == 3 else None


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

async def nextrace_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db.set_predictions_enabled(chat_id, True)

    race = race_calendar.get_next_race()
    if race is None:
        await update.message.reply_text("No more races left on this season's calendar.")
        return

    days = race_calendar.days_until(race)
    when = "This is race week." if days <= 3 else f"In {days} days."

    lines = [
        f"Round {race.round}: {race.name}",
        f"Location: {race.location}",
        f"Race day: {race.race_date.strftime('%-d %B %Y')}",
        when,
    ]
    text = ui.section("Next Race", lines)
    text += "\n\nUse /predict to open (or check) the podium prediction round for this race."
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def predict_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db.set_predictions_enabled(chat_id, True)

    existing = db.get_scoreable_round(chat_id)
    if existing:
        note = (
            "Submit your podium with /pick Driver1, Driver2, Driver3."
            if existing["status"] == "open"
            else "Entries are locked — results will be posted once the race finishes."
        )
        await update.message.reply_text(
            f"There's already a round open for *{existing['gp_name']}*.\n{note}",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if context.args:
        gp_name = " ".join(context.args)  # manual override
    else:
        race = race_calendar.get_next_race()
        if race is None:
            await update.message.reply_text("No more races left on this season's calendar.")
            return
        gp_name = race.name

    round_id = db.create_prediction_round(chat_id, gp_name, update.effective_user.id)

    lines = [
        f"Predict the podium with:",
        "`/pick Driver1, Driver2, Driver3`",
        "",
        f"Exact position: +{config.PREDICTION_EXACT_POSITION_POINTS} pts",
        f"Right driver, wrong slot: +{config.PREDICTION_WRONG_POSITION_POINTS} pts",
        f"Perfect podium bonus: +{config.PREDICTION_PERFECT_PODIUM_BONUS} pts",
    ]
    text = ui.section(f"Prediction Round Open — {gp_name}", lines)
    text += f"\n\nRound #{round_id}"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def pick_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    round_ = db.get_open_round(chat_id)
    if not round_:
        await update.message.reply_text("No open prediction round. Start one with /predict.")
        return

    picks = _parse_three(" ".join(context.args))
    if not picks:
        await update.message.reply_text("Usage: /pick Driver1, Driver2, Driver3")
        return

    db.submit_prediction(
        round_id=round_["round_id"],
        chat_id=chat_id,
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        p1=picks[0],
        p2=picks[1],
        p3=picks[2],
    )

    await update.message.reply_text(
        f"Saved — your podium for *{round_['gp_name']}*: {picks[0]} / {picks[1]} / {picks[2]}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def predictions_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    round_ = db.get_scoreable_round(chat_id)

    if not round_:
        await update.message.reply_text("No open prediction round. Start one with /predict.")
        return

    preds = db.get_predictions_for_round(round_["round_id"])
    names = [p["first_name"] or p["username"] or f"User {p['user_id']}" for p in preds]

    lines = [f"Status: {round_['status']}", f"Entries: {len(names)}"]
    if names:
        lines.append(", ".join(names))
        lines.append("Picks stay hidden until results are scored.")

    text = ui.section(round_["gp_name"], lines)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def lockpredictions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not await _is_chat_admin(update, context):
        await update.message.reply_text("Only chat admins can lock predictions.")
        return

    round_ = db.get_open_round(chat_id)
    if not round_:
        await update.message.reply_text("No open prediction round to lock.")
        return

    db.lock_round(round_["round_id"])
    await update.message.reply_text(f"Locked — {round_['gp_name']} predictions are closed.")


async def setresult_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not await _is_chat_admin(update, context):
        await update.message.reply_text("Only chat admins can enter race results.")
        return

    round_ = db.get_scoreable_round(chat_id)
    if not round_:
        await update.message.reply_text("No open or locked prediction round found.")
        return

    actual = _parse_three(" ".join(context.args))
    if not actual:
        await update.message.reply_text("Usage: /setresult Driver1, Driver2, Driver3")
        return

    await finalize_round(chat_id, round_, actual, context)


async def predictionboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows = db.get_prediction_leaderboard(chat_id, limit=10)

    if not rows:
        await update.message.reply_text("No scored rounds yet. Start one with /predict.")
        return

    lines = []
    for i, row in enumerate(rows):
        name = row["first_name"] or row["username"] or f"User {row['user_id']}"
        lines.append(ui.rank_line(i, name, f"{row['total_points']} pts / {row['rounds_played']} round(s)"))

    text = ui.section("Prediction Leaderboard", lines)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# --------------------------------------------------------------------------
# Shared scoring logic — used by /setresult AND the automatic results job
# --------------------------------------------------------------------------

async def finalize_round(chat_id: int, round_: dict, actual: list, context: ContextTypes.DEFAULT_TYPE):
    """Scores every prediction in `round_` against `actual` = [p1, p2, p3]
    (driver family names), updates the DB, and announces the outcome."""
    db.score_round(round_["round_id"], actual[0], actual[1], actual[2])
    preds = db.get_predictions_for_round(round_["round_id"])

    if not preds:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Result recorded for {round_['gp_name']}, but nobody submitted a prediction.",
        )
        return

    actual_lower = [a.lower() for a in actual]
    lines = [f"{actual[0]} / {actual[1]} / {actual[2]}", ""]
    badge_lines = []
    scored = []

    for pred in preds:
        guesses = [pred["p1"], pred["p2"], pred["p3"]]
        points, exact_matches = 0, 0
        for i, guess in enumerate(guesses):
            if guess.lower() == actual_lower[i]:
                points += config.PREDICTION_EXACT_POSITION_POINTS
                exact_matches += 1
            elif guess.lower() in actual_lower:
                points += config.PREDICTION_WRONG_POSITION_POINTS

        perfect = exact_matches == 3
        if perfect:
            points += config.PREDICTION_PERFECT_PODIUM_BONUS

        db.set_prediction_points(round_["round_id"], pred["user_id"], points)
        db.add_bonus_points(chat_id, pred["user_id"], pred["username"], pred["first_name"], points)

        name = pred["first_name"] or pred["username"] or f"User {pred['user_id']}"
        tag = " — perfect podium" if perfect else ""
        scored.append((points, f"{name}: {points} pts{tag}"))

        already = db.get_unlocked_badges(chat_id, pred["user_id"])
        if perfect and "podium_perfect" not in already and db.unlock_badge(chat_id, pred["user_id"], "podium_perfect"):
            ach = next(a for a in config.PREDICTION_ACHIEVEMENTS if a["key"] == "podium_perfect")
            badge_lines.append(f"Badge unlocked — {name}: {ach['name']}")

        rounds_played = db.count_rounds_played(chat_id, pred["user_id"])
        if rounds_played >= 5 and "prediction_pro" not in already and db.unlock_badge(chat_id, pred["user_id"], "prediction_pro"):
            ach = next(a for a in config.PREDICTION_ACHIEVEMENTS if a["key"] == "prediction_pro")
            badge_lines.append(f"Badge unlocked — {name}: {ach['name']}")

    scored.sort(key=lambda x: x[0], reverse=True)
    lines.extend(line for _, line in scored)
    lines.extend(badge_lines)

    text = ui.section(f"Results — {round_['gp_name']}", lines)
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
