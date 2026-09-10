"""
1v1 "Duel" mode: reply to someone's message with /challenge to start a
5-question head-to-head. Both players answer the same quiz polls; whoever
gets more correct after 5 rounds wins. Only the two duelists' answers count
toward the duel score (everyone else can still answer for fun/normal points).
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


def _duel_job_name(duel_id: int) -> str:
    return f"duel_{duel_id}"


async def challenge_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    challenger = update.effective_user

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "To challenge someone, *reply to one of their messages* with /challenge.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    opponent = update.message.reply_to_message.from_user

    if opponent.is_bot:
        await update.message.reply_text("You can't duel a bot. Try a real F1 fan! 🏁")
        return
    if opponent.id == challenger.id:
        await update.message.reply_text("You can't challenge yourself!")
        return

    existing = db.get_active_duel_for_chat(chat_id)
    if existing:
        await update.message.reply_text(
            "There's already a duel in progress in this chat. Wait for it to finish!"
        )
        return

    duel_id = db.create_duel(
        chat_id=chat_id,
        challenger_id=challenger.id,
        challenger_name=challenger.first_name or challenger.username or "Player 1",
        opponent_id=opponent.id,
        opponent_name=opponent.first_name or opponent.username or "Player 2",
    )

    await update.message.reply_text(
        f"⚔️ *DUEL!* {challenger.first_name} has challenged {opponent.first_name} to "
        f"{config.DUEL_ROUNDS} rounds of F1 trivia!\n\nFirst question coming up...",
        parse_mode=ParseMode.MARKDOWN,
    )

    await _send_duel_round(chat_id, duel_id, context)

    context.job_queue.run_repeating(
        _duel_round_job,
        interval=config.DUEL_GAP_SECONDS,
        first=config.DUEL_GAP_SECONDS,
        data=duel_id,
        chat_id=chat_id,
        name=_duel_job_name(duel_id),
    )


async def _send_duel_round(chat_id: int, duel_id: int, context: ContextTypes.DEFAULT_TYPE):
    duel = db.get_duel(duel_id)
    if not duel or duel["status"] != "active":
        return

    db.bump_duel_round(duel_id)
    duel = db.get_duel(duel_id)  # refresh with new round_number

    q = random.choice(QUESTIONS)
    message = await context.bot.send_poll(
        chat_id=chat_id,
        question=(
            f"⚔️ Duel Round {duel['round_number']}/{config.DUEL_ROUNDS} — "
            f"{duel['challenger_name']} vs {duel['opponent_name']}: {q['question']}"
        ),
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct"],
        explanation=q["explanation"],
        is_anonymous=False,
        open_period=config.DUEL_QUESTION_OPEN_SECONDS,
    )
    db.save_active_poll(
        poll_id=message.poll.id,
        chat_id=chat_id,
        correct_option=q["correct"],
        kind="duel",
        duel_id=duel_id,
        duel_round=duel["round_number"],
    )


async def _duel_round_job(context: ContextTypes.DEFAULT_TYPE):
    duel_id = context.job.data
    chat_id = context.job.chat_id
    duel = db.get_duel(duel_id)

    if not duel or duel["status"] != "active":
        context.job.schedule_removal()
        return

    if duel["round_number"] >= config.DUEL_ROUNDS:
        await _finish_duel(chat_id, duel_id, context)
        context.job.schedule_removal()
        return

    await _send_duel_round(chat_id, duel_id, context)


async def handle_duel_answer(poll: dict, user, is_correct: bool, context: ContextTypes.DEFAULT_TYPE):
    duel = db.get_duel(poll["duel_id"])
    if not duel or duel["status"] != "active":
        return
    if user.id not in (duel["challenger_id"], duel["opponent_id"]):
        return  # bystander answering just for fun, doesn't affect the duel
    if is_correct:
        db.add_duel_point(poll["duel_id"], user.id)


async def _finish_duel(chat_id: int, duel_id: int, context: ContextTypes.DEFAULT_TYPE):
    duel = db.get_duel(duel_id)
    db.finish_duel(duel_id)

    c_score, o_score = duel["challenger_score"], duel["opponent_score"]
    c_name, o_name = duel["challenger_name"], duel["opponent_name"]

    if c_score == o_score:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🤝 *Duel over!* {c_name} {c_score} - {o_score} {o_name}\n"
                f"It's a draw — rematch? Reply /challenge again!"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if c_score > o_score:
        winner_id, winner_name = duel["challenger_id"], c_name
        loser_id, loser_name = duel["opponent_id"], o_name
    else:
        winner_id, winner_name = duel["opponent_id"], o_name
        loser_id, loser_name = duel["challenger_id"], c_name

    db.record_duel_result(chat_id, winner_id, loser_id)

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"🏆 *Duel over!* {c_name} {c_score} - {o_score} {o_name}\n"
            f"*{winner_name} wins!* 🎉 Better luck next time, {loser_name}."
        ),
        parse_mode=ParseMode.MARKDOWN,
    )

    # Duel-related achievements for the winner
    stats = db.get_user_stats(chat_id, winner_id)
    already = db.get_unlocked_badges(chat_id, winner_id)
    for ach in config.DUEL_ACHIEVEMENTS:
        earned = (
            (ach["key"] == "duelist" and stats["duel_wins"] >= 1)
            or (ach["key"] == "gladiator" and stats["duel_wins"] >= 10)
        )
        if earned and ach["key"] not in already:
            if db.unlock_badge(chat_id, winner_id, ach["key"]):
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🎖 *{winner_name}* just unlocked *{ach['name']}*!\n_{ach['desc']}_",
                    parse_mode=ParseMode.MARKDOWN,
                )


async def duelstats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    stats = db.get_user_stats(chat_id, user.id)

    if not stats or (stats["duel_wins"] == 0 and stats["duel_losses"] == 0):
        await update.message.reply_text(
            "You haven't dueled anyone yet! Reply to someone's message with /challenge."
        )
        return

    total = stats["duel_wins"] + stats["duel_losses"]
    win_rate = (stats["duel_wins"] / total * 100) if total else 0
    await update.message.reply_text(
        f"⚔️ *Your duel record*\n"
        f"Wins: {stats['duel_wins']}  |  Losses: {stats['duel_losses']}\n"
        f"Win rate: {win_rate:.0f}%",
        parse_mode=ParseMode.MARKDOWN,
    )
