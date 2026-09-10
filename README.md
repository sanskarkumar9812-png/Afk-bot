# 🏁 F1 Trivia, Duels & Predictions Bot (Telegram)

A group-chat game bot built to keep an F1 fan chat hooked: random trivia
(history, records, drivers, teams, rules and memes), a points/rank system,
badges that get announced live in-chat, daily streaks, 1v1 duels, weekly
leaderboard resets, and a full podium-prediction game for upcoming races.

## Features

- **46 built-in F1 questions** across history, records, drivers, teams, rules, and memes
- Native Telegram **quiz polls** — auto-graded, with an explanation + points shown instantly
- **Difficulty-weighted points**: easy = 5, medium = 10, hard = 15
- **Rank titles** (Rookie → Test Driver → Point Scorer → Race Winner → Champion → Legend → GOAT)
- **Achievements/badges** that get announced in the chat the moment someone unlocks them
  (Hat Trick, On Fire, Trivia Master, Daily Warrior, Perfect Podium, Duelist, and more)
- **Daily answer streaks** — answer correctly on consecutive days to build a streak
- **All-time + weekly leaderboards** — the weekly board auto-resets every Sunday with
  a "Champion of the Week" announcement
- **1v1 Duels** — reply to someone's message with `/challenge` for a 5-question head-to-head
- **GP Podium Predictions** — predict P1/P2/P3 for an upcoming race, admin locks entries
  and enters the real result, bot auto-scores everyone and updates a dedicated leaderboard
- Survives restarts — everything is saved to a local SQLite file
- Easy to extend — add more trivia questions in `questions.py`

## 1. Create your bot

1. Open Telegram, message **@BotFather**
2. Send `/newbot`, follow the prompts, and copy the token it gives you
3. (Optional) Send `/setcommands` to BotFather and paste:
   ```
   quiz - Ask a random F1 question
   daily - Today's daily challenge
   leaderboard - All-time top scorers
   weekly - This week's leaderboard
   mystats - Your rank, points, streaks and badges
   autoquiz - Auto-post a question every N minutes
   stopquiz - Stop auto-quiz
   challenge - Reply to someone to start a 1v1 duel
   duelstats - Your duel win/loss record
   predict - Start a podium prediction round
   pick - Submit your podium pick
   predictions - See who's picked so far
   lockpredictions - Admin: close entries
   setresult - Admin: enter real results and score everyone
   predictionboard - Prediction game leaderboard
   help - Show help
   ```

> You do **not** need to disable Privacy Mode — the bot only reacts to slash
> commands and poll answers, both of which reach it regardless of that setting.

## 2. Install & run

```bash
pip install -r requirements.txt
export BOT_TOKEN="paste-your-token-here"     # Windows: set BOT_TOKEN=...
python bot.py
```

## 3. Add it to a group

Add the bot to your group with permission to send messages (polls are sent
as regular messages — no extra permission needed), then run `/quiz` to fire
off your first question.

## Commands

### Trivia
| Command | Description |
|---|---|
| `/quiz` | Ask one random F1 question right now |
| `/daily` | Today's daily challenge — keep your daily streak alive |
| `/leaderboard` | All-time top scorers in this chat, with rank titles |
| `/weekly` | This week's leaderboard (auto-resets every Sunday) |
| `/mystats` | Your rank, points, streaks, duel record, and badges |
| `/autoquiz <minutes>` | Auto-post a question every N minutes, e.g. `/autoquiz 60` |
| `/stopquiz` | Turn off auto-quiz |

### Duels
| Command | Description |
|---|---|
| `/challenge` | Reply to someone's message with this to start a 5-question 1v1 |
| `/duelstats` | Your duel win/loss record |

### Predictions
| Command | Description |
|---|---|
| `/predict <GP name>` | Start a podium prediction round, e.g. `/predict Singapore GP` |
| `/pick Driver1, Driver2, Driver3` | Submit your P1/P2/P3 guess |
| `/predictions` | See who's submitted a pick (picks stay hidden until scored) |
| `/lockpredictions` | *(admin)* Close entries before the race starts |
| `/setresult Driver1, Driver2, Driver3` | *(admin)* Enter the real result — auto-scores everyone |
| `/predictionboard` | All-time prediction game leaderboard |

## How scoring works

**Trivia:** each question is tagged easy/medium/hard, worth 5/10/15 points.
Points build your rank and place you on the leaderboard.

**Predictions:** for each of your three picks —
- Exact position match → **+10 pts**
- Right driver, wrong slot (still in the actual top 3) → **+4 pts**
- Nailed the entire podium in order → **+15 bonus** on top (max 45 pts/round)

Prediction points are added straight to your overall points total too, so a
great podium call can boost your rank on the main leaderboard as well as the
dedicated `/predictionboard`.

**Duels:** 5 quiz questions, most correct answers wins. Only the two
duelists' answers count toward the duel score — everyone else in the chat
can still answer the same polls just for fun/normal trivia points.

## Achievements

Unlocked automatically and announced live in the chat:

| Badge | How to unlock |
|---|---|
| 🩸 First Blood | Answer your first question correctly |
| 🎩 Hat Trick | 3 correct in a row |
| 🔥 On Fire | 10 correct in a row |
| 🧠 Trivia Master | 50 total correct answers |
| 💯 Century Club | 100 total correct answers |
| 📅 Daily Warrior | 7-day daily answer streak |
| 🛡 Iron Will | 30-day daily answer streak |
| 🏆 Perfect Podium | Nail an exact P1-P2-P3 prediction |
| 🔮 Prediction Pro | Play 5 prediction rounds |
| ⚔️ Duelist | Win your first duel |
| 🗡 Gladiator | Win 10 duels |

## Adding more trivia questions

Open `questions.py` and append to the `QUESTIONS` list:

```python
QUESTIONS.append({
    "question": "Which driver crashed into the back of the Safety Car at the 2021 Turkish GP?",
    "options": ["Antonio Giovinazzi", "Nikita Mazepin", "Mick Schumacher", "George Russell"],
    "correct": 0,
    "explanation": "Antonio Giovinazzi memorably crashed into the Safety Car itself in wet conditions.",
    "category": "meme",
    "difficulty": "hard",  # easy=5pts, medium=10pts, hard=15pts
})
```

Keep `question` under ~255 characters and each option under ~100 characters
— these are Telegram's native poll limits.

## Rebalancing points, ranks, or achievements

All of that lives in `config.py`:
- `POINTS_BY_DIFFICULTY` — points per question difficulty
- `RANKS` — point thresholds and titles
- `ACHIEVEMENTS` / `PREDICTION_ACHIEVEMENTS` / `DUEL_ACHIEVEMENTS` — badge definitions
- `PREDICTION_*_POINTS` — prediction game scoring
- `DUEL_ROUNDS`, `DUEL_*_SECONDS` — duel format/timing

## Project structure

```
bot.py                  # entrypoint, wires up all handlers
config.py               # points, ranks, achievement definitions
database.py             # all SQLite persistence
questions.py            # trivia question bank
trivia_handlers.py      # /quiz, /daily, /leaderboard, /mystats, /autoquiz, achievements
duel_handlers.py        # /challenge and 1v1 duel flow
prediction_handlers.py  # /predict, /pick, /setresult, prediction leaderboard
common_handlers.py      # /start, /help
jobs.py                 # weekly reset job + auto-quiz restore on startup
```

## Deploying so it runs 24/7

This script uses long-polling, so it just needs to keep running somewhere:

- **Simplest**: a small VPS + `tmux`/`screen`, or a `systemd` service running `python bot.py`
- **Docker**: `CMD ["python", "bot.py"]` with `BOT_TOKEN` passed as an env var
- **PaaS**: Railway, Render, Fly.io etc. — set `BOT_TOKEN` as a secret and the
  start command to `python bot.py`

The SQLite file (`f1_quiz.db`) is created next to `bot.py` and holds all
scores, badges, duels, and predictions — make sure your deployment target
has a **persistent disk**, or you'll lose everything on redeploy.

## Notes on accuracy

F1 records and standings change every season. The trivia bank is accurate
through the 2023-2024 seasons — revisit `questions.py` periodically,
especially the "most wins", "current record", etc. questions, since those
are the ones most likely to go stale. The prediction game doesn't hardcode
any calendar or driver data, so it stays accurate regardless of season —
you just type in whatever GP and driver names are current.
