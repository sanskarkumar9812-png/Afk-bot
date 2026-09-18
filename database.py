"""
SQLite persistence layer for the F1 Quiz Bot.

Tables:
  scores          -> per (chat_id, user_id): all-time correct/wrong, streak,
                     points (XP), daily-answer-streak tracking
  weekly_scores   -> same shape, reset every week for "Champion of the Week"
  active_polls    -> maps an open Telegram poll_id -> chat/answer/points/kind,
                     so poll_answer updates can be graded
  chat_settings   -> per-chat auto-quiz interval
  badges          -> unlocked achievements per (chat_id, user_id)
  duels           -> 1v1 challenge state
  prediction_rounds -> a GP podium-prediction round for a chat
  predictions     -> a user's P1/P2/P3 pick for a given round
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, timedelta
import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "f1_quiz.db"

_lock = threading.Lock()


def init_db():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scores (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                correct INTEGER NOT NULL DEFAULT 0,
                wrong INTEGER NOT NULL DEFAULT 0,
                streak INTEGER NOT NULL DEFAULT 0,
                best_streak INTEGER NOT NULL DEFAULT 0,
                points INTEGER NOT NULL DEFAULT 0,
                daily_streak INTEGER NOT NULL DEFAULT 0,
                best_daily_streak INTEGER NOT NULL DEFAULT 0,
                last_active_date TEXT,
                duel_wins INTEGER NOT NULL DEFAULT 0,
                duel_losses INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weekly_scores (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                correct INTEGER NOT NULL DEFAULT 0,
                points INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS active_polls (
                poll_id TEXT PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                correct_option INTEGER NOT NULL,
                points INTEGER NOT NULL DEFAULT 10,
                kind TEXT NOT NULL DEFAULT 'trivia',   -- 'trivia' | 'duel'
                duel_id INTEGER,
                duel_round INTEGER,
                asked_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER PRIMARY KEY,
                auto_interval_minutes INTEGER DEFAULT 0,
                predictions_enabled INTEGER DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                message_id INTEGER,
                kind TEXT NOT NULL DEFAULT 'trivia',   -- 'trivia' | 'duel'
                question_text TEXT NOT NULL,
                options_json TEXT NOT NULL,
                correct_option INTEGER NOT NULL,
                points INTEGER NOT NULL DEFAULT 10,
                category TEXT,
                difficulty TEXT,
                duel_id INTEGER,
                duel_round INTEGER,
                status TEXT NOT NULL DEFAULT 'open',   -- 'open' | 'closed'
                opened_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_answers (
                session_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                option_index INTEGER NOT NULL,
                is_correct INTEGER NOT NULL,
                answered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_id, user_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS command_cooldowns (
                chat_id INTEGER NOT NULL,
                command TEXT NOT NULL,
                last_used_at TEXT NOT NULL,
                PRIMARY KEY (chat_id, command)
            )
            """
        )
        # Migration for DBs created before quiz_cooldown_seconds existed.
        try:
            conn.execute("ALTER TABLE chat_settings ADD COLUMN quiz_cooldown_seconds INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE chat_settings ADD COLUMN predictions_enabled INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # column already exists
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recent_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                question_key TEXT NOT NULL,
                asked_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS badges (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                badge_key TEXT NOT NULL,
                earned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (chat_id, user_id, badge_key)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS duels (
                duel_id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                challenger_id INTEGER NOT NULL,
                challenger_name TEXT,
                opponent_id INTEGER NOT NULL,
                opponent_name TEXT,
                round_number INTEGER NOT NULL DEFAULT 0,
                challenger_score INTEGER NOT NULL DEFAULT 0,
                opponent_score INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',   -- 'active' | 'finished'
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_rounds (
                round_id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                gp_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',   -- 'open' | 'locked' | 'scored'
                created_by INTEGER,
                p1_actual TEXT,
                p2_actual TEXT,
                p3_actual TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                round_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                p1 TEXT NOT NULL,
                p2 TEXT NOT NULL,
                p3 TEXT NOT NULL,
                points_awarded INTEGER,
                PRIMARY KEY (round_id, user_id)
            )
            """
        )
        conn.commit()


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ==========================================================================
# Active poll tracking (trivia + duel)
# ==========================================================================

def save_active_poll(poll_id, chat_id, correct_option, points=10, kind="trivia",
                      duel_id=None, duel_round=None):
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO active_polls "
            "(poll_id, chat_id, correct_option, points, kind, duel_id, duel_round) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (poll_id, chat_id, correct_option, points, kind, duel_id, duel_round),
        )
        conn.commit()


def get_active_poll(poll_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM active_polls WHERE poll_id = ?", (poll_id,)).fetchone()
        return dict(row) if row else None


def delete_active_poll(poll_id):
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM active_polls WHERE poll_id = ?", (poll_id,))
        conn.commit()


# ==========================================================================
# Trivia scores (all-time + weekly + daily streak)
# ==========================================================================

def _today_str() -> str:
    return date.today().isoformat()


def record_answer(chat_id: int, user_id: int, username: str, first_name: str,
                   is_correct: bool, points: int):
    """Updates all-time score, weekly score, streaks, and daily-answer-streak.
    Returns the fresh stats dict for this user in this chat."""
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT * FROM scores WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)
        ).fetchone()

        today = _today_str()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        earned_points = points if is_correct else 0

        if row is None:
            correct = 1 if is_correct else 0
            wrong = 0 if is_correct else 1
            streak = 1 if is_correct else 0
            daily_streak = 1 if is_correct else 0
            conn.execute(
                "INSERT INTO scores (chat_id, user_id, username, first_name, correct, wrong, "
                "streak, best_streak, points, daily_streak, best_daily_streak, last_active_date) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (chat_id, user_id, username, first_name, correct, wrong, streak, streak,
                 earned_points, daily_streak, daily_streak, today if is_correct else None),
            )
        else:
            correct = row["correct"] + (1 if is_correct else 0)
            wrong = row["wrong"] + (0 if is_correct else 1)
            streak = row["streak"] + 1 if is_correct else 0
            best_streak = max(row["best_streak"], streak)
            new_points = row["points"] + earned_points

            if is_correct:
                if row["last_active_date"] == today:
                    daily_streak = row["daily_streak"]  # already counted today
                elif row["last_active_date"] == yesterday:
                    daily_streak = row["daily_streak"] + 1
                else:
                    daily_streak = 1
                last_active = today
            else:
                daily_streak = row["daily_streak"]
                last_active = row["last_active_date"]

            best_daily_streak = max(row["best_daily_streak"], daily_streak)

            conn.execute(
                "UPDATE scores SET username = ?, first_name = ?, correct = ?, wrong = ?, "
                "streak = ?, best_streak = ?, points = ?, daily_streak = ?, "
                "best_daily_streak = ?, last_active_date = ? WHERE chat_id = ? AND user_id = ?",
                (username, first_name, correct, wrong, streak, best_streak, new_points,
                 daily_streak, best_daily_streak, last_active, chat_id, user_id),
            )

        # weekly table
        wrow = conn.execute(
            "SELECT * FROM weekly_scores WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)
        ).fetchone()
        if wrow is None:
            conn.execute(
                "INSERT INTO weekly_scores (chat_id, user_id, username, first_name, correct, points) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (chat_id, user_id, username, first_name, 1 if is_correct else 0, earned_points),
            )
        else:
            conn.execute(
                "UPDATE weekly_scores SET username = ?, first_name = ?, correct = correct + ?, "
                "points = points + ? WHERE chat_id = ? AND user_id = ?",
                (username, first_name, 1 if is_correct else 0, earned_points, chat_id, user_id),
            )

        conn.commit()

        result = conn.execute(
            "SELECT * FROM scores WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)
        ).fetchone()
        return dict(result)


def get_leaderboard(chat_id: int, limit: int = 10):
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM scores WHERE chat_id = ? ORDER BY points DESC, correct DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_weekly_leaderboard(chat_id: int, limit: int = 10):
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM weekly_scores WHERE chat_id = ? ORDER BY points DESC, correct DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def reset_weekly_scores(chat_id: int):
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM weekly_scores WHERE chat_id = ?", (chat_id,))
        conn.commit()


def get_all_chats_with_scores():
    with _connect() as conn:
        rows = conn.execute("SELECT DISTINCT chat_id FROM scores").fetchall()
        return [r["chat_id"] for r in rows]


def get_user_stats(chat_id: int, user_id: int):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM scores WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)
        ).fetchone()
        return dict(row) if row else None


# ==========================================================================
# Badges
# ==========================================================================

def get_unlocked_badges(chat_id: int, user_id: int) -> set:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT badge_key FROM badges WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)
        ).fetchall()
        return {r["badge_key"] for r in rows}


def unlock_badge(chat_id: int, user_id: int, badge_key: str) -> bool:
    """Returns True if newly inserted, False if already had it."""
    with _lock, _connect() as conn:
        try:
            conn.execute(
                "INSERT INTO badges (chat_id, user_id, badge_key) VALUES (?, ?, ?)",
                (chat_id, user_id, badge_key),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


# ==========================================================================
# Chat settings (auto-quiz)
# ==========================================================================

def set_auto_interval(chat_id: int, minutes: int):
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO chat_settings (chat_id, auto_interval_minutes) VALUES (?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET auto_interval_minutes = excluded.auto_interval_minutes",
            (chat_id, minutes),
        )
        conn.commit()


def set_predictions_enabled(chat_id: int, enabled: bool = True):
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO chat_settings (chat_id, predictions_enabled) VALUES (?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET predictions_enabled = excluded.predictions_enabled",
            (chat_id, 1 if enabled else 0),
        )
        conn.commit()


def get_prediction_enabled_chats():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT chat_id FROM chat_settings WHERE predictions_enabled = 1"
        ).fetchall()
        return [r["chat_id"] for r in rows]


def get_all_auto_chats():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT chat_id, auto_interval_minutes FROM chat_settings WHERE auto_interval_minutes > 0"
        ).fetchall()
        return [(r["chat_id"], r["auto_interval_minutes"]) for r in rows]


# ==========================================================================
# Duels
# ==========================================================================

def create_duel(chat_id, challenger_id, challenger_name, opponent_id, opponent_name):
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO duels (chat_id, challenger_id, challenger_name, opponent_id, "
            "opponent_name) VALUES (?, ?, ?, ?, ?)",
            (chat_id, challenger_id, challenger_name, opponent_id, opponent_name),
        )
        conn.commit()
        return cur.lastrowid


def get_duel(duel_id: int):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM duels WHERE duel_id = ?", (duel_id,)).fetchone()
        return dict(row) if row else None


def get_active_duel_for_chat(chat_id: int):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM duels WHERE chat_id = ? AND status = 'active' "
            "ORDER BY duel_id DESC LIMIT 1",
            (chat_id,),
        ).fetchone()
        return dict(row) if row else None


def bump_duel_round(duel_id: int):
    with _lock, _connect() as conn:
        conn.execute("UPDATE duels SET round_number = round_number + 1 WHERE duel_id = ?", (duel_id,))
        conn.commit()


def add_duel_point(duel_id: int, user_id: int):
    with _lock, _connect() as conn:
        duel = conn.execute("SELECT * FROM duels WHERE duel_id = ?", (duel_id,)).fetchone()
        if not duel:
            return
        if user_id == duel["challenger_id"]:
            conn.execute(
                "UPDATE duels SET challenger_score = challenger_score + 1 WHERE duel_id = ?",
                (duel_id,),
            )
        elif user_id == duel["opponent_id"]:
            conn.execute(
                "UPDATE duels SET opponent_score = opponent_score + 1 WHERE duel_id = ?",
                (duel_id,),
            )
        conn.commit()


def finish_duel(duel_id: int):
    with _lock, _connect() as conn:
        conn.execute("UPDATE duels SET status = 'finished' WHERE duel_id = ?", (duel_id,))
        conn.commit()


def record_duel_result(chat_id, winner_id, loser_id, is_draw=False):
    with _lock, _connect() as conn:
        for uid in (winner_id, loser_id):
            row = conn.execute(
                "SELECT * FROM scores WHERE chat_id = ? AND user_id = ?", (chat_id, uid)
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO scores (chat_id, user_id, duel_wins, duel_losses) VALUES (?, ?, 0, 0)",
                    (chat_id, uid),
                )
        if not is_draw:
            conn.execute(
                "UPDATE scores SET duel_wins = duel_wins + 1 WHERE chat_id = ? AND user_id = ?",
                (chat_id, winner_id),
            )
            conn.execute(
                "UPDATE scores SET duel_losses = duel_losses + 1 WHERE chat_id = ? AND user_id = ?",
                (chat_id, loser_id),
            )
        conn.commit()


# ==========================================================================
# Predictions (GP podium picks)
# ==========================================================================

def create_prediction_round(chat_id: int, gp_name: str, created_by: int) -> int:
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO prediction_rounds (chat_id, gp_name, created_by) VALUES (?, ?, ?)",
            (chat_id, gp_name, created_by),
        )
        conn.commit()
        return cur.lastrowid


def get_open_round(chat_id: int):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM prediction_rounds WHERE chat_id = ? AND status = 'open' "
            "ORDER BY round_id DESC LIMIT 1",
            (chat_id,),
        ).fetchone()
        return dict(row) if row else None


def get_scoreable_round(chat_id: int):
    """Latest round that hasn't been scored yet (open or locked)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM prediction_rounds WHERE chat_id = ? AND status IN ('open', 'locked') "
            "ORDER BY round_id DESC LIMIT 1",
            (chat_id,),
        ).fetchone()
        return dict(row) if row else None


def get_round(round_id: int):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM prediction_rounds WHERE round_id = ?", (round_id,)
        ).fetchone()
        return dict(row) if row else None


def lock_round(round_id: int):
    with _lock, _connect() as conn:
        conn.execute("UPDATE prediction_rounds SET status = 'locked' WHERE round_id = ?", (round_id,))
        conn.commit()


def score_round(round_id: int, p1_actual: str, p2_actual: str, p3_actual: str):
    with _lock, _connect() as conn:
        conn.execute(
            "UPDATE prediction_rounds SET status = 'scored', p1_actual = ?, p2_actual = ?, "
            "p3_actual = ? WHERE round_id = ?",
            (p1_actual, p2_actual, p3_actual, round_id),
        )
        conn.commit()


def submit_prediction(round_id, chat_id, user_id, username, first_name, p1, p2, p3):
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO predictions (round_id, chat_id, user_id, username, "
            "first_name, p1, p2, p3, points_awarded) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (round_id, chat_id, user_id, username, first_name, p1, p2, p3),
        )
        conn.commit()


def get_predictions_for_round(round_id: int):
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM predictions WHERE round_id = ?", (round_id,)).fetchall()
        return [dict(r) for r in rows]


def set_prediction_points(round_id: int, user_id: int, points: int):
    with _lock, _connect() as conn:
        conn.execute(
            "UPDATE predictions SET points_awarded = ? WHERE round_id = ? AND user_id = ?",
            (points, round_id, user_id),
        )
        conn.commit()


def get_prediction_leaderboard(chat_id: int, limit: int = 10):
    """All-time prediction points, summed across every scored round in this chat."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT user_id,
                   COALESCE(username, '') as username,
                   COALESCE(first_name, '') as first_name,
                   SUM(COALESCE(points_awarded, 0)) as total_points,
                   COUNT(*) as rounds_played
            FROM predictions
            WHERE chat_id = ? AND points_awarded IS NOT NULL
            GROUP BY user_id
            ORDER BY total_points DESC
            LIMIT ?
            """,
            (chat_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def count_rounds_played(chat_id: int, user_id: int) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM predictions WHERE chat_id = ? AND user_id = ? "
            "AND points_awarded IS NOT NULL",
            (chat_id, user_id),
        ).fetchone()
        return row["c"] if row else 0


def get_user_prediction_summary(chat_id: int, user_id: int):
    with _connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(points_awarded), 0) as total_points, COUNT(*) as rounds_played "
            "FROM predictions WHERE chat_id = ? AND user_id = ? AND points_awarded IS NOT NULL",
            (chat_id, user_id),
        ).fetchone()
        return dict(row)


def get_recently_asked(chat_id: int, limit: int) -> set:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT question_key FROM recent_questions WHERE chat_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
        return {r["question_key"] for r in rows}


def record_asked(chat_id: int, question_key: str, keep_last: int):
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO recent_questions (chat_id, question_key) VALUES (?, ?)",
            (chat_id, question_key),
        )
        # prune anything older than the most recent `keep_last` rows for this chat
        conn.execute(
            """
            DELETE FROM recent_questions
            WHERE chat_id = ? AND id NOT IN (
                SELECT id FROM recent_questions WHERE chat_id = ? ORDER BY id DESC LIMIT ?
            )
            """,
            (chat_id, chat_id, keep_last),
        )
        conn.commit()


def add_bonus_points(chat_id: int, user_id: int, username: str, first_name: str, points: int):
    """Adds points to a user's main score total (used for prediction-game points),
    without touching correct/wrong/streak counters."""
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT * FROM scores WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO scores (chat_id, user_id, username, first_name, points) "
                "VALUES (?, ?, ?, ?, ?)",
                (chat_id, user_id, username, first_name, points),
            )
        else:
            conn.execute(
                "UPDATE scores SET username = ?, first_name = ?, points = points + ? "
                "WHERE chat_id = ? AND user_id = ?",
                (username, first_name, points, chat_id, user_id),
            )
        conn.commit()


# ==========================================================================
# Custom quiz sessions (button-based quiz UI, replaces native Telegram polls)
# ==========================================================================

def create_quiz_session(chat_id, kind, question_text, options, correct_option,
                         points, category, difficulty, duel_id=None, duel_round=None):
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO quiz_sessions (chat_id, kind, question_text, options_json, "
            "correct_option, points, category, difficulty, duel_id, duel_round) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (chat_id, kind, question_text, json.dumps(options), correct_option,
             points, category, difficulty, duel_id, duel_round),
        )
        conn.commit()
        return cur.lastrowid


def set_session_message_id(session_id: int, message_id: int):
    with _lock, _connect() as conn:
        conn.execute(
            "UPDATE quiz_sessions SET message_id = ? WHERE session_id = ?",
            (message_id, session_id),
        )
        conn.commit()


def get_open_quiz_session(chat_id: int, kind: str = "trivia"):
    """Latest still-open session of this kind in a chat, or None. Used to
    stop a new /quiz from stacking on top of one that's still live."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM quiz_sessions WHERE chat_id = ? AND kind = ? AND status = 'open' "
            "ORDER BY session_id DESC LIMIT 1",
            (chat_id, kind),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["options"] = json.loads(d["options_json"])
        return d


def get_quiz_session(session_id: int):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM quiz_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["options"] = json.loads(d["options_json"])
        return d


def close_quiz_session(session_id: int):
    with _lock, _connect() as conn:
        conn.execute(
            "UPDATE quiz_sessions SET status = 'closed' WHERE session_id = ?", (session_id,)
        )
        conn.commit()


def record_quiz_answer(session_id, user_id, username, first_name, option_index, is_correct) -> bool:
    """Returns True if this is the user's first (accepted) answer for this
    session, False if they'd already answered (duplicate, ignored)."""
    with _lock, _connect() as conn:
        try:
            conn.execute(
                "INSERT INTO quiz_answers (session_id, user_id, username, first_name, "
                "option_index, is_correct) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, user_id, username, first_name, option_index, int(is_correct)),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def get_quiz_answers(session_id: int):
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM quiz_answers WHERE session_id = ? ORDER BY answered_at ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ==========================================================================
# Cooldowns (rate-limit manual commands like /quiz to prevent spam/flooding)
# ==========================================================================

def set_quiz_cooldown(chat_id: int, seconds: int):
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO chat_settings (chat_id, quiz_cooldown_seconds) VALUES (?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET quiz_cooldown_seconds = excluded.quiz_cooldown_seconds",
            (chat_id, seconds),
        )
        conn.commit()


def get_quiz_cooldown(chat_id: int) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT quiz_cooldown_seconds FROM chat_settings WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return row["quiz_cooldown_seconds"] if row and row["quiz_cooldown_seconds"] else 0


def check_and_apply_cooldown(chat_id: int, command: str, cooldown_seconds: int):
    """Returns (allowed: bool, remaining_seconds: int). If allowed, records
    this as the new last-used time so the cooldown window starts now."""
    if cooldown_seconds <= 0:
        return True, 0

    now = datetime.datetime.utcnow()
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT last_used_at FROM command_cooldowns WHERE chat_id = ? AND command = ?",
            (chat_id, command),
        ).fetchone()

        if row:
            last_used = datetime.datetime.fromisoformat(row["last_used_at"])
            elapsed = (now - last_used).total_seconds()
            if elapsed < cooldown_seconds:
                return False, int(cooldown_seconds - elapsed)

        conn.execute(
            "INSERT INTO command_cooldowns (chat_id, command, last_used_at) VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id, command) DO UPDATE SET last_used_at = excluded.last_used_at",
            (chat_id, command, now.isoformat()),
        )
        conn.commit()
        return True, 0
