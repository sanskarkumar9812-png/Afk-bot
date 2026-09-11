# F1 Trivia, Duels & Predictions Bot (Telegram)

A group-chat F1 game bot: trivia across history, records, drivers, teams,
rules and iconic moments, a points/rank system, badges, daily streaks,
1v1 duels, weekly leaderboard resets, and a podium-prediction game that
tracks the **real 2026 F1 calendar** — it knows what the next race is and
manages prediction rounds around it automatically.

## What changed in this version

- **125 trivia questions** (up from 46 originally), still fact-checked rather than
  invented — see "On the 1,000-question ask" below for why it isn't 1,000+ yet.
- **Anti-repeat engine**: each chat now avoids repeating a question until
  ~85% of the pool has been used, so it doesn't feel like the same handful
  of questions on loop, regardless of the pool's exact size.
- **Calendar-aware predictions**: `/predict` with no arguments automatically
  targets the real next Grand Prix. A background job opens the round, locks
  it on race day, fetches the actual result, and scores everyone — no admin
  typing needed unless the auto-fetch fails.
- **Cleaner UI**: message copy was rewritten to be plain and structured
  (headers + a divider + short lines) instead of emoji-heavy.

## On the "1,000+ questions" ask

I can't responsibly hand-write 1,000+ fact-checked F1 trivia questions in
one pass — at that volume the risk of quietly inventing a wrong stat or
date is real, and a trivia bot that confidently states wrong facts is worse
than one with fewer, correct questions. What I did instead:

1. Grown the bank to 125 questions across three batches, all still individually checked.
2. Added the anti-repeat engine above, which is the actual fix for "it
   keeps repeating" — it matters more than raw question count.
3. Made it easy to keep growing: open `questions.py` and append more dicts
   in the documented format (see the bottom of that file). If you've got a
   trivia set from elsewhere (a book, a site, another bot) you're allowed to
   use, converting it into that format is mechanical.

If you want, ask me for another batch (I can keep adding ~40-50 at a time
in follow-up messages, fact-checking each batch) — that scales to a large
bank over a few rounds without the accuracy risk of doing it all at once.

## Features

- **Trivia**: 125 questions, difficulty-weighted points (easy=5, medium=10,
  hard=15), native Telegram quiz polls, anti-repeat selection
- **Ranks**: Rookie → Test Driver → Point Scorer → Race Winner → Champion →
  Legend → GOAT, based on total points
- **Badges**: unlocked and announced live in chat (streaks, milestones,
  perfect predictions, duel wins)
- **Daily streaks**: answer correctly on consecutive days to build one
- **Leaderboards**: all-time + a weekly one that auto-resets every Sunday
  with a "Champion of the Week" announcement
- **1v1 Duels**: reply to someone's message with `/challenge` for a
  5-question head-to-head
- **GP Predictions**: tied to the real 2026 calendar —
  - `/nextrace` shows the actual next Grand Prix and a countdown
  - `/predict` auto-opens a round for it (or accepts a manual name override)
  - A background job auto-locks entries on race day and auto-scores the
    round using a free public results API once the race is over
  - `/setresult` remains available as an admin fallback if the automatic
    fetch ever fails or the race isn't in the built-in calendar
- Survives restarts — everything lives in a local SQLite file

## 1. Create your bot

1. Message **@BotFather** on Telegram, send `/newbot`, copy the token
2. Optionally run `/setcommands` on BotFather and paste:
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
   nextrace - The real next race on the calendar
   predict - Open a podium prediction round
   pick - Submit your podium pick
   predictions - See who's picked so far
   lockpredictions - Admin: close entries
   setresult - Admin: manual scoring fallback
   predictionboard - Prediction game leaderboard
   help - Show help
   ```

## 2. Install & run

```bash
pip install -r requirements.txt
export BOT_TOKEN="paste-your-token-here"
python bot.py
```

Add the bot to your group with permission to send messages, then run
`/quiz` or `/nextrace` to try it out.

## Commands

### Trivia
| Command | Description |
|---|---|
| `/quiz` | Random F1 question |
| `/daily` | Daily challenge — keeps your daily streak alive |
| `/leaderboard` | All-time top scorers, with rank titles |
| `/weekly` | This week's leaderboard (resets Sundays) |
| `/mystats` | Your rank, points, streaks, duel record, predictions, badges |
| `/autoquiz <minutes>` | Auto-post a question every N minutes |
| `/stopquiz` | Turn off auto-quiz |

### Duels
| Command | Description |
|---|---|
| `/challenge` | Reply to someone's message to start a 5-question 1v1 |
| `/duelstats` | Your duel win/loss record |

### Predictions
| Command | Description |
|---|---|
| `/nextrace` | Shows the real next Grand Prix and days remaining |
| `/predict` | Opens a round for the next GP automatically (or `/predict <name>` to override) |
| `/pick Driver1, Driver2, Driver3` | Submit your P1/P2/P3 guess |
| `/predictions` | See who's entered (picks stay hidden until scored) |
| `/lockpredictions` | *(admin)* Manually close entries early |
| `/setresult Driver1, Driver2, Driver3` | *(admin)* Manual scoring fallback |
| `/predictionboard` | All-time prediction game leaderboard |

## How the automatic prediction cycle works

A background job (`jobs.prediction_maintenance_job`) runs hourly for every
chat that's used a prediction command at least once:

1. **~5 days before** the next race, if no round is open, it opens one
   automatically, named after the real Grand Prix.
2. **On race day at 11:00 UTC**, if the round is still open, it locks it.
3. **Once the race date has passed**, it queries the free
   [Jolpica-F1](https://github.com/jolpica/jolpica-f1) API (the open-source
   successor to the retired Ergast API) for the actual top 3 and scores
   everyone automatically, same as `/setresult` would.
4. If that fetch fails (API downtime, result not posted yet), it just
   retries next cycle — an admin can always run `/setresult` manually in
   the meantime, nothing gets stuck.

The 2026 calendar itself lives in `race_calendar.py`, sourced from
formula1.com's official schedule. **This needs a manual update each
off-season** — add next year's rounds to the `CALENDAR` list there.

## Scoring

**Trivia**: easy/medium/hard = 5/10/15 points, building your rank.

**Predictions**, per pick:
- Exact position → **+10**
- Right driver, wrong slot → **+4**
- Perfect podium (all 3 exact) → **+15 bonus** on top (max 45/round)

Prediction points also add to your main leaderboard total.

**Duels**: 5 questions, most correct wins. Only the two duelists' answers
count toward the duel score.

## Achievements

| Badge | Unlocks when |
|---|---|
| First Blood | First correct answer |
| Hat Trick | 3 correct in a row |
| On Fire | 10 correct in a row |
| Trivia Master | 50 total correct |
| Century Club | 100 total correct |
| Daily Warrior | 7-day daily streak |
| Iron Will | 30-day daily streak |
| Perfect Podium | Exact P1-P2-P3 prediction |
| Prediction Pro | 5 prediction rounds played |
| Duelist | First duel win |
| Gladiator | 10 duel wins |

## Project structure

```
bot.py                  # entrypoint, wires up all handlers
config.py               # points, ranks, achievement definitions
ui.py                   # shared message-formatting helpers
database.py             # all SQLite persistence
questions.py            # trivia question bank
race_calendar.py        # official 2026 F1 calendar — update yearly
results_api.py          # Jolpica-F1 client for auto-fetching race results
trivia_handlers.py      # /quiz, /daily, /leaderboard, /mystats, achievements
duel_handlers.py        # /challenge and 1v1 duel flow
prediction_handlers.py  # /predict, /pick, /setresult, scoring
common_handlers.py      # /start, /help
jobs.py                 # weekly reset, auto-quiz restore, prediction automation
```

## Deploying so it runs 24/7

Long-polling, so it just needs to stay running:
- **VPS**: `tmux`/`screen`, or a `systemd` service running `python bot.py`
- **Docker**: `CMD ["python", "bot.py"]`, `BOT_TOKEN` as an env var
- **PaaS** (Railway, Render, Fly.io): set `BOT_TOKEN` as a secret, start
  command `python bot.py`

The SQLite file (`f1_quiz.db`) holds everything — scores, badges, duels,
predictions. Make sure your host has a **persistent disk**, or a redeploy
wipes it.

## Keeping things accurate

- **Trivia** (`questions.py`): historical facts don't go stale, but
  "current record holder"-type questions will eventually need updating.
- **Calendar** (`race_calendar.py`): update the `CALENDAR` list every
  off-season with next year's rounds and dates.
- **Results** (`results_api.py`): depends on the free, community-run
  Jolpica-F1 API staying up. If it ever goes away, `/setresult` still works
  as a fully manual path — nothing else breaks.
