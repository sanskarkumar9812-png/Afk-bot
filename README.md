# AFK + Reminders + Quote of the Day + Memes Telegram Bot

## AFK

- `/afk [reason]` — marks you AFK, with an optional reason (default: "AFK").
- **Admin-only in groups**: only group admins/the creator can run `/afk` in a
  group chat. Anyone can use it in a private chat with the bot, since there's
  no concept of "admin" there. Non-admins get a polite "Only group admins can
  use /afk here." message.
- Sending **any** message automatically clears your AFK status and the bot
  welcomes you back.
- If someone **replies to** or **@mentions** an AFK user, the bot tells them
  who's away, why, and for how long.
- AFK status is stored in a local SQLite file (`afk.db`), so it survives bot
  restarts.

## Reminders

- `/remind <time> <message>` — one-off reminder.
  - Example: `/remind 30m Take a break`, `/remind 2h Call mom`, `/remind 1d Renew subscription`
  - Time units: `s` seconds, `m` minutes, `h` hours, `d` days.
  - The bot pings you back in the same chat when it's due.
  - **Admin-only in groups**, same rule as `/afk`. Works for anyone in a
    private chat with the bot.

## Quote of the day

- `/quote` — sends a random quote right now (pulled from [ZenQuotes](https://zenquotes.io)).
- `/qotd on HH:MM` — schedules an automatic quote every day at that time
  (24-hour format, **UTC**), posted in the chat where you ran the command.
  - Example: `/qotd on 09:00`
- `/qotd off` — turns off the daily quote for that chat.
- Daily quote schedules are saved to SQLite, so they survive bot restarts.

## Random memes

- `/meme` — fetches and posts a random meme image (pulled from
  [meme-api.com](https://meme-api.com), which sources from Reddit).

## Setup

1. Talk to [@BotFather](https://t.me/BotFather) on Telegram, run `/newbot`,
   and copy the token it gives you.
2. Install dependencies (note the `[job-queue]` extra — it's needed for
   reminders and the daily quote scheduler):
   ```bash
   pip install -r requirements.txt
   ```
3. Set your bot token as an environment variable called `BOT_TOKEN` (don't
   hardcode it in `bot.py` — this matters especially if you ever push the
   code to GitHub):
   ```bash
   export BOT_TOKEN=your_token_here      # macOS/Linux
   set BOT_TOKEN=your_token_here         # Windows (cmd)
   ```
4. Run it:
   ```bash
   python bot.py
   ```
5. Add the bot to your group and **disable privacy mode** via BotFather
   (`/mybots` → your bot → Bot Settings → Group Privacy → Turn off) so it can
   see all messages, not just commands — this is required for the
   "mention/reply while AFK" feature to work in groups.

## How it works

- All AFK records live in a tiny SQLite table: `user_id`, `username`,
  `first_name`, `reason`, `since` (timestamp).
- Every incoming text message runs through one handler that:
  1. Clears AFK for the sender if they had it set.
  2. Checks if the message is a reply to an AFK user.
  3. Checks if the message @mentions an AFK user by username.
- This mirrors exactly what the bot in your screenshot is doing.

## Extending it

See the suggestions in the chat response for a long list of features you can
layer on top of this (welcome messages, warns, filters, notes, locks, etc.).
The same `Application` object and message-handler pattern used here scales
to all of them — you just add more `CommandHandler` / `MessageHandler`
registrations in `main()`.

## Deploying on Railway (so it runs 24/7)

1. Push this folder to a GitHub repo (Railway deploys from GitHub).
2. On [railway.com](https://railway.com), click **New Project → Deploy from
   GitHub repo**, and pick your repo. Railway auto-detects Python from
   `requirements.txt`.
3. Go to the service's **Variables** tab and add `BOT_TOKEN` with your real
   token as the value. Never commit the token itself to GitHub.
4. Railway will use the included `Procfile` (`worker: python bot.py`) to run
   the bot as a background worker — no web server or public URL needed,
   since this bot uses long polling.
5. Open the **Deployments → Logs** tab and confirm you see `Bot is
   running...` with no errors.
6. That's it — Railway keeps the process alive continuously and restarts it
   automatically if it crashes. Note: the `afk.db` SQLite file lives on
   Railway's ephemeral filesystem, so if you want AFK/QOTD data to survive a
   redeploy, add a Railway **Volume** and point `DB_PATH` at a file inside
   it (e.g. `/data/afk.db`).
