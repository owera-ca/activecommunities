#!/usr/bin/env python3
"""
Unit tests for register.py

All browser interactions and network calls are mocked so these tests
run quickly and without real credentials or a live server.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# ---------------------------------------------------------------------------
# Patch environment variables BEFORE importing the module under test so that
# module-level constants (AC_EMAIL etc.) are set predictably.
# ---------------------------------------------------------------------------
TEST_ENV = {
    "AC_EMAIL": "test@example.com",
    "AC_PASSWORD": "testpass",
    "AC_BASE_URL": "https://anc.ca.apm.activecommunities.com/toronto",
    "AC_ACTIVITY_NAME": "Ultra Swim 6",
    "AC_CENTER_ID": "131",
    "AC_MIN_SPOTS": "1",
    "AC_CHECK_INTERVAL": "300",
    "AC_MAX_RETRIES": "3",
    "TELEGRAM_BOT_TOKEN": "fake_token",
    "TELEGRAM_CHAT_ID": "123456",
}

with patch.dict(os.environ, TEST_ENV):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import register


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_page():
    """Return a fully-mocked Playwright page object."""
    page = MagicMock()
    page.url = "https://anc.ca.apm.activecommunities.com/toronto/myaccount"
    return page


# ---------------------------------------------------------------------------
# Tests: notify_telegram
# ---------------------------------------------------------------------------

class TestNotifyTelegram(unittest.TestCase):

    @patch("register.requests.post")
    def test_sends_message_when_credentials_set(self, mock_post):
        mock_post.return_value = MagicMock(ok=True)
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "999"}):
            # Re-read module globals for this sub-test
            orig_token = register.TELEGRAM_BOT_TOKEN
            orig_chat = register.TELEGRAM_CHAT_ID
            register.TELEGRAM_BOT_TOKEN = "tok"
            register.TELEGRAM_CHAT_ID = "999"
            register.notify_telegram("hello")
            register.TELEGRAM_BOT_TOKEN = orig_token
            register.TELEGRAM_CHAT_ID = orig_chat

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert "sendMessage" in call_kwargs[0][0]

    @patch("register.requests.post")
    def test_silent_when_no_token(self, mock_post):
        orig_token = register.TELEGRAM_BOT_TOKEN
        register.TELEGRAM_BOT_TOKEN = ""
        register.notify_telegram("should not send")
        register.TELEGRAM_BOT_TOKEN = orig_token
        mock_post.assert_not_called()

    @patch("register.requests.post")
    def test_silent_when_no_chat_id(self, mock_post):
        orig_chat = register.TELEGRAM_CHAT_ID
        register.TELEGRAM_CHAT_ID = ""
        register.notify_telegram("should not send")
        register.TELEGRAM_CHAT_ID = orig_chat
        mock_post.assert_not_called()

    @patch("register.requests.post", side_effect=Exception("network error"))
    def test_does_not_raise_on_network_error(self, mock_post):
        """notify_telegram must never propagate exceptions."""
        # Should complete without raising
        register.notify_telegram("message")

    @patch("register.requests.post")
    def test_logs_warning_on_api_error(self, mock_post):
        mock_post.return_value = MagicMock(ok=False, status_code=400, text="Bad Request")
        with self.assertLogs("register", level="WARNING") as cm:
            register.notify_telegram("bad message")
        self.assertTrue(any("Telegram API error" in line for line in cm.output))


# ---------------------------------------------------------------------------
# Tests: get_telegram_chat_id
# ---------------------------------------------------------------------------

class TestGetTelegramChatId(unittest.TestCase):

    @patch("register.requests.get")
    def test_prints_chat_id_when_updates_exist(self, mock_get):
        mock_get.return_value = MagicMock(
            json=lambda: {
                "result": [
                    {"message": {"chat": {"id": 42, "first_name": "Alice"}}}
                ]
            }
        )
        orig_token = register.TELEGRAM_BOT_TOKEN
        register.TELEGRAM_BOT_TOKEN = "tok"
        from io import StringIO
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            register.get_telegram_chat_id()
        output = mock_stdout.getvalue()
        register.TELEGRAM_BOT_TOKEN = orig_token
        self.assertIn("42", output)

    @patch("register.requests.get")
    def test_prints_guidance_when_no_updates(self, mock_get):
        mock_get.return_value = MagicMock(json=lambda: {"result": []})
        orig_token = register.TELEGRAM_BOT_TOKEN
        register.TELEGRAM_BOT_TOKEN = "tok"
        from io import StringIO
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            register.get_telegram_chat_id()
        output = mock_stdout.getvalue()
        register.TELEGRAM_BOT_TOKEN = orig_token
        self.assertIn("No messages received", output)

    def test_prints_error_when_no_token(self):
        orig_token = register.TELEGRAM_BOT_TOKEN
        register.TELEGRAM_BOT_TOKEN = ""
        from io import StringIO
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            register.get_telegram_chat_id()
        output = mock_stdout.getvalue()
        register.TELEGRAM_BOT_TOKEN = orig_token
        self.assertIn("TELEGRAM_BOT_TOKEN", output)


# ---------------------------------------------------------------------------
# Tests: login
# ---------------------------------------------------------------------------

class TestLogin(unittest.TestCase):

    def _make_page(self, already_logged_in=False):
        page = MagicMock()
        page.url = "https://anc.ca.apm.activecommunities.com/toronto/myaccount"

        # email / password locators
        email_locator = MagicMock()
        password_locator = MagicMock()
        sign_in_locator = MagicMock()

        yes_locator = MagicMock()
        if already_logged_in:
            # Simulate modal appearing
            yes_locator.first.wait_for = MagicMock()
        else:
            # Simulate TimeoutError so the modal branch is skipped
            from playwright.sync_api import TimeoutError as PTE
            yes_locator.first.wait_for = MagicMock(side_effect=PTE("timeout"))

        def locator_side_effect(selector):
            if "email" in selector.lower() or "Email" in selector:
                return email_locator
            if "password" in selector.lower() or "Password" in selector:
                return password_locator
            if "Sign in" in selector or "Sign In" in selector:
                return sign_in_locator
            if "Yes" in selector:
                return yes_locator
            return MagicMock()

        page.locator = MagicMock(side_effect=locator_side_effect)
        return page, email_locator, password_locator

    def test_login_happy_path(self):
        page, email_loc, pw_loc = self._make_page(already_logged_in=False)
        register.login(page)
        email_loc.first.fill.assert_called_once_with("test@example.com")
        pw_loc.first.fill.assert_called_once_with("testpass")
        page.wait_for_url.assert_called_once()

    def test_login_dismisses_modal_when_already_logged_in(self):
        page, _, _ = self._make_page(already_logged_in=True)
        register.login(page)
        # Just check that no exception propagated
        page.wait_for_url.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: check_and_register — no results
# ---------------------------------------------------------------------------

class TestCheckAndRegisterNoSpots(unittest.TestCase):

    def test_returns_false_when_no_results_text_found(self):
        page = _mock_page()

        # "No results found" text is visible
        no_results_locator = MagicMock()
        no_results_locator.count.return_value = 1

        cards_locator = MagicMock()
        cards_locator.all.return_value = []

        def locator_side_effect(selector):
            if "no-result" in selector or "No results" in selector:
                return no_results_locator
            return cards_locator

        page.locator = MagicMock(side_effect=locator_side_effect)

        result = register.check_and_register(page)
        self.assertFalse(result)

    def test_returns_false_when_no_cards_found(self):
        page = _mock_page()

        no_results_locator = MagicMock()
        no_results_locator.count.return_value = 0

        cards_locator = MagicMock()
        cards_locator.all.return_value = []

        def locator_side_effect(selector):
            if "no-result" in selector or "No results" in selector:
                return no_results_locator
            return cards_locator

        page.locator = MagicMock(side_effect=locator_side_effect)

        result = register.check_and_register(page)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# Tests: check_and_register — spots found, enroll button visible on card
# ---------------------------------------------------------------------------

class TestCheckAndRegisterSpotsFound(unittest.TestCase):

    @patch("register.enroll", return_value=True)
    def test_returns_true_when_enroll_succeeds(self, mock_enroll):
        page = _mock_page()

        no_results_locator = MagicMock()
        no_results_locator.count.return_value = 0

        # Build a fake card with a visible Enroll Now button
        enroll_btn = MagicMock()
        enroll_btn.is_visible = MagicMock(return_value=True)

        card = MagicMock()
        card.inner_text.return_value = "Ultra Swim 6 | Monday | 10 spots"
        card.locator = MagicMock(return_value=MagicMock(first=enroll_btn))

        cards_locator = MagicMock()
        cards_locator.all.return_value = [card]

        def locator_side_effect(selector):
            if "no-result" in selector or "No results" in selector:
                return no_results_locator
            return cards_locator

        page.locator = MagicMock(side_effect=locator_side_effect)

        result = register.check_and_register(page)
        self.assertTrue(result)
        mock_enroll.assert_called_once()

    @patch("register.enroll", return_value=False)
    def test_returns_false_when_enroll_fails(self, mock_enroll):
        page = _mock_page()

        no_results_locator = MagicMock()
        no_results_locator.count.return_value = 0

        enroll_btn = MagicMock()
        enroll_btn.is_visible = MagicMock(return_value=True)

        card = MagicMock()
        card.inner_text.return_value = "Ultra Swim 6 | Tuesday"
        card.locator = MagicMock(return_value=MagicMock(first=enroll_btn))

        cards_locator = MagicMock()
        cards_locator.all.return_value = [card]

        def locator_side_effect(selector):
            if "no-result" in selector or "No results" in selector:
                return no_results_locator
            return cards_locator

        page.locator = MagicMock(side_effect=locator_side_effect)

        result = register.check_and_register(page)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# Tests: enroll — confirmation page reached
# ---------------------------------------------------------------------------

class TestEnroll(unittest.TestCase):

    def _make_enroll_page(self, participant_timeout=True, add_to_cart_timeout=True,
                          checkout_timeout=False, confirmation_found=True):
        from playwright.sync_api import TimeoutError as PTE

        page = _mock_page()
        enroll_btn = MagicMock()

        # Participant section
        participant_locator = MagicMock()
        if participant_timeout:
            participant_locator.wait_for = MagicMock(side_effect=PTE("timeout"))
        else:
            participant_locator.wait_for = MagicMock()

        # Add to cart button
        add_to_cart_locator = MagicMock()
        if add_to_cart_timeout:
            add_to_cart_locator.first.wait_for = MagicMock(side_effect=PTE("timeout"))
        else:
            add_to_cart_locator.first.wait_for = MagicMock()

        # Checkout button
        checkout_locator = MagicMock()
        if checkout_timeout:
            checkout_locator.first.wait_for = MagicMock(side_effect=PTE("timeout"))
        else:
            checkout_locator.first.wait_for = MagicMock()

        def locator_side_effect(selector):
            if "participant" in selector.lower() or "household" in selector.lower():
                return participant_locator
            if "Add to Cart" in selector or "Add To Cart" in selector:
                return add_to_cart_locator
            if "Checkout" in selector or "Check Out" in selector:
                return checkout_locator
            return MagicMock()

        page.locator = MagicMock(side_effect=locator_side_effect)

        # Confirmation selector
        if confirmation_found:
            page.wait_for_selector = MagicMock()
        else:
            page.wait_for_selector = MagicMock(side_effect=PTE("timeout"))

        return page, enroll_btn

    def test_returns_true_on_successful_confirmation(self):
        page, enroll_btn = self._make_enroll_page(
            participant_timeout=True,
            add_to_cart_timeout=True,
            checkout_timeout=False,
            confirmation_found=True,
        )
        card = MagicMock()
        result = register.enroll(page, card, enroll_btn)
        self.assertTrue(result)

    def test_returns_false_when_checkout_button_missing(self):
        page, enroll_btn = self._make_enroll_page(
            checkout_timeout=True,
            confirmation_found=False,
        )
        card = MagicMock()
        result = register.enroll(page, card, enroll_btn)
        self.assertFalse(result)

    def test_returns_false_when_enroll_click_raises(self):
        page = _mock_page()
        enroll_btn = MagicMock()
        enroll_btn.click = MagicMock(side_effect=Exception("click failed"))
        card = MagicMock()
        result = register.enroll(page, card, enroll_btn)
        self.assertFalse(result)

    def test_returns_false_when_no_confirmation_page(self):
        page, enroll_btn = self._make_enroll_page(
            participant_timeout=True,
            add_to_cart_timeout=True,
            checkout_timeout=False,
            confirmation_found=False,
        )
        card = MagicMock()
        result = register.enroll(page, card, enroll_btn)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# Tests: SEARCH_URL construction
# ---------------------------------------------------------------------------

class TestSearchUrl(unittest.TestCase):

    def test_search_url_contains_center_id(self):
        self.assertIn("center_ids=131", register.SEARCH_URL)

    def test_search_url_contains_open_spots(self):
        self.assertIn("open_spots=1", register.SEARCH_URL)

    def test_search_url_contains_activity_keyword(self):
        self.assertIn("Ultra%20Swim%206", register.SEARCH_URL)

    def test_search_url_contains_base_url(self):
        self.assertIn(register.AC_BASE_URL, register.SEARCH_URL)


# ---------------------------------------------------------------------------
# Tests: Configuration defaults
# ---------------------------------------------------------------------------

class TestConfiguration(unittest.TestCase):

    def test_default_check_interval_is_int(self):
        self.assertIsInstance(register.AC_CHECK_INTERVAL, int)

    def test_default_min_spots_is_int(self):
        self.assertIsInstance(register.AC_MIN_SPOTS, int)

    def test_default_max_retries_is_int(self):
        self.assertIsInstance(register.AC_MAX_RETRIES, int)

    def test_email_is_loaded(self):
        self.assertEqual(register.AC_EMAIL, "test@example.com")

    def test_password_is_loaded(self):
        self.assertEqual(register.AC_PASSWORD, "testpass")


if __name__ == "__main__":
    unittest.main()
