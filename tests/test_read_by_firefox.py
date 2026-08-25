"""Tests for read_by_firefox error handling — pins Sentry-capture + retry behavior.

S1: Selenium page-load timeout exhausts retries → return None, NO Sentry capture.
S2: Selenium NoSuchWindowException exhausts retries → return None, NO Sentry capture.
S3: A genuinely unexpected exception still IS captured to Sentry (regression guard), NOT retried.
S4: Operational failure on first attempt, success on retry → returns data from 2nd attempt.
S5: NoSuchWindowException on first attempt, success on retry → returns data from 2nd attempt.
S6: URL without a scheme (e.g. '2ip.ru') is normalised to http:// before browser.get
    (Bugsink FIREFOX_READER_WEB_SERVICE-3: InvalidArgumentException).
S7: Page with no <title> tag → returns {title:'', content:...}, NO Sentry capture
    (Bugsink FIREFOX_READER_WEB_SERVICE-4: NoSuchElementException).
S8: Warm-up DNS lookup (socket.gethostbyname) fails with gaierror → warm-up is
    skipped, target URL still loads, NO Sentry capture
    (Bugsink FIREFOX_READER_WEB_SERVICE-5: gaierror on /ping).
S9: Warm-up navigation (browser.get to resolved IP) raises WebDriverException
    (e.g. about:neterror connectionFailure) → warm-up skipped, target URL still
    loads, NO Sentry capture
    (Bugsink FIREFOX_READER_WEB_SERVICE-6: WebDriverException on /ping).
S10: Target navigation (browser.get(url)) raises WebDriverException (Tor node
    unreachable → about:neterror) on every attempt → retries, return None, NO
    Sentry capture. Same operational class as TimeoutException.
S11: webdriver.Firefox() constructor itself raises WebDriverException (e.g.
    "Failed to decode response from marionette" — transient geckodriver/Firefox
    startup race) on first attempt, succeeds on retry → returns data from 2nd
    attempt, NO Sentry capture
    (Bugsink FIREFOX_READER_WEB_SERVICE-8: constructor failure escaped the
    retry loop because webdriver.Firefox() sat outside try/except).
"""
import os
import socket
from unittest.mock import MagicMock, patch

os.environ.setdefault("SENTRY_DSN", "http://fake@localhost/1")

import pytest
from selenium.common.exceptions import (
    InvalidArgumentException,
    NoSuchWindowException,
    TimeoutException,
    WebDriverException,
)


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
    good.title = "Example Domain"
    good.find_element.side_effect = [
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
    good.title = "Title"
    good.find_element.side_effect = [
        MagicMock(get_attribute=MagicMock(return_value="<p>body</p>")),
    ]
    patched_webdriver.browsers.append(good)

    result = read_by_firefox("https://example.com", reader=False)
    assert result is not None
    assert result["title"] == "Title"
    assert result["content"] == "<p>body</p>"
    assert not sentry_spy.called
    assert len(patched_webdriver.browsers_made) == 2


def test_schemeless_url_normalised_to_http(patched_webdriver, sentry_spy):
    """S6: '2ip.ru' (no scheme) is normalised to 'http://2ip.ru' before browser.get.

    Regression for Bugsink FIREFOX_READER_WEB_SERVICE-3: Selenium raises
    InvalidArgumentException when given a schemeless URL. We prepend 'http://'
    when no scheme is present.
    """
    from reader_web_service.read_by_firefox import read_by_firefox

    b = MagicMock()
    # Simulate real Selenium: InvalidArgumentException when browser.get gets a schemeless URL.
    # The warm-up get (http://<ip>/) succeeds; the target get with '2ip.ru' would raise.
    # After the fix, the code normalises before calling get, so no raise + title/content returned.
    call_state = {"count": 0}

    def fake_get(url):
        call_state["count"] += 1
        if "://" not in url:
            raise InvalidArgumentException(f'Expected "url" to be a valid URL, got {url}')

    b.get.side_effect = fake_get
    b.title = "2IP"
    b.find_element.side_effect = [
        MagicMock(get_attribute=MagicMock(return_value="<body>2ip</body>")),
    ]
    patched_webdriver.browsers.append(b)

    result = read_by_firefox("2ip.ru", reader=False)
    assert result is not None, "schemeless URL should be normalised, not crash"
    # The second browser.get (target URL) must carry the http:// scheme.
    target_url = b.get.call_args_list[1].args[0]
    assert target_url == "http://2ip.ru", (
        f"schemeless URL must be normalised to http:// — got {target_url!r}"
    )
    assert not sentry_spy.called, "normalised URL must not hit Sentry"


def test_missing_title_returns_empty_no_sentry(patched_webdriver, sentry_spy):
    """S7: page with no <title> tag → returns {title:'', content:...}, NO Sentry capture.

    Regression for Bugsink FIREFOX_READER_WEB_SERVICE-4: find_element(By.TAG_NAME,
    'title') raised NoSuchElementException, which escaped _OPERATIONAL_EXCEPTIONS
    and was captured to Sentry as a bug. Use browser.title (returns '' if absent).
    """
    from reader_web_service.read_by_firefox import read_by_firefox

    b = MagicMock()
    b.title = ""  # no <title> on the page — browser.title returns '' instead of raising
    # body is still present; find_element is now called only once (for body),
    # since title comes from browser.title.
    b.find_element.side_effect = [
        MagicMock(get_attribute=MagicMock(return_value="<p>body</p>")),
    ]
    patched_webdriver.browsers.append(b)

    result = read_by_firefox("https://example.com", reader=False)
    assert result is not None, "titleless page should still return content, not None"
    assert result["title"] == "", "missing title → empty string, not crash"
    assert result["content"] == "<p>body</p>"
    assert not sentry_spy.called, (
        "NoSuchElementException for missing <title> is operational, not a bug — "
        "must not hit Sentry (now avoided via browser.title)"
    )


def test_warmup_dns_failure_skips_warmup_no_sentry(patched_webdriver, sentry_spy):
    """S8: socket.gethostbyname('ifconfig.me') raising gaierror → warm-up skipped,
    target URL still loads, NO Sentry capture.

    Regression for Bugsink FIREFOX_READER_WEB_SERVICE-5: the warm-up DNS lookup
    ran on the host (outside Tor) and failed with 'Temporary failure in name
    resolution', escaping _OPERATIONAL_EXCEPTIONS, hitting Sentry, and aborting.
    The warm-up is best-effort — the target URL loads through Tor regardless.
    """
    from reader_web_service.read_by_firefox import read_by_firefox

    b = MagicMock()
    b.title = "Example Domain"
    b.find_element.side_effect = [
        MagicMock(get_attribute=MagicMock(return_value="<div>hi</div>")),
    ]
    patched_webdriver.browsers.append(b)

    with patch("reader_web_service.read_by_firefox.socket") as mock_socket:
        mock_socket.gethostbyname.side_effect = socket.gaierror(
            -3, "Temporary failure in name resolution"
        )
        result = read_by_firefox("https://example.com", reader=False)

    assert result is not None, "warm-up DNS failure must not abort the request"
    assert result["title"] == "Example Domain"
    assert result["content"] == "<div>hi</div>"
    # Target URL must still be opened (the second browser.get call).
    target_url = b.get.call_args_list[-1].args[0]
    assert target_url == "https://example.com", (
        f"target URL must still be opened after warm-up failure — got {target_url!r}"
    )
    assert not sentry_spy.called, (
        "warm-up DNS failure is operational, not a bug — must not hit Sentry"
    )


def test_warmup_navigation_failure_skips_warmup_no_sentry(patched_webdriver, sentry_spy):
    """S9: warm-up browser.get(http://<ip>/) raising WebDriverException → warm-up
    skipped, target URL still loads, NO Sentry capture.

    Regression for Bugsink FIREFOX_READER_WEB_SERVICE-6: the resolved IP was
    unreachable through Tor (about:neterror?e=connectionFailure), so
    browser.get raised WebDriverException, which escaped the warm-up's
    `except OSError` clause, hit the outer `except Exception`, was captured to
    Sentry as a bug, and aborted the request. The warm-up is best-effort — the
    target URL loads through Tor regardless.
    """
    from reader_web_service.read_by_firefox import read_by_firefox

    b = MagicMock()
    # Warm-up get raises WebDriverException (IP unreachable); target get succeeds.
    call_state = {"count": 0}

    def fake_get(url):
        call_state["count"] += 1
        if call_state["count"] == 1:
            # Warm-up to resolved IP unreachable — Firefox shows about:neterror.
            raise WebDriverException(
                "Reached error page: about:neterror?e=connectionFailure"
            )
        # target URL loads fine

    b.get.side_effect = fake_get
    b.title = "Example Domain"
    b.find_element.side_effect = [
        MagicMock(get_attribute=MagicMock(return_value="<div>hi</div>")),
    ]
    patched_webdriver.browsers.append(b)

    with patch("reader_web_service.read_by_firefox.socket") as mock_socket:
        mock_socket.gethostbyname.return_value = "34.160.111.145"
        result = read_by_firefox("https://example.com", reader=False)

    assert result is not None, "warm-up navigation failure must not abort the request"
    assert result["title"] == "Example Domain"
    assert result["content"] == "<div>hi</div>"
    # Target URL must still be opened (the second browser.get call).
    target_url = b.get.call_args_list[-1].args[0]
    assert target_url == "https://example.com", (
        f"target URL must still be opened after warm-up failure — got {target_url!r}"
    )
    assert not sentry_spy.called, (
        "warm-up navigation failure is operational, not a bug — must not hit Sentry"
    )


def test_target_webdriver_exception_retries_no_sentry(patched_webdriver, sentry_spy):
    """S10: target browser.get(url) raising WebDriverException on every attempt
    → return None, NO Sentry capture, MAX_ATTEMPTS retries.

    Regression for the gap left after FIREFOX_READER_WEB_SERVICE-6: when the
    Tor node is unreachable, Firefox shows about:neterror and Selenium raises
    WebDriverException from the *target* navigation (not just warm-up). That
    escaped _OPERATIONAL_EXCEPTIONS, hit Sentry, and aborted on the first
    attempt without retrying — even though it is the same operational class as
    TimeoutException (transient network failure, worth a fresh browser).
    """
    from reader_web_service.read_by_firefox import MAX_ATTEMPTS, read_by_firefox

    for _ in range(MAX_ATTEMPTS):
        b = MagicMock()
        # Warm-up succeeds; the target get raises WebDriverException (Tor node
        # unreachable → about:neterror?e=connectionFailure).
        call_state = {"count": 0}

        def fake_get(url):
            call_state["count"] += 1

        b.get.side_effect = [
            None,  # warm-up navigation to resolved IP
            WebDriverException("Reached error page: about:neterror?e=connectionFailure"),
        ]
        patched_webdriver.browsers.append(b)

    with patch("reader_web_service.read_by_firefox.socket") as mock_socket:
        mock_socket.gethostbyname.return_value = "34.160.111.145"
        result = read_by_firefox("https://example.com", reader=False)

    assert result is None, "WebDriverException from target must exhaust retries → None"
    assert not sentry_spy.called, (
        "WebDriverException from target navigation is operational, not a bug "
        "— must not hit Sentry"
    )
    assert len(patched_webdriver.browsers_made) == MAX_ATTEMPTS, (
        f"should retry {MAX_ATTEMPTS} times (one browser per attempt)"
    )
    for b in patched_webdriver.browsers_made:
        assert b.quit.called, "every attempt's browser must be quit"


def test_constructor_failure_retries_no_sentry(patched_webdriver, sentry_spy):
    """S11: webdriver.Firefox() raising WebDriverException on the first call
    (transient marionette/geckodriver startup failure), then succeeding on the
    second call → returns data from the 2nd attempt, NO Sentry capture.

    Regression for Bugsink FIREFOX_READER_WEB_SERVICE-8: the constructor
    `webdriver.Firefox(options=...)` sat OUTSIDE the try/except
    _OPERATIONAL_EXCEPTIONS block, so a WebDriverException raised during
    session creation escaped the retry loop, hit the caller as a 500, and was
    captured to Sentry as a bug. The fix moves the constructor inside the try
    block so constructor failures retry on a fresh browser (same operational
    class as a page-load timeout).
    """
    from reader_web_service.read_by_firefox import read_by_firefox

    # First Firefox() call raises WebDriverException during session creation.
    # Second Firefox() call succeeds and returns a working browser.
    good = MagicMock()
    good.title = "Example Domain"
    good.find_element.side_effect = [
        MagicMock(get_attribute=MagicMock(return_value="<div>hi</div>")),
    ]

    call_state = {"count": 0}

    def fake_firefox(*args, **kwargs):
        call_state["count"] += 1
        if call_state["count"] == 1:
            raise WebDriverException("Failed to decode response from marionette")
        return good

    patched_webdriver.Firefox.side_effect = fake_firefox

    result = read_by_firefox("https://example.com", reader=False)

    assert result is not None, (
        "constructor failure must retry on a fresh browser, not abort"
    )
    assert result["title"] == "Example Domain"
    assert result["content"] == "<div>hi</div>"
    assert not sentry_spy.called, (
        "WebDriverException from the constructor is operational (transient "
        "browser startup), not a bug — must not hit Sentry"
    )
    assert call_state["count"] == 2, "exactly 2 Firefox() calls (fail then succeed)"
    assert good.quit.called, "successful attempt's browser must be quit"
