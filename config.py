"""
Shared constants: difficulty point values, rank titles, and achievement
definitions. Keeping these in one place makes it easy to rebalance the game.
"""

# --------------------------------------------------------------------------
# Points per question difficulty
# --------------------------------------------------------------------------
POINTS_BY_DIFFICULTY = {
    "easy": 5,
    "medium": 10,
    "hard": 15,
}

# --------------------------------------------------------------------------
# Rank titles, unlocked by total (all-time) points
# --------------------------------------------------------------------------
RANKS = [
    (0, "🟢 Rookie"),
    (75, "🔵 Test Driver"),
    (200, "🟡 Point Scorer"),
    (450, "🟠 Race Winner"),
    (800, "🔴 Champion"),
    (1500, "🟣 Legend"),
    (3000, "⚪ GOAT"),
]


def get_rank(points: int) -> str:
    title = RANKS[0][1]
    for threshold, name in RANKS:
        if points >= threshold:
            title = name
        else:
            break
    return title


def next_rank_info(points: int):
    """Returns (points_needed, next_title) or None if already at max rank."""
    for threshold, name in RANKS:
        if points < threshold:
            return threshold - points, name
    return None


# --------------------------------------------------------------------------
# Achievements. Each has a unique key, display name/emoji, and a
# `check(stats)` function that returns True the first time it should unlock.
# `stats` is the row dict from database.get_user_stats().
# --------------------------------------------------------------------------
ACHIEVEMENTS = [
    {
        "key": "first_blood",
        "name": "🩸 First Blood",
        "desc": "Answered your first question correctly",
        "check": lambda s: s["correct"] >= 1,
    },
    {
        "key": "hat_trick",
        "name": "🎩 Hat Trick",
        "desc": "3 correct answers in a row",
        "check": lambda s: s["streak"] >= 3,
    },
    {
        "key": "perfect_ten",
        "name": "🔥 On Fire",
        "desc": "10 correct answers in a row",
        "check": lambda s: s["streak"] >= 10,
    },
    {
        "key": "trivia_master",
        "name": "🧠 Trivia Master",
        "desc": "50 total correct answers",
        "check": lambda s: s["correct"] >= 50,
    },
    {
        "key": "century",
        "name": "💯 Century Club",
        "desc": "100 total correct answers",
        "check": lambda s: s["correct"] >= 100,
    },
    {
        "key": "daily_warrior",
        "name": "📅 Daily Warrior",
        "desc": "7-day daily answer streak",
        "check": lambda s: s["daily_streak"] >= 7,
    },
    {
        "key": "iron_will",
        "name": "🛡 Iron Will",
        "desc": "30-day daily answer streak",
        "check": lambda s: s["daily_streak"] >= 30,
    },
]

# Achievements unlocked via other systems (predictions/duels), checked separately
PREDICTION_ACHIEVEMENTS = [
    {
        "key": "podium_perfect",
        "name": "🏆 Perfect Podium",
        "desc": "Predicted an exact P1-P2-P3 podium",
    },
    {
        "key": "prediction_pro",
        "name": "🔮 Prediction Pro",
        "desc": "Played 5 prediction rounds",
    },
]

DUEL_ACHIEVEMENTS = [
    {
        "key": "duelist",
        "name": "⚔️ Duelist",
        "desc": "Won your first 1v1 duel",
    },
    {
        "key": "gladiator",
        "name": "🗡 Gladiator",
        "desc": "Won 10 duels",
    },
]


def check_trivia_achievements(stats: dict, already_unlocked: set) -> list:
    """Returns list of achievement dicts newly unlocked given current stats."""
    newly_unlocked = []
    for ach in ACHIEVEMENTS:
        if ach["key"] not in already_unlocked and ach["check"](stats):
            newly_unlocked.append(ach)
    return newly_unlocked


# --------------------------------------------------------------------------
# Prediction game scoring
# --------------------------------------------------------------------------
PREDICTION_EXACT_POSITION_POINTS = 10   # driver correct AND in the predicted slot
PREDICTION_WRONG_POSITION_POINTS = 4    # driver correct but in the wrong slot
PREDICTION_PERFECT_PODIUM_BONUS = 15    # all 3 slots exactly right

# --------------------------------------------------------------------------
# Duel settings
# --------------------------------------------------------------------------
DUEL_ROUNDS = 5
DUEL_QUESTION_OPEN_SECONDS = 15
DUEL_GAP_SECONDS = 20  # time between duel questions
