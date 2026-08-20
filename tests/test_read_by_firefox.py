"""Tests for read_by_firefox error handling — pins Sentry-capture + retry behavior.

S1: Selenium page-load timeout exhausts retries → return None, NO Sentry capture.
S2: Selenium NoSuchWindowException exhausts retries → return None, NO Sentry capture.
S3: A genuinely unexpected exception still IS captured to Sentry (regression guard), NOT retried.
S4: Operational failure on first attempt, success on retry → returns data from 2nd attempt.
S5: NoSuchWindowException on first attempt, success on retry → returns data from 2nd attempt.
"""
import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("SENTRY_DSN", "http://fake@localhost/1")

import pytest
from selenium.common.exceptions import NoSuchWindowException, TimeoutException


@pytest.fixture
def patched_webdriver():
    """Patch webdriver.Firefox so no real browser launches.

    Tests pre-seed `mock_wd.browsers` with the MagicMock browser(s) they want
    each Firefox() call to return (consumed in order). If the queue runs out,
    a fresh MagicMock is created automatically.
    `mock_wd.browsers_made` tracks every browser actually returned by Firefox().
    """
    with patch("reader_web_service.read_by_firefox.webdriver") as mock_wd:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.firefox.options import Options
        mock_wd.Options = Options
        mock_wd.common.by.By = By
        mock_wd.browsers = []          # queue: tests pre-seed browsers here
        mock_wd.browsers_made = []      # history: every browser actually returned

        def _make_browser(*args, **kwargs):
            if mock_wd.browsers:
                b = mock_wd.browsers.pop(0)
            else:
                b = MagicMock()
            mock_wd.browsers_made.append(b)
            return b

        mock_wd.Firefox.side_effect = _make_browser
        yield mock_wd


@pytest.fixture
def sentry_spy():
    """Capture sentry_sdk.capture_exception calls."""
    with patch("reader_web_service.read_by_firefox.sentry_sdk") as mock_sentry:
        yield mock_sentry.capture_exception


def test_page_load_timeout_not_captured_to_sentry(patched_webdriver, sentry_spy):
    """S1: browser.get() raising TimeoutException on every attempt → return None,
    NO Sentry capture, browser quit called once per attempt (retries exhausted).
    """
    from reader_web_service.read_by_firefox import MAX_ATTEMPTS, read_by_firefox
    for _ in range(MAX_ATTEMPTS):
        b = MagicMock()
        b.get.side_effect = TimeoutException("timed out")
        patched_webdriver.browsers.append(b)
    result = read_by_firefox("https://example.com", reader=False)
    assert result is None
    assert not sentry_spy.called, (
        "Selenium TimeoutException is operational, not a bug — must not hit Sentry"
    )
    assert len(patched_webdriver.browsers_made) == MAX_ATTEMPTS, (
        f"should have tried {MAX_ATTEMPTS} times (one browser per attempt)"
    )
    for b in patched_webdriver.browsers_made:
        assert b.quit.called, "every attempt's browser must be quit"


def test_no_such_window_not_captured_to_sentry(patched_webdriver, sentry_spy):
    """S2: find_element raising NoSuchWindowException on every attempt → return None,
    NO Sentry capture, retries exhausted.
    """
    from reader_web_service.read_by_firefox import MAX_ATTEMPTS, read_by_firefox
    for _ in range(MAX_ATTEMPTS):
        b = MagicMock()
        b.find_element.side_effect = NoSuchWindowException(
            "Browsing context has been discarded"
        )
        patched_webdriver.browsers.append(b)
    result = read_by_firefox("https://example.com", reader=False)
    assert result is None
    assert not sentry_spy.called, (
        "NoSuchWindowException is operational, not a bug — must not hit Sentry"
    )
    assert len(patched_webdriver.browsers_made) == MAX_ATTEMPTS


def test_unexpected_exception_still_captured_to_sentry(patched_webdriver, sentry_spy):
    """S3: a non-Selenium-runtime exception still hits Sentry, and is NOT retried."""
    from reader_web_service.read_by_firefox import read_by_firefox
    bad = MagicMock()
    bad.get.side_effect = RuntimeError("genuinely unexpected")
    patched_webdriver.browsers.append(bad)
    result = read_by_firefox("https://example.com", reader=False)
    assert result is None
    assert sentry_spy.called, "Unexpected errors must still be captured to Sentry"
    assert sentry_spy.call_count == 1, "Unexpected errors must NOT be retried"
    assert len(patched_webdriver.browsers_made) == 1, "Unexpected errors must NOT retry"


def test_operational_failure_then_success(patched_webdriver, sentry_spy):
    """S4: first attempt times out, second attempt succeeds → returns data from 2nd
    attempt, NO Sentry capture, exactly 2 browsers launched.
    """
    from reader_web_service.read_by_firefox import read_by_firefox

    bad = MagicMock()
    bad.get.side_effect = TimeoutException("timed out")
    patched_webdriver.browsers.append(bad)

    good = MagicMock()
    good.find_element.side_effect = [
        MagicMock(get_attribute=MagicMock(return_value="Example Domain")),
        MagicMock(get_attribute=MagicMock(return_value="<div>hi</div>")),
    ]
    patched_webdriver.browsers.append(good)

    result = read_by_firefox("https://example.com", reader=False)
    assert result is not None, "retry should have succeeded on 2nd attempt"
    assert result["title"] == "Example Domain"
    assert result["content"] == "<div>hi</div>"
    assert not sentry_spy.called, "operational failures must not hit Sentry even before retry"
    assert len(patched_webdriver.browsers_made) == 2, "exactly 2 attempts (fail then succeed)"
    assert bad.quit.called, "failed attempt's browser must be quit"
    assert good.quit.called, "successful attempt's browser must be quit"


def test_no_such_window_then_success(patched_webdriver, sentry_spy):
    """S5: first attempt's find_element raises NoSuchWindowException, second succeeds."""
    from reader_web_service.read_by_firefox import read_by_firefox

    bad = MagicMock()
    bad.find_element.side_effect = NoSuchWindowException("discarded")
    patched_webdriver.browsers.append(bad)

    good = MagicMock()
    good.find_element.side_effect = [
        MagicMock(get_attribute=MagicMock(return_value="Title")),
        MagicMock(get_attribute=MagicMock(return_value="<p>body</p>")),
    ]
    patched_webdriver.browsers.append(good)

    result = read_by_firefox("https://example.com", reader=False)
    assert result is not None
    assert result["title"] == "Title"
    assert result["content"] == "<p>body</p>"
    assert not sentry_spy.called
    assert len(patched_webdriver.browsers_made) == 2
