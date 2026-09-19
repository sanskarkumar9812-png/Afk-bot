"""
Custom quiz engine: renders questions as a plain message + inline keyboard
buttons (A/B/C/D) instead of Telegram's native quiz-poll type, so the
message can show a clean header, an optional live countdown, live
"who's answered" lines, and a timed reveal.

Important platform limitation: Telegram's Bot API does not support colored
button backgrounds. Buttons always render in the client's default style.

Used by both trivia_handlers.py (regular questions) and duel_handlers.py
(1v1 duels) so the two share one consistent look and one code path for
sending/answering/closing a question.
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

import database as db

logger = logging.getLogger(__name__)

LETTERS = ["A", "B", "C", "D", "E", "F"]

CATEGORY_TAGS = {
    "history": "History",
    "records": "Records",
    "drivers": "Drivers",
    "teams": "Teams",
    "rules": "Rules",
    "meme": "Iconic Moments",
}
DIFFICULTY_TAGS = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}


def _build_text(session: dict, answers: list, closed: bool, seconds_left: int = None) -> str:
    tag = CATEGORY_TAGS.get(session["category"], session["category"] or "F1")
    difficulty = DIFFICULTY_TAGS.get(session["difficulty"], session["difficulty"] or "")
    label_part = f"{session['header_label']} · " if session.get("header_label") else ""

    lines = [f"🧠 *Trivia* · {label_part}_{tag} ({difficulty})_"]
    if not closed and seconds_left is not None:
        lines.append(f"⏱ {seconds_left}s remaining")
    lines.append("")
    lines.append(session["question_text"])

    if answers:
        lines.append("")
        for a in answers:
            mark = "✅" if a["is_correct"] else "❌"
            label = "Answered correctly" if a["is_correct"] else "Answered incorrectly"
            name = f"@{a['username']}" if a["username"] else (a["first_name"] or "Someone")
            lines.append(f"{mark} _{label}:_ {name}")

    if closed:
        lines.append("")
        lines.append("⏰ *Time's up!*")
        correct_text = session["options"][session["correct_option"]]
        lines.append(f"✅ *Answer:* {correct_text}")

    return "\n".join(lines)


def _build_keyboard(session: dict, closed: bool) -> InlineKeyboardMarkup:
    rows = []
    for idx, option in enumerate(session["options"]):
        letter = LETTERS[idx] if idx < len(LETTERS) else str(idx + 1)
        if closed:
            prefix = "✅ " if idx == session["correct_option"] else ""
            rows.append([InlineKeyboardButton(f"{prefix}{letter}. {option}", callback_data="noop")])
        else:
            rows.append([
                InlineKeyboardButton(
                    f"{letter}. {option}", callback_data=f"qa:{session['session_id']}:{idx}"
                )
            ])
    return InlineKeyboardMarkup(rows)


async def send_quiz_message(chat_id: int, question: dict, points: int, context: ContextTypes.DEFAULT_TYPE,
                             kind: str = "trivia", duel_id=None, duel_round=None, header_label: str = None,
                             seconds_left: int = None) -> int:
    """Sends a new question and returns its session_id."""
    session_id = db.create_quiz_session(
        chat_id=chat_id,
        kind=kind,
        question_text=question["question"],
        options=question["options"],
        correct_option=question["correct"],
        points=points,
        category=question.get("category"),
        difficulty=question.get("difficulty"),
        duel_id=duel_id,
        duel_round=duel_round,
        header_label=header_label,
    )
    session = db.get_quiz_session(session_id)
    text = _build_text(session, answers=[], closed=False, seconds_left=seconds_left)
    markup = _build_keyboard(session, closed=False)

    try:
        message = await context.bot.send_message(
            chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup
        )
    except TelegramError as e:
        logger.warning("Failed to send quiz message to %s: %s", chat_id, e)
        raise

    db.set_session_message_id(session_id, message.message_id)
    return session_id


async def refresh_message(session_id: int, context: ContextTypes.DEFAULT_TYPE, seconds_left: int = None):
    """Re-renders an still-open question in place — used for the live
    countdown. No-ops quietly if the session has already closed."""
    session = db.get_quiz_session(session_id)
    if not session or session["status"] != "open":
        return session

    answers = db.get_quiz_answers(session_id)
    text = _build_text(session, answers, closed=False, seconds_left=seconds_left)
    markup = _build_keyboard(session, closed=False)
    try:
        await context.bot.edit_message_text(
            chat_id=session["chat_id"],
            message_id=session["message_id"],
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup,
        )
    except TelegramError as e:
        logger.info("Couldn't refresh quiz message %s: %s", session_id, e)
    return session


async def close_quiz_session(session_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Marks a session closed and reveals the answer in-place. Safe to call
    more than once (no-op if already closed)."""
    session = db.get_quiz_session(session_id)
    if not session or session["status"] == "closed":
        return session

    db.close_quiz_session(session_id)
    answers = db.get_quiz_answers(session_id)
    session = db.get_quiz_session(session_id)  # re-fetch so returned status reflects the close
    text = _build_text(session, answers, closed=True)
    markup = _build_keyboard(session, closed=True)

    try:
        await context.bot.edit_message_text(
            chat_id=session["chat_id"],
            message_id=session["message_id"],
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup,
        )
    except TelegramError as e:
        logger.info("Couldn't edit closing quiz message %s: %s", session_id, e)

    return session


async def handle_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Single CallbackQueryHandler for all quiz answer buttons (trivia + duel)."""
    query = update.callback_query
    data = query.data or ""

    if data == "noop":
        await query.answer()
        return

    try:
        _, sid_str, idx_str = data.split(":")
        session_id, option_index = int(sid_str), int(idx_str)
    except (ValueError, IndexError):
        await query.answer()
        return

    session = db.get_quiz_session(session_id)
    if not session or session["status"] != "open":
        await query.answer("This question has already closed.")
        return

    user = query.from_user
    is_correct = option_index == session["correct_option"]

    inserted = db.record_quiz_answer(
        session_id, user.id, user.username or "", user.first_name or "", option_index, is_correct
    )
    if not inserted:
        await query.answer("You already answered this one.")
        return

    await query.answer(f"Correct! +{session['points']} pts" if is_correct else "Wrong answer.")

    # Route scoring to the right game mode. A duel may close (and advance
    # to the next round) right here if this was the second participant to
    # answer — see duel_handlers.handle_duel_answer.
    if session["kind"] == "duel":
        import duel_handlers
        await duel_handlers.handle_duel_answer(session, user, is_correct, context)
    else:
        import trivia_handlers
        stats = db.record_answer(
            chat_id=session["chat_id"],
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            is_correct=is_correct,
            points=session["points"],
        )
        if is_correct:
            await trivia_handlers.check_and_announce_achievements(session["chat_id"], user, stats, context)

    # If the duel-answer handling above already closed this session (both
    # participants had answered), it already rendered the final reveal —
    # don't overwrite that with a stale "still open" edit.
    fresh = db.get_quiz_session(session_id)
    if fresh["status"] == "closed":
        return

    answers = db.get_quiz_answers(session_id)
    text = _build_text(fresh, answers, closed=False)
    markup = _build_keyboard(fresh, closed=False)
    try:
        await context.bot.edit_message_text(
            chat_id=fresh["chat_id"],
            message_id=fresh["message_id"],
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup,
        )
    except TelegramError as e:
        logger.info("Couldn't update quiz message %s after an answer: %s", session_id, e)
