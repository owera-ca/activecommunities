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
The `.env` file already contains your credentials. Edit it to adjust:
- `AC_CHECK_INTERVAL` – How often to check for spots (seconds, default 300 = 5 min)
- `AC_MIN_SPOTS` – Minimum open spots required before attempting registration (default 1)

## Usage

### Test / Single Check (with visible browser)
Check once and stop. Good for verifying the script works:
```bash
python register.py --check-once
```

### Run in Headless Mode (single check)
```bash
python register.py --check-once --headless
```

### Continuous Monitor Mode
Keeps checking every `AC_CHECK_INTERVAL` seconds and registers as soon as a spot opens:
```bash
python register.py
```

### Continuous Headless Monitor
```bash
python register.py --headless
```

## How It Works

1. **Login** – Logs in using credentials from `.env`, handles session conflicts.
2. **Search** – Navigates directly to the filtered search URL (center ID 131, "Ultra Swim 6").
3. **Spot Detection** – Parses each activity card for "X space(s) left" text or an active "Enroll Now" button.
4. **Enrollment** – Clicks "Enroll Now", selects participant, adds to cart, and proceeds to checkout.
5. **Confirmation** – Watches for the order confirmation page and logs success.
6. **Retry Loop** – If no spots are found, waits `AC_CHECK_INTERVAL` seconds and repeats.

## Logs
All output is logged to both the terminal and `registration.log` in the project directory.

## ⚠️ Notes
- The script stops monitoring as soon as a registration is successfully completed.
- If payment details are required at checkout, the script will pause at that step and log the current URL for manual completion.
- Run with a visible browser (`--check-once` without `--headless`) at least once to verify all steps work correctly for your account.
# activecommunities
