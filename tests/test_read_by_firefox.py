"""Tests for read_by_firefox error handling — pins Sentry-capture + retry behavior.

S1: Navigation timeout exhausts retries → return None, NO Sentry capture.
S2: Playwright Error (closed context) exhausts retries → return None, NO Sentry capture.
S3: A genuinely unexpected exception still IS captured to Sentry (regression guard), NOT retried.
S4: Operational failure on first attempt, success on retry → returns data from 2nd attempt.
S5: Playwright Error on first attempt, success on retry → returns data from 2nd attempt.
S6: URL without a scheme (e.g. '2ip.ru') is normalised to http:// before page.goto
    (Bugsink FIREFOX_READER_WEB_SERVICE-3: InvalidArgumentError).
S7: Page with no <title> tag → returns {title:'', content:...}, NO Sentry capture
    (Bugsink FIREFOX_READER_WEB_SERVICE-4: page.title() returns '' if absent).
S10: Target navigation lands on about:neterror (Tor node unreachable) on every
    attempt → retries, return None, NO Sentry capture. Playwright's goto can
    resolve error pages without raising, so read_by_firefox detects them via
    page.url — undetected, /ping and /ip would false-positive on the error page.
S11: Camoufox() launch itself raises PlaywrightError (transient browser startup
    race) on first attempt, succeeds on retry → returns data from 2nd attempt,
    NO Sentry capture (Bugsink FIREFOX_READER_WEB_SERVICE-8: constructor
    failures must retry on a fresh browser).

Warm-up scenarios S8/S9 were deleted with the warm-up navigation itself —
entrypoint.sh already waits for Tor bootstrap 100% before the app starts.

P8: Readability.js CDN load fails (add_script_tag timeout) → return None,
    NO Sentry capture, no retry (parse-phase failures return, not retry).
P9: Readability parse returns null → return None, NO Sentry capture.
P10: about:neterror on first attempt, normal page on second → data from 2nd
    attempt, NO Sentry capture (neterror path drives the retry).
"""
import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("SENTRY_DSN", "http://fake@localhost/1")

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


class MockCamoufoxContext(MagicMock):
    """Context-manager stand-in for Camoufox: __enter__ returns a queued mock
    browser, __exit__ records the teardown."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.__enter__.side_effect = None

    # MagicMock auto-generates __enter__/__exit__; we wire them in the fixture.


@pytest.fixture
def patched_camoufox():
    """Patch read_by_firefox.Camoufox so no real browser launches.

    Tests pre-seed `mock_cm.browsers` with the MagicMock browser(s) they want
    each Camoufox() call to enter (consumed in order). If the queue runs out,
    a fresh MagicMock is created automatically. `mock_cm.entered` /
    `mock_cm.exited` track every browser actually entered/exited.
    """
    with patch("reader_web_service.read_by_firefox.Camoufox") as mock_cm:
        mock_cm.browsers = []      # queue: tests pre-seed browsers here
        mock_cm.entered = []       # history: every browser actually entered
        mock_cm.exited = []        # history: every browser actually exited
        mock_cm.enter_side_effect = None  # optional: [exc, ...] raise on __enter__ by index

        # Wire __enter__/__exit__ on the instance MagicMock returned by Camoufox().
        # enter_side_effect: list of exceptions (or None) raised on __enter__ by
        # attempt index — a not-None entry raises instead of entering a browser.
        def _enter(*args, **kwargs):
            effects = mock_cm.enter_side_effect
            if effects is not None:
                n = mock_cm._enter_invocations
                mock_cm._enter_invocations += 1
                if n < len(effects) and effects[n] is not None:
                    raise effects[n]
            if mock_cm.browsers:
                b = mock_cm.browsers.pop(0)
            else:
                b = MagicMock()
            mock_cm.entered.append(b)
            return b

        def _exit(*args, **kwargs):
            if mock_cm.entered:
                mock_cm.exited.append(mock_cm.entered[-1])
            return False

        mock_cm._enter_invocations = 0
        mock_cm.return_value.__enter__.side_effect = _enter
        mock_cm.return_value.__exit__.side_effect = _exit
        yield mock_cm


def _good_page(title="Example Domain", content="<div>hi</div>", url="https://example.com"):
    """A mock page whose navigation succeeds and returns title/content."""
    p = MagicMock()
    p.url = url
    p.title.return_value = title
    p.inner_html.return_value = content
    return p


@pytest.fixture
def sentry_spy():
    """Capture sentry_sdk.capture_exception calls."""
    with patch("reader_web_service.read_by_firefox.sentry_sdk") as mock_sentry:
        yield mock_sentry.capture_exception


def test_navigation_timeout_not_captured_to_sentry(patched_camoufox, sentry_spy):
    """S1: page.goto raising TimeoutError on every attempt → return None, NO
    Sentry capture, one browser per attempt, every attempt exited.
    """
    from reader_web_service.read_by_firefox import MAX_ATTEMPTS, read_by_firefox
    for _ in range(MAX_ATTEMPTS):
        b = MagicMock()
        page = MagicMock()
        page.goto.side_effect = PlaywrightTimeoutError("Timeout 30000ms exceeded")
        b.new_page.return_value = page
        patched_camoufox.browsers.append(b)
    result = read_by_firefox("https://example.com", reader=False)
    assert result is None
    assert not sentry_spy.called, (
        "Playwright TimeoutError is operational, not a bug — must not hit Sentry"
    )
    assert len(patched_camoufox.entered) == MAX_ATTEMPTS, (
        f"should have tried {MAX_ATTEMPTS} times (one browser per attempt)"
    )
    assert len(patched_camoufox.exited) == MAX_ATTEMPTS, "every attempt's browser must be exited"


def test_closed_context_not_captured_to_sentry(patched_camoufox, sentry_spy):
    """S2: page.goto raising Error('context closed') on every attempt → return
    None, NO Sentry capture, retries exhausted.
    """
    from reader_web_service.read_by_firefox import MAX_ATTEMPTS, read_by_firefox
    for _ in range(MAX_ATTEMPTS):
        b = MagicMock()
        page = MagicMock()
        page.goto.side_effect = PlaywrightError("Target page, context or browser has been closed")
        b.new_page.return_value = page
        patched_camoufox.browsers.append(b)
    result = read_by_firefox("https://example.com", reader=False)
    assert result is None
    assert not sentry_spy.called, (
        "Playwright Error (closed context) is operational, not a bug — must not hit Sentry"
    )
    assert len(patched_camoufox.entered) == MAX_ATTEMPTS


def test_unexpected_exception_still_captured_to_sentry(patched_camoufox, sentry_spy):
    """S3: a non-operational exception still hits Sentry, and is NOT retried."""
    from reader_web_service.read_by_firefox import read_by_firefox
    b = MagicMock()
    page = MagicMock()
    page.goto.side_effect = RuntimeError("genuinely unexpected")
    b.new_page.return_value = page
    patched_camoufox.browsers.append(b)
    result = read_by_firefox("https://example.com", reader=False)
    assert result is None
    assert sentry_spy.called, "Unexpected errors must still be captured to Sentry"
    assert sentry_spy.call_count == 1, "Unexpected errors must NOT be retried"
    assert len(patched_camoufox.entered) == 1, "Unexpected errors must NOT retry"


def test_operational_failure_then_success(patched_camoufox, sentry_spy):
    """S4: first attempt times out, second attempt succeeds → returns data
    from 2nd attempt, NO Sentry capture, exactly 2 browsers launched.
    """
    from reader_web_service.read_by_firefox import read_by_firefox

    bad = MagicMock()
    bad_page = MagicMock()
    bad_page.goto.side_effect = PlaywrightTimeoutError("Timeout 30000ms exceeded")
    bad.new_page.return_value = bad_page
    patched_camoufox.browsers.append(bad)

    good = MagicMock()
    good.new_page.return_value = _good_page(title="Example Domain", content="<div>hi</div>")
    patched_camoufox.browsers.append(good)

    result = read_by_firefox("https://example.com", reader=False)
    assert result is not None, "retry should have succeeded on 2nd attempt"
    assert result["title"] == "Example Domain"
    assert result["content"] == "<div>hi</div>"
    assert not sentry_spy.called, "operational failures must not hit Sentry even before retry"
    assert len(patched_camoufox.entered) == 2, "exactly 2 attempts (fail then succeed)"
    assert len(patched_camoufox.exited) == 2, "both attempts' browsers must be exited"


def test_error_then_success(patched_camoufox, sentry_spy):
    """S5: first attempt's goto raises PlaywrightError, second succeeds."""
    from reader_web_service.read_by_firefox import read_by_firefox

    bad = MagicMock()
    bad_page = MagicMock()
    bad_page.goto.side_effect = PlaywrightError("Target closed")
    bad.new_page.return_value = bad_page
    patched_camoufox.browsers.append(bad)

    good = MagicMock()
    good.new_page.return_value = _good_page(title="Title", content="<p>body</p>")
    patched_camoufox.browsers.append(good)

    result = read_by_firefox("https://example.com", reader=False)
    assert result is not None
    assert result["title"] == "Title"
    assert result["content"] == "<p>body</p>"
    assert not sentry_spy.called
    assert len(patched_camoufox.entered) == 2


def test_schemeless_url_normalised_to_http(patched_camoufox, sentry_spy):
    """S6: '2ip.ru' (no scheme) is normalised to 'http://2ip.ru' before page.goto.

    Regression for Bugsink FIREFOX_READER_WEB_SERVICE-3: the browser rejects a
    schemeless URL with InvalidArgumentError. We prepend 'http://' when no
    scheme is present.
    """
    from reader_web_service.read_by_firefox import read_by_firefox

    b = MagicMock()
    page = _good_page(title="2IP", content="<body>2ip</body>", url="http://2ip.ru")
    b.new_page.return_value = page
    patched_camoufox.browsers.append(b)

    result = read_by_firefox("2ip.ru", reader=False)
    assert result is not None, "schemeless URL should be normalised, not crash"
    target_url = page.goto.call_args.args[0]
    assert target_url == "http://2ip.ru", (
        f"schemeless URL must be normalised to http:// — got {target_url!r}"
    )
    assert not sentry_spy.called, "normalised URL must not hit Sentry"


def test_missing_title_returns_empty_no_sentry(patched_camoufox, sentry_spy):
    """S7: page with no <title> tag → returns {title:'', content:...}, NO Sentry capture.

    Regression for Bugsink FIREFOX_READER_WEB_SERVICE-4: page.title() returns
    '' when the page has no <title> tag, instead of raising.
    """
    from reader_web_service.read_by_firefox import read_by_firefox

    b = MagicMock()
    b.new_page.return_value = _good_page(title="", content="<p>body</p>")
    patched_camoufox.browsers.append(b)

    result = read_by_firefox("https://example.com", reader=False)
    assert result is not None, "titleless page should still return content, not None"
    assert result["title"] == "", "missing title → empty string, not crash"
    assert result["content"] == "<p>body</p>"
    assert not sentry_spy.called, (
        "missing <title> is operational, not a bug — must not hit Sentry"
    )


def test_neterror_on_target_retries_no_sentry(patched_camoufox, sentry_spy):
    """S10: target navigation lands on about:neterror on every attempt →
    return None, NO Sentry capture, MAX_ATTEMPTS retries.

    Playwright's page.goto resolves error pages without raising, so
    read_by_firefox must detect them via page.url. Undetected, /ping and /ip
    would false-positive on Firefox's error page.
    """
    from reader_web_service.read_by_firefox import MAX_ATTEMPTS, read_by_firefox

    for _ in range(MAX_ATTEMPTS):
        b = MagicMock()
        page = MagicMock()
        page.url = "about:neterror?e=connectionFailure"
        b.new_page.return_value = page
        patched_camoufox.browsers.append(b)

    result = read_by_firefox("https://example.com", reader=False)

    assert result is None, "about:neterror must exhaust retries → None"
    assert not sentry_spy.called, (
        "about:neterror is operational (dead Tor node), not a bug — must not hit Sentry"
    )
    assert len(patched_camoufox.entered) == MAX_ATTEMPTS, (
        f"should retry {MAX_ATTEMPTS} times (one browser per attempt)"
    )
    assert len(patched_camoufox.exited) == MAX_ATTEMPTS, "every attempt's browser must be exited"


def test_constructor_failure_retries_no_sentry(patched_camoufox, sentry_spy):
    """S11: Camoufox() launch raising PlaywrightError on the first attempt
    (transient browser startup failure), then succeeding on the second call →
    returns data from the 2nd attempt, NO Sentry capture.

    Regression for Bugsink FIREFOX_READER_WEB_SERVICE-8: the launch must sit
    inside the retry loop's try/except so launch failures retry on a fresh
    browser instead of escaping as a 500 + Sentry bug.
    """
    from reader_web_service.read_by_firefox import read_by_firefox

    good = MagicMock()
    good.new_page.return_value = _good_page(title="Example Domain", content="<div>hi</div>")
    patched_camoufox.browsers.append(good)

    # First Camoufox().__enter__ raises (launch failure); second enters `good`.
    patched_camoufox.enter_side_effect = [PlaywrightError("Failed to launch browser")]

    result = read_by_firefox("https://example.com", reader=False)

    assert result is not None, (
        "constructor failure must retry on a fresh browser, not abort"
    )
    assert result["title"] == "Example Domain"
    assert result["content"] == "<div>hi</div>"
    assert not sentry_spy.called, (
        "PlaywrightError from the launch is operational (transient browser "
        "startup), not a bug — must not hit Sentry"
    )
    assert len(patched_camoufox.entered) == 1, "exactly 1 successful launch (2nd call)"
    assert len(patched_camoufox.exited) == 1, "successful attempt's browser must be exited"


def test_readability_load_failure_returns_none_no_sentry(patched_camoufox, sentry_spy):
    """P8: Readability.js CDN load times out (add_script_tag) with reader=True
    → returns None, NO Sentry capture, NO retry (parse-phase failures return).
    """
    from reader_web_service.read_by_firefox import read_by_firefox

    b = MagicMock()
    page = _good_page()
    page.add_script_tag.side_effect = PlaywrightTimeoutError("Timeout 5000ms exceeded")
    b.new_page.return_value = page
    patched_camoufox.browsers.append(b)

    result = read_by_firefox("https://example.com", reader=True)

    assert result is None, "Readability load failure must return None"
    assert not sentry_spy.called, (
        "CDN load failure is operational, not a bug — must not hit Sentry"
    )
    assert len(patched_camoufox.entered) == 1, "parse-phase failures must NOT retry"


def test_readability_parse_none_returns_none_no_sentry(patched_camoufox, sentry_spy):
    """P9: Readability parse returns null (no article on the page) → return
    None, NO Sentry capture.
    """
    from reader_web_service.read_by_firefox import read_by_firefox

    b = MagicMock()
    page = _good_page()
    page.evaluate.return_value = None
    b.new_page.return_value = page
    patched_camoufox.browsers.append(b)

    result = read_by_firefox("https://example.com", reader=True)

    assert result is None, "reader-not-found must return None"
    assert not sentry_spy.called, "reader-not-found is operational, not a bug"


def test_neterror_then_success(patched_camoufox, sentry_spy):
    """P10: about:neterror on first attempt, normal page on second → data from
    2nd attempt, NO Sentry capture (neterror path drives the retry).
    """
    from reader_web_service.read_by_firefox import read_by_firefox

    bad = MagicMock()
    bad_page = MagicMock()
    bad_page.url = "about:neterror?e=connectionFailure"
    bad.new_page.return_value = bad_page
    patched_camoufox.browsers.append(bad)

    good = MagicMock()
    good.new_page.return_value = _good_page(title="Example Domain", content="<div>hi</div>")
    patched_camoufox.browsers.append(good)

    result = read_by_firefox("https://example.com", reader=False)

    assert result is not None, "neterror on 1st attempt must retry and succeed on 2nd"
    assert result["title"] == "Example Domain"
    assert result["content"] == "<div>hi</div>"
    assert not sentry_spy.called, "neterror retries are operational, not a bug"
    assert len(patched_camoufox.entered) == 2
