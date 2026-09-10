"""
GP podium prediction game: predict the top 3 finishers of an upcoming race.

Flow:
  1. Anyone starts a round:      /predict Singapore GP
  2. Everyone submits a pick:    /pick Verstappen, Norris, Leclerc
  3. An admin locks entries:     /lockpredictions   (optional - stops new picks)
  4. After the race, an admin
     enters the real result:     /setresult Verstappen, Norris, Leclerc
     -> bot auto-scores everyone and posts the results + updated leaderboard

Scoring (per predicted slot):
  - Exact position match  -> +10 pts
  - Right driver, wrong slot (still podium) -> +4 pts
  - Perfect podium (all 3 exact) -> +15 bonus on top
Points also count toward the user's overall rank/leaderboard.
"""

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
import database as db

logger = logging.getLogger(__name__)


async def _is_chat_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    if chat.type == "private":
        return True
    member = await context.bot.get_chat_member(chat.id, update.effective_user.id)
    return member.status in ("administrator", "creator")


def _parse_three(text: str):
    """Parses 'A, B, C' (or 'A,B,C') into a list of 3 stripped names, or None."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) != 3:
        return None
    return parts


async def predict_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text(
            "Usage: /predict <GP name>\nExample: /predict Singapore GP"
        )
        return

    existing = db.get_scoreable_round(chat_id)
    if existing:
        status_note = (
            "Use /pick to submit your podium."
            if existing["status"] == "open"
            else "It's locked — an admin needs to /setresult before a new round can start."
        )
        await update.message.reply_text(
            f"There's already a round for *{existing['gp_name']}* in progress. {status_note}",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    gp_name = " ".join(context.args)
    round_id = db.create_prediction_round(chat_id, gp_name, update.effective_user.id)

    await update.message.reply_text(
        f"🔮 *New Prediction Round: {gp_name}*\n\n"
        f"Everyone: predict the podium with:\n"
        f"`/pick Driver1, Driver2, Driver3`\n\n"
        f"Scoring: exact position = +{config.PREDICTION_EXACT_POSITION_POINTS} pts, "
        f"right driver/wrong slot = +{config.PREDICTION_WRONG_POSITION_POINTS} pts, "
        f"perfect podium bonus = +{config.PREDICTION_PERFECT_PODIUM_BONUS} pts!\n\n"
        f"(round #{round_id})",
        parse_mode=ParseMode.MARKDOWN,
    )


async def pick_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    round_ = db.get_open_round(chat_id)
    if not round_:
        await update.message.reply_text(
            "There's no open prediction round right now. Start one with /predict <GP name>."
        )
        return

    text = " ".join(context.args)
    picks = _parse_three(text)
    if not picks:
        await update.message.reply_text(
            "Usage: /pick Driver1, Driver2, Driver3\nExample: /pick Verstappen, Norris, Leclerc"
        )
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
        f"✅ Got it, {user.first_name}! Your podium for *{round_['gp_name']}*: "
        f"🥇 {picks[0]}  🥈 {picks[1]}  🥉 {picks[2]}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def predictions_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    round_ = db.get_scoreable_round(chat_id)

    if not round_:
        await update.message.reply_text("No open prediction round right now. Start one with /predict <GP name>.")
        return

    preds = db.get_predictions_for_round(round_["round_id"])
    names = [p["first_name"] or p["username"] or f"User {p['user_id']}" for p in preds]

    lines = [f"🔮 *{round_['gp_name']}* — status: {round_['status']}\n"]
    if names:
        lines.append(f"{len(names)} prediction(s) submitted so far:")
        lines.append(", ".join(names))
        lines.append("\n(Picks stay hidden until results are in — no peeking!)")
    else:
        lines.append("No predictions submitted yet. Use /pick Driver1, Driver2, Driver3")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


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
    await update.message.reply_text(
        f"🔒 Predictions for *{round_['gp_name']}* are now locked. No more picks accepted.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def setresult_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not await _is_chat_admin(update, context):
        await update.message.reply_text("Only chat admins can enter race results.")
        return

    # Find the most recent round that isn't already scored (open or locked)
    round_ = db.get_scoreable_round(chat_id)
    if not round_:
        await update.message.reply_text(
            "No open or locked prediction round found for this chat. "
            "Start one with /predict <GP name> first."
        )
        return

    text = " ".join(context.args)
    actual = _parse_three(text)
    if not actual:
        await update.message.reply_text(
            "Usage: /setresult Driver1, Driver2, Driver3  (actual P1, P2, P3)"
        )
        return

    db.score_round(round_["round_id"], actual[0], actual[1], actual[2])

    preds = db.get_predictions_for_round(round_["round_id"])
    if not preds:
        await update.message.reply_text(
            f"Result recorded for *{round_['gp_name']}*, but nobody submitted a prediction!",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    actual_lower = [a.lower() for a in actual]
    results_lines = [f"🏁 *Results are in for {round_['gp_name']}!*"]
    results_lines.append(f"🥇 {actual[0]}  🥈 {actual[1]}  🥉 {actual[2]}\n")

    scored = []
    for pred in preds:
        guesses = [pred["p1"], pred["p2"], pred["p3"]]
        points = 0
        exact_matches = 0
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
        db.add_bonus_points(
            chat_id, pred["user_id"], pred["username"], pred["first_name"], points
        )

        name = pred["first_name"] or pred["username"] or f"User {pred['user_id']}"
        tag = " 🏆 PERFECT PODIUM!" if perfect else ""
        scored.append((points, f"*{name}*: {points} pts{tag}"))

        if perfect:
            already = db.get_unlocked_badges(chat_id, pred["user_id"])
            if "podium_perfect" not in already and db.unlock_badge(chat_id, pred["user_id"], "podium_perfect"):
                ach = next(a for a in config.PREDICTION_ACHIEVEMENTS if a["key"] == "podium_perfect")
                results_lines.append(f"🎖 *{name}* just unlocked *{ach['name']}*!")

        rounds_played = db.count_rounds_played(chat_id, pred["user_id"])
        already = db.get_unlocked_badges(chat_id, pred["user_id"])
        if rounds_played >= 5 and "prediction_pro" not in already:
            if db.unlock_badge(chat_id, pred["user_id"], "prediction_pro"):
                ach = next(a for a in config.PREDICTION_ACHIEVEMENTS if a["key"] == "prediction_pro")
                results_lines.append(f"🎖 *{name}* just unlocked *{ach['name']}*!")

    scored.sort(key=lambda x: x[0], reverse=True)
    results_lines.extend(line for _, line in scored)

    await update.message.reply_text("\n".join(results_lines), parse_mode=ParseMode.MARKDOWN)


async def predictionboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows = db.get_prediction_leaderboard(chat_id, limit=10)

    if not rows:
        await update.message.reply_text(
            "No scored prediction rounds yet. Start one with /predict <GP name>!"
        )
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🔮 *Prediction Game Leaderboard*\n"]
    for i, row in enumerate(rows):
        name = row["first_name"] or row["username"] or f"User {row['user_id']}"
        prefix = medals[i] if i < 3 else f"{i + 1}."
        lines.append(
            f"{prefix} *{name}* — {row['total_points']} pts across {row['rounds_played']} round(s)"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
