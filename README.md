# Active Communities Registration Automation

Playwright-based Python script that monitors and auto-registers for **Ultra Swim 6** at **Ethennonnhawahstihnen' Community Recreation Centre** on the [Active Communities Toronto portal](https://anc.ca.apm.activecommunities.com/toronto/signin).

## Setup

### 1. Create a Virtual Environment
```bash
cd /Users/sandeepkumar/github/activecommunities
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure `.env`
The `.env` file contains your credentials. Edit it to adjust:
- `AC_CHECK_INTERVAL` – How often to check for spots (seconds, default 300 = 5 min)
- `AC_MIN_SPOTS` – Minimum open spots required before attempting registration (default 1)

### 4. Set Up Telegram Notifications

The script sends you a Telegram message after every check and on successful registration.

**Step 1** — Add your bot token to `.env`:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

**Step 2** — Open Telegram, search for your bot by name, and send it any message (e.g. `/start`).

**Step 3** — Run this command to fetch your chat ID automatically:
```bash
python register.py --get-chat-id
```
Output will look like:
```
✅ Your Telegram chat ID is: 889767431  (name: Sandeep)
Add this to your .env file:
  TELEGRAM_CHAT_ID=889767431
```

**Step 4** — Paste the chat ID into `.env`:
```
TELEGRAM_CHAT_ID=889767431
```

> If `TELEGRAM_CHAT_ID` is left empty, the script still works — it just won't send Telegram messages.

## Usage

| Command | What it does |
|---|---|
| `python register.py --get-chat-id` | Fetch your Telegram chat ID (one-time setup) |
| `python register.py --check-once` | Single check, visible browser (good for testing) |
| `python register.py --check-once --headless` | Single check, no browser window |
| `python register.py` | Continuous monitor, visible browser |
| `python register.py --headless` | Continuous monitor, no browser window |

### Run in the background (survives terminal close)
```bash
nohup python register.py --headless > registration.log 2>&1 &
echo "Monitor running, PID: $!"
```
To stop it: `kill <PID>`

## How It Works

1. **Login** – Logs in using credentials from `.env`, handles session conflicts.
2. **Search** – Uses the portal's `open_spots` URL filter (mirrors the "Open spots" button in the UI) so only sessions with available spots are returned.
3. **Spot Detection** – If any results appear, all have open spots; if "No results" is returned, all sessions are full.
4. **Enrollment** – Clicks "Enroll Now", selects participant, adds to cart, and proceeds to checkout.
5. **Confirmation** – Watches for the order confirmation page and logs success.
6. **Notifications** – Sends a Telegram message after every check, and on registration success or error.
7. **Retry Loop** – If no spots are found, waits `AC_CHECK_INTERVAL` seconds and repeats.

## Logs
All output is logged to both the terminal and `registration.log` in the project directory.

## ⚠️ Notes
- The script stops monitoring as soon as a registration is successfully completed.
- If payment details are required at checkout, the script will pause and log the current URL for manual completion.
- Run `--check-once` (without `--headless`) at least once to visually verify all steps work correctly for your account.
