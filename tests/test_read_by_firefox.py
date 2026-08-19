"""Tests for read_by_firefox error handling — pins Sentry-capture behavior.

S1: Selenium page-load timeout (ReadTimeoutError in prod) must NOT be captured to Sentry.
S2: Selenium NoSuchWindowException (discarded browsing context) must NOT be captured to Sentry.
S3: A genuinely unexpected exception still IS captured to Sentry (regression guard).
"""
import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("SENTRY_DSN", "http://fake@localhost/1")

import pytest
from selenium.common.exceptions import NoSuchWindowException, TimeoutException


@pytest.fixture
def fake_browser():
    """A MagicMock standing in for a selenium WebDriver."""
    return MagicMock()


@pytest.fixture
def patched_webdriver(fake_browser):
    """Patch webdriver.Firefox so no real browser launches."""
    with patch("reader_web_service.read_by_firefox.webdriver") as mock_wd:
        mock_wd.Firefox.return_value = fake_browser
        # Also expose the real Options/By used at import time on the patched module
        from selenium.webdriver.common.by import By
        from selenium.webdriver.firefox.options import Options
        mock_wd.Options = Options
        mock_wd.common.by.By = By
        yield mock_wd


@pytest.fixture
def sentry_spy():
    """Capture sentry_sdk.capture_exception calls."""
    with patch("reader_web_service.read_by_firefox.sentry_sdk") as mock_sentry:
        yield mock_sentry.capture_exception


def test_page_load_timeout_not_captured_to_sentry(patched_webdriver, fake_browser, sentry_spy):
    """S1: browser.get() raising TimeoutException → return None, NO Sentry capture.

    Reproduces Bugsink issue FIREFOX_READER_WEB_SERVICE-1 (ReadTimeoutError
    surfaced when browser.get hangs past Selenium's page-load timeout).
    """
    from reader_web_service.read_by_firefox import read_by_firefox
    fake_browser.get.side_effect = TimeoutException("timed out")
    result = read_by_firefox("https://example.com", reader=False)
    assert result is None
    assert not sentry_spy.called, (
        "Selenium TimeoutException is operational, not a bug — must not hit Sentry"
    )
    fake_browser.quit.assert_called_once()


def test_no_such_window_not_captured_to_sentry(patched_webdriver, fake_browser, sentry_spy):
    """S2: find_element raising NoSuchWindowException → return None, NO Sentry capture.

    Reproduces Bugsink issue FIREFOX_READER_WEB_SERVICE-2 (Browsing context
    has been discarded).
    """
    from reader_web_service.read_by_firefox import read_by_firefox
    # browser.get succeeds, then find_element blows up with discarded context
    fake_browser.find_element.side_effect = NoSuchWindowException(
        "Browsing context has been discarded"
    )
    result = read_by_firefox("https://example.com", reader=False)
    assert result is None
    assert not sentry_spy.called, (
        "NoSuchWindowException is operational, not a bug — must not hit Sentry"
    )
    fake_browser.quit.assert_called_once()


def test_unexpected_exception_still_captured_to_sentry(patched_webdriver, fake_browser, sentry_spy):
    """S3: a non-Selenium-runtime exception still hits Sentry (regression guard)."""
    from reader_web_service.read_by_firefox import read_by_firefox
    fake_browser.get.side_effect = RuntimeError("genuinely unexpected")
    result = read_by_firefox("https://example.com", reader=False)
    assert result is None
    assert sentry_spy.called, "Unexpected errors must still be captured to Sentry"
    fake_browser.quit.assert_called_once()
