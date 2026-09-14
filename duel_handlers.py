"""
1v1 "Duel" mode: reply to someone's message with /challenge to start a
5-question head-to-head, rendered with the same button-based quiz engine
used for regular trivia. Only the two duelists' answers count toward the
duel score — everyone else in the chat can still answer for fun/normal points.

Rounds are chained: each round's close callback immediately sends the next
one (or finishes the duel), rather than running on a fixed repeating timer.
"""

import logging
import random

from telegram import Update
from telegram.ext import ContextTypes

import config
import database as db
import quiz_engine
import ui
from questions import QUESTIONS

logger = logging.getLogger(__name__)


async def challenge_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    challenger = update.effective_user

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "To challenge someone, reply to one of their messages with /challenge."
        )
        return

    opponent = update.message.reply_to_message.from_user

    if opponent.is_bot:
        await update.message.reply_text("You can't duel a bot — pick a real F1 fan in the chat.")
        return
    if opponent.id == challenger.id:
        await update.message.reply_text("You can't challenge yourself!")
        return

    existing = db.get_active_duel_for_chat(chat_id)
    if existing:
        await update.message.reply_text("There's already a duel in progress in this chat.")
        return

    duel_id = db.create_duel(
        chat_id=chat_id,
        challenger_id=challenger.id,
        challenger_name=challenger.first_name or challenger.username or "Player 1",
        opponent_id=opponent.id,
        opponent_name=opponent.first_name or opponent.username or "Player 2",
    )

    await update.message.reply_text(
        f"Duel started: {challenger.first_name} vs {opponent.first_name} — "
        f"{config.DUEL_ROUNDS} questions. First one coming up."
    )

    await _send_duel_round(chat_id, duel_id, context)


async def _send_duel_round(chat_id: int, duel_id: int, context: ContextTypes.DEFAULT_TYPE):
    duel = db.get_duel(duel_id)
    if not duel or duel["status"] != "active":
        return

    db.bump_duel_round(duel_id)
    duel = db.get_duel(duel_id)  # refresh with new round_number

    q = random.choice(QUESTIONS)
    label = f"Duel {duel['round_number']}/{config.DUEL_ROUNDS}: {duel['challenger_name']} vs {duel['opponent_name']}"

    session_id = await quiz_engine.send_quiz_message(
        chat_id=chat_id, question=q, points=0, context=context,
        kind="duel", duel_id=duel_id, duel_round=duel["round_number"], header_label=label,
    )
    context.job_queue.run_once(
        _duel_round_close_job,
        when=config.DUEL_QUESTION_OPEN_SECONDS,
        data=session_id,
        chat_id=chat_id,
        name=f"duel_close_{session_id}",
    )


async def _duel_round_close_job(context: ContextTypes.DEFAULT_TYPE):
    session = await quiz_engine.close_quiz_session(context.job.data, context)
    if not session or session["kind"] != "duel":
        return

    duel_id = session["duel_id"]
    duel = db.get_duel(duel_id)
    if not duel or duel["status"] != "active":
        return

    if duel["round_number"] >= config.DUEL_ROUNDS:
        await _finish_duel(session["chat_id"], duel_id, context)
    else:
        await _send_duel_round(session["chat_id"], duel_id, context)


async def handle_duel_answer(session: dict, user, is_correct: bool, context: ContextTypes.DEFAULT_TYPE):
    """Called by quiz_engine when someone answers a duel-flagged question."""
    duel = db.get_duel(session["duel_id"])
    if not duel or duel["status"] != "active":
        return
    if user.id not in (duel["challenger_id"], duel["opponent_id"]):
        return  # bystander answering just for fun, doesn't affect the duel
    if is_correct:
        db.add_duel_point(session["duel_id"], user.id)


async def _finish_duel(chat_id: int, duel_id: int, context: ContextTypes.DEFAULT_TYPE):
    duel = db.get_duel(duel_id)
    db.finish_duel(duel_id)

    c_score, o_score = duel["challenger_score"], duel["opponent_score"]
    c_name, o_name = duel["challenger_name"], duel["opponent_name"]

    if c_score == o_score:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Duel finished: {c_name} {c_score} – {o_score} {o_name}. Draw.",
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
        text=f"Duel finished: {c_name} {c_score} – {o_score} {o_name}. {winner_name} wins.",
    )

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
                    text=f"Badge unlocked — {winner_name}: *{ach['name']}*\n{ach['desc']}",
                    parse_mode="Markdown",
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
    text = ui.section(
        "Duel Record",
        [f"Wins: {stats['duel_wins']}", f"Losses: {stats['duel_losses']}", f"Win rate: {win_rate:.0f}%"],
    )
    await update.message.reply_text(text, parse_mode="Markdown")
