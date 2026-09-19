"""
1v1 "Duel" mode.

Flow:
  1. Reply to someone's message with /challenge — they get an Accept/Decline
     prompt (nothing starts until they respond).
  2. On Accept, a 5-question head-to-head begins, rendered with the same
     button-based quiz engine used for regular trivia, plus a visible
     countdown that ticks down on each question.
  3. As soon as BOTH duelists have answered a question, it closes and the
     next one is sent immediately — no waiting out the full timer if
     everyone's already responded.

Only the two duelists' answers count toward the duel score — everyone else
in the chat can still answer the same buttons for fun/normal trivia points.
"""

import logging
import random

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

import config
import database as db
import quiz_engine
import ui
from questions import QUESTIONS

logger = logging.getLogger(__name__)


def _close_job_name(session_id: int) -> str:
    return f"duel_close_{session_id}"


def _tick_job_name(session_id: int) -> str:
    return f"duel_tick_{session_id}"


def _invite_expire_job_name(invite_id: int) -> str:
    return f"invite_expire_{invite_id}"


# --------------------------------------------------------------------------
# Challenge -> Accept/Decline invite
# --------------------------------------------------------------------------

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

    if db.get_active_duel_for_chat(chat_id):
        await update.message.reply_text("There's already a duel in progress in this chat.")
        return
    if db.get_pending_invite_for_chat(chat_id):
        await update.message.reply_text("There's already a pending challenge in this chat.")
        return

    challenger_name = challenger.first_name or challenger.username or "Player 1"
    opponent_name = opponent.first_name or opponent.username or "Player 2"

    invite_id = db.create_duel_invite(chat_id, challenger.id, challenger_name, opponent.id, opponent_name)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Accept", callback_data=f"dc:{invite_id}:accept"),
        InlineKeyboardButton("❌ Decline", callback_data=f"dc:{invite_id}:decline"),
    ]])
    text = (
        f"{challenger_name} has challenged {opponent_name} to a {config.DUEL_ROUNDS}-question F1 duel.\n\n"
        f"{opponent_name}, do you accept?"
    )
    message = await update.message.reply_text(text, reply_markup=keyboard)
    db.set_invite_message_id(invite_id, message.message_id)

    context.job_queue.run_once(
        _invite_expire_job,
        when=config.DUEL_INVITE_TIMEOUT_SECONDS,
        data=invite_id,
        chat_id=chat_id,
        name=_invite_expire_job_name(invite_id),
    )


async def _invite_expire_job(context: ContextTypes.DEFAULT_TYPE):
    invite_id = context.job.data
    invite = db.get_duel_invite(invite_id)
    if not invite or invite["status"] != "pending":
        return

    db.set_invite_status(invite_id, "expired")
    try:
        await context.bot.edit_message_text(
            chat_id=invite["chat_id"],
            message_id=invite["message_id"],
            text=f"Challenge from {invite['challenger_name']} to {invite['opponent_name']} expired — no response in time.",
        )
    except TelegramError as e:
        logger.info("Couldn't edit expired invite %s: %s", invite_id, e)


async def handle_invite_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""

    try:
        _, iid_str, action = data.split(":")
        invite_id = int(iid_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    invite = db.get_duel_invite(invite_id)
    if not invite or invite["status"] != "pending":
        await query.answer("This challenge is no longer active.")
        return

    user = query.from_user
    if user.id != invite["opponent_id"]:
        await query.answer("This challenge isn't addressed to you.")
        return

    for job in context.job_queue.get_jobs_by_name(_invite_expire_job_name(invite_id)):
        job.schedule_removal()

    if action == "decline":
        db.set_invite_status(invite_id, "declined")
        await query.answer("Challenge declined.")
        try:
            await context.bot.edit_message_text(
                chat_id=invite["chat_id"],
                message_id=invite["message_id"],
                text=f"{invite['opponent_name']} declined the challenge from {invite['challenger_name']}.",
            )
        except TelegramError as e:
            logger.info("Couldn't edit declined invite %s: %s", invite_id, e)
        return

    # Accepted
    db.set_invite_status(invite_id, "accepted")
    await query.answer("Challenge accepted!")

    duel_id = db.create_duel(
        chat_id=invite["chat_id"],
        challenger_id=invite["challenger_id"],
        challenger_name=invite["challenger_name"],
        opponent_id=invite["opponent_id"],
        opponent_name=invite["opponent_name"],
    )

    try:
        await context.bot.edit_message_text(
            chat_id=invite["chat_id"],
            message_id=invite["message_id"],
            text=(
                f"{invite['opponent_name']} accepted! {invite['challenger_name']} vs "
                f"{invite['opponent_name']} — {config.DUEL_ROUNDS} questions, starting now."
            ),
        )
    except TelegramError as e:
        logger.info("Couldn't edit accepted invite %s: %s", invite_id, e)

    await _send_duel_round(invite["chat_id"], duel_id, context)


# --------------------------------------------------------------------------
# Duel rounds: send, tick countdown, close (naturally or early), advance
# --------------------------------------------------------------------------

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
        seconds_left=config.DUEL_QUESTION_OPEN_SECONDS,
    )

    context.job_queue.run_once(
        _duel_round_close_job,
        when=config.DUEL_QUESTION_OPEN_SECONDS,
        data=session_id,
        chat_id=chat_id,
        name=_close_job_name(session_id),
    )
    _schedule_countdown_ticks(context, session_id, chat_id, config.DUEL_QUESTION_OPEN_SECONDS)


def _schedule_countdown_ticks(context: ContextTypes.DEFAULT_TYPE, session_id: int, chat_id: int, total_seconds: int):
    tick = config.DUEL_TIMER_TICK_SECONDS
    when = tick
    remaining = total_seconds - tick
    while remaining > 0:
        context.job_queue.run_once(
            _duel_timer_tick, when=when, data=(session_id, remaining), chat_id=chat_id,
            name=_tick_job_name(session_id),
        )
        when += tick
        remaining -= tick


async def _duel_timer_tick(context: ContextTypes.DEFAULT_TYPE):
    session_id, remaining = context.job.data
    await quiz_engine.refresh_message(session_id, context, seconds_left=remaining)


def _cancel_duel_timers(context: ContextTypes.DEFAULT_TYPE, session_id: int):
    for name in (_close_job_name(session_id), _tick_job_name(session_id)):
        for job in context.job_queue.get_jobs_by_name(name):
            job.schedule_removal()


async def _duel_round_close_job(context: ContextTypes.DEFAULT_TYPE):
    await _advance_after_round(context.job.data, context)


async def _advance_after_round(session_id: int, context: ContextTypes.DEFAULT_TYPE):
    session = await quiz_engine.close_quiz_session(session_id, context)
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
    """Called by quiz_engine right after someone answers a duel-flagged
    question. If both duelists have now answered, closes the round early
    and advances immediately instead of waiting out the timer."""
    duel = db.get_duel(session["duel_id"])
    if not duel or duel["status"] != "active":
        return
    if user.id not in (duel["challenger_id"], duel["opponent_id"]):
        return  # bystander answering just for fun, doesn't affect the duel

    if is_correct:
        db.add_duel_point(session["duel_id"], user.id)

    answers = db.get_quiz_answers(session["session_id"])
    answered_ids = {a["user_id"] for a in answers}
    if duel["challenger_id"] in answered_ids and duel["opponent_id"] in answered_ids:
        _cancel_duel_timers(context, session["session_id"])
        await _advance_after_round(session["session_id"], context)


# --------------------------------------------------------------------------
# Finishing up
# --------------------------------------------------------------------------

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
