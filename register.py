#!/usr/bin/env python3
"""
Active Communities - Ultra Swim 6 Registration Automation
Monitors available spots and auto-registers when a spot opens up.
"""

import os
import sys
import time
import logging
import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Load environment variables
load_dotenv()

# Configuration
AC_EMAIL = os.getenv("AC_EMAIL")
AC_PASSWORD = os.getenv("AC_PASSWORD")
AC_BASE_URL = os.getenv("AC_BASE_URL", "https://anc.ca.apm.activecommunities.com/toronto")
AC_ACTIVITY_NAME = os.getenv("AC_ACTIVITY_NAME", "Ultra Swim 6")
AC_CENTER_ID = os.getenv("AC_CENTER_ID", "131")
AC_MIN_SPOTS = int(os.getenv("AC_MIN_SPOTS", "1"))
AC_CHECK_INTERVAL = int(os.getenv("AC_CHECK_INTERVAL", "300"))
AC_MAX_RETRIES = int(os.getenv("AC_MAX_RETRIES", "3"))

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Search URL — open_spots filter tells the portal to only return activities with available spots
# This avoids brittle text-parsing of card content and mirrors what the "Open spots" button does
SEARCH_URL = (
    f"{AC_BASE_URL}/activity/search"
    f"?onlineSiteId=0"
    f"&center_ids={AC_CENTER_ID}"
    f"&open_spots={AC_MIN_SPOTS}"
    f"&activity_keyword={AC_ACTIVITY_NAME.replace(' ', '%20')}"
    f"&viewMode=list"
)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("registration.log"),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------------------------

def notify_telegram(message: str) -> None:
    """Send a message to the configured Telegram chat. Fails silently."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
        if resp.ok:
            logger.info("📨 Telegram notification sent.")
        else:
            logger.warning(f"Telegram API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.warning(f"Failed to send Telegram notification: {e}")


def get_telegram_chat_id() -> None:
    """Fetch and print the chat ID of whoever last messaged the bot (via getUpdates)."""
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN is not set in .env")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    resp = requests.get(url, timeout=10)
    data = resp.json()
    updates = data.get("result", [])
    if not updates:
        print(
            "No messages received yet.\n"
            "👉 Open Telegram, search for your bot, send it any message (e.g. /start), "
            "then run this command again."
        )
        return
    # Use the most recent update
    last = updates[-1]
    chat = last.get("message", {}).get("chat", {})
    chat_id = chat.get("id")
    first_name = chat.get("first_name", "")
    print(f"\n✅ Your Telegram chat ID is: {chat_id}  (name: {first_name})")
    print(f"Add this to your .env file:\n  TELEGRAM_CHAT_ID={chat_id}")


# ---------------------------------------------------------------------------


def login(page):
    """Log in to the Active Communities portal."""
    logger.info("Navigating to sign-in page...")
    page.goto(f"{AC_BASE_URL}/signin", wait_until="networkidle")

    # Fill email
    email_input = page.locator("input[placeholder*='Email'], input[type='email']").first
    email_input.wait_for(state="visible", timeout=15000)
    email_input.fill(AC_EMAIL)
    logger.info("Filled email.")

    # Fill password
    password_input = page.locator("input[placeholder*='Password'], input[type='password']").first
    password_input.fill(AC_PASSWORD)
    logger.info("Filled password.")

    # Click Sign In
    page.locator("button:has-text('Sign in'), button:has-text('Sign In')").first.click()
    logger.info("Clicked Sign In button.")

    # Handle "already logged in" modal if it appears
    try:
        yes_btn = page.locator("button:has-text('Yes')").first
        yes_btn.wait_for(state="visible", timeout=5000)
        yes_btn.click()
        logger.info("Dismissed 'already logged in' modal.")
    except PlaywrightTimeoutError:
        pass  # No modal, proceed normally

    # Wait for redirect to account page
    page.wait_for_url(f"**/myaccount**", timeout=20000)
    logger.info("✅ Login successful.")


def check_and_register(page) -> bool:
    """
    Navigate to search results filtered by open_spots, find Ultra Swim 6 with
    available spots, and enroll. Returns True if registration was completed.

    The open_spots URL parameter does the heavy lifting — if results appear,
    the portal guarantees they have at least AC_MIN_SPOTS available.
    """
    logger.info(
        f"Searching for '{AC_ACTIVITY_NAME}' at center ID {AC_CENTER_ID} "
        f"(open_spots >= {AC_MIN_SPOTS})..."
    )
    page.goto(SEARCH_URL, wait_until="networkidle")

    # Short wait for the results section to stabilise
    page.wait_for_timeout(2000)

    # Check for "No results found" — means all sessions are full
    no_results = page.locator(
        "text='No results found', [class*='no-result'], [class*='empty-result']"
    )
    if no_results.count() > 0:
        logger.info("All sessions are currently full (portal returned no results with open spots filter).")
        return False

    # Find activity cards — portal only returns cards with open spots
    cards = page.locator(".search-result-item, .an-activity-card, .activity-card-item").all()
    if not cards:
        logger.info("No activity cards found; all sessions likely full.")
        return False

    logger.info(f"🎯 Found {len(cards)} session(s) with open spot(s)!")

    for i, card in enumerate(cards):
        card_text = card.inner_text().strip().replace("\n", " | ")[:200]
        logger.info(f"Card {i + 1}: {card_text}")

        # Try the Enroll Now button directly on the card
        enroll_btn = card.locator("button:has-text('Enroll Now'), a:has-text('Enroll Now')").first
        try:
            if enroll_btn.is_visible(timeout=1000):
                logger.info(f"  → Clicking 'Enroll Now' on card {i + 1}...")
                return enroll(page, card, enroll_btn)
        except Exception:
            pass

        # Fallback: open the activity detail page and look for Enroll Now there
        activity_link = card.locator("a").first
        try:
            if activity_link.is_visible(timeout=1000):
                logger.info(f"  → Opening detail page for card {i + 1}...")
                activity_link.click()
                page.wait_for_load_state("networkidle")
                detail_enroll = page.locator("button:has-text('Enroll Now'), a:has-text('Enroll Now')").first
                try:
                    detail_enroll.wait_for(state="visible", timeout=6000)
                    return enroll(page, page, detail_enroll)
                except PlaywrightTimeoutError:
                    logger.info("  → No 'Enroll Now' button on detail page. Going back.")
                    page.go_back()
                    page.wait_for_load_state("networkidle")
        except Exception:
            pass

    logger.info("Open spot(s) detected but could not find an active Enroll Now button.")
    return False


def enroll(page, card, enroll_btn) -> bool:
    """Click Enroll Now and complete the registration flow."""
    try:
        enroll_btn.click()
        logger.info("Clicked 'Enroll Now'.")
        page.wait_for_load_state("networkidle")
    except Exception as e:
        logger.error(f"Failed to click Enroll Now: {e}")
        return False

    # --- Step: Select Participant ---
    # The portal prompts to select a household member
    try:
        participant_section = page.locator(".participant-selection, .household-member-list, [class*='participant']")
        participant_section.wait_for(state="visible", timeout=10000)
        logger.info("Participant selection screen found.")

        # Select the first available participant (primary account holder)
        first_participant = page.locator(
            "input[type='radio']:not([disabled]), button:has-text('Select'), "
            ".household-member-list li:first-child button"
        ).first
        if first_participant.is_visible():
            first_participant.click()
            logger.info("Selected first participant.")

        # Click Continue/Next
        continue_btn = page.locator(
            "button:has-text('Continue'), button:has-text('Next'), button:has-text('Add to Cart')"
        ).first
        continue_btn.wait_for(state="visible", timeout=8000)
        continue_btn.click()
        logger.info("Clicked Continue after participant selection.")
        page.wait_for_load_state("networkidle")
    except PlaywrightTimeoutError:
        logger.info("No participant selection screen (may have auto-selected).")

    # --- Step: Add to Cart ---
    try:
        add_to_cart_btn = page.locator(
            "button:has-text('Add to Cart'), button:has-text('Proceed to Checkout'), "
            "button:has-text('Add To Cart')"
        ).first
        add_to_cart_btn.wait_for(state="visible", timeout=8000)
        add_to_cart_btn.click()
        logger.info("Clicked 'Add to Cart'.")
        page.wait_for_load_state("networkidle")
    except PlaywrightTimeoutError:
        logger.info("No 'Add to Cart' button found; may already be in cart flow.")

    # --- Step: Checkout ---
    try:
        checkout_btn = page.locator(
            "button:has-text('Checkout'), button:has-text('Check Out'), a:has-text('Checkout')"
        ).first
        checkout_btn.wait_for(state="visible", timeout=8000)
        checkout_btn.click()
        logger.info("Clicked 'Checkout'.")
        page.wait_for_load_state("networkidle")
    except PlaywrightTimeoutError:
        logger.warning("No checkout button found. Enrollment may require manual payment completion.")
        logger.info(f"Current URL: {page.url}")
        return False

    # --- Step: Complete Payment / Confirm ---
    try:
        # Look for order confirmation
        page.wait_for_selector(
            ".order-confirmation, .receipt, [class*='confirmation'], h1:has-text('Confirmation')",
            timeout=15000
        )
        logger.info("✅ Registration completed successfully! Order confirmation found.")
        logger.info(f"Confirmation page URL: {page.url}")
        return True
    except PlaywrightTimeoutError:
        logger.warning(
            "Did not reach confirmation page automatically. "
            "Payment details may be required manually."
        )
        logger.info(f"Current URL: {page.url}")
        return False


def run_monitor(headless: bool = False):
    """Main monitoring loop. Checks for spots every AC_CHECK_INTERVAL seconds."""
    logger.info("=" * 60)
    logger.info("Active Communities - Registration Monitor")
    logger.info(f"Activity: {AC_ACTIVITY_NAME}")
    logger.info(f"Center ID: {AC_CENTER_ID}")
    logger.info(f"Min Spots Required: {AC_MIN_SPOTS}")
    logger.info(f"Check Interval: {AC_CHECK_INTERVAL}s")
    logger.info("=" * 60)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless, slow_mo=500)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # Login once
        retries = 0
        while retries < AC_MAX_RETRIES:
            try:
                login(page)
                break
            except Exception as e:
                retries += 1
                logger.error(f"Login attempt {retries} failed: {e}")
                if retries >= AC_MAX_RETRIES:
                    msg = f"❌ Login failed after {AC_MAX_RETRIES} attempts. Monitor stopped."
                    logger.error(msg)
                    notify_telegram(msg)
                    browser.close()
                    return
                time.sleep(10)

        # Monitor loop
        check_count = 0
        while True:
            check_count += 1
            logger.info(f"\n--- Check #{check_count} ---")
            try:
                registered = check_and_register(page)
                if registered:
                    msg = (
                        f"🎉 Successfully registered for {AC_ACTIVITY_NAME}!\n"
                        f"Check your Active Communities account to confirm."
                    )
                    logger.info(msg)
                    notify_telegram(msg)
                    break
                else:
                    notify_telegram(
                        f"⏳ Check #{check_count}: No open spots for {AC_ACTIVITY_NAME}.\n"
                        f"Next check in {AC_CHECK_INTERVAL // 60} min "
                        f"({AC_CHECK_INTERVAL} s)."
                    )
            except Exception as e:
                err_msg = f"❌ Check #{check_count} error: {e}"
                logger.error(err_msg)
                notify_telegram(err_msg)
                # Try to recover
                try:
                    page.goto(AC_BASE_URL, wait_until="networkidle")
                except Exception:
                    pass

            logger.info(f"⏳ Next check in {AC_CHECK_INTERVAL} seconds...")
            time.sleep(AC_CHECK_INTERVAL)

        browser.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Active Communities Registration Monitor")
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (no GUI). Default: visible browser.",
    )
    parser.add_argument(
        "--check-once",
        action="store_true",
        default=False,
        help="Run a single check and exit (useful for testing).",
    )
    parser.add_argument(
        "--get-chat-id",
        action="store_true",
        default=False,
        help="Fetch and print your Telegram chat ID (message the bot first, then run this).",
    )
    args = parser.parse_args()

    if args.get_chat_id:
        get_telegram_chat_id()
    elif args.check_once:
        # Single check mode for testing
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=args.headless, slow_mo=500)
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()
            try:
                login(page)
                registered = check_and_register(page)
                if registered:
                    notify_telegram(
                        f"🎉 Successfully registered for {AC_ACTIVITY_NAME}!\n"
                        "Check your Active Communities account to confirm."
                    )
                else:
                    logger.info("No open spots found in this single check.")
                    notify_telegram(
                        f"⏳ Single check: No open spots for {AC_ACTIVITY_NAME} right now."
                    )
            except Exception as e:
                logger.error(f"Error in single check: {e}")
            finally:
                input("Press Enter to close browser...")
                browser.close()
    else:
        run_monitor(headless=args.headless)

