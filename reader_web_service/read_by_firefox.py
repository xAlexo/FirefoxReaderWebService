import json
from urllib.parse import urlparse

import sentry_sdk
from camoufox.sync_api import Camoufox
from loguru import logger as _log
from playwright.sync_api import Error as PlaywrightError

from reader_web_service.proxy_router import get_proxy_for_host

# Operational browser failures (navigation timeout, about:neterror from an
# unreachable Tor node, discarded browsing context, browser launch failure)
# are expected in production — they must NOT be captured to Sentry as bugs.
# They ARE retried: a transient timeout, crashed context, or dead Tor node
# often succeeds on a fresh browser instance. Playwright's TimeoutError
# subclasses Error, so one tuple covers the whole operational class.
_OPERATIONAL_EXCEPTIONS = (PlaywrightError,)
MAX_ATTEMPTS = 3

READABILITY_URL = 'https://cdn.jsdelivr.net/npm/@mozilla/readability@0.5.0/Readability.js'

_READABILITY_PARSE = """
() => {
    try {
        const doc = document.cloneNode(true);
        const reader = new Readability(doc);
        const article = reader.parse();
        if (article) {
            return JSON.stringify({title: article.title, content: article.content});
        }
        return null;
    } catch(e) {
        return null;
    }
}
"""


def _build_camoufox_kwargs():
    """Build Camoufox launch kwargs: headless, blocked images, SOCKS5 proxy.

    When a proxy is configured (default ``socks5h://127.0.0.1:9050`` from
    ``TOR_PROXY``), the browser routes all traffic through the local Tor
    SOCKS5 port. Playwright's proxy dict has no ``socks5h`` scheme, so it is
    normalised to ``socks5``; remote DNS (the ``h`` semantics) is preserved
    via ``network.proxy.socks_remote_dns = true`` so name resolution happens
    at the Tor proxy, preventing DNS leaks.
    """
    kwargs = {'headless': True, 'block_images': True, 'i_know_what_im_doing': True}

    proxy = get_proxy_for_host('')
    if proxy:
        parsed = urlparse(proxy)
        host = parsed.hostname or '127.0.0.1'
        port = parsed.port or 9050
        scheme = parsed.scheme or 'socks5'
        proxy_dict = {'server': f'{scheme}://{host}:{port}'}
        if parsed.username:
            proxy_dict['username'] = parsed.username
            proxy_dict['password'] = parsed.password or ''
        kwargs['proxy'] = proxy_dict
        # socks5h:// (remote DNS) is not a Playwright scheme; emulate it via
        # the Firefox preference so DNS resolves at the Tor proxy, not locally.
        kwargs['firefox_user_prefs'] = {'network.proxy.socks_remote_dns': True}
        _log.debug(f'Camoufox SOCKS5 proxy: {host}:{port}')

    return kwargs


def read_by_firefox(url, reader=True):
    _log.debug(f'read_by_firefox: {url}')

    # ponytail: browsers reject schemeless URLs (e.g. '2ip.ru') with
    # InvalidArgumentError. Prepend 'http://' when no scheme is present.
    # Matches Bugsink FIREFOX_READER_WEB_SERVICE-3 fix.
    if '://' not in url:
        url = f'http://{url}'

    for attempt in range(1, MAX_ATTEMPTS + 1):
        # ponytail: Camoufox() is a context manager — its __enter__ can raise
        # a PlaywrightError during launch (transient browser startup race),
        # and camoufox's own __enter__ teardown prevents session leaks (daijro/
        # camoufox#82). The constructor MUST sit inside the try/except
        # _OPERATIONAL_EXCEPTIONS block so it retries on a fresh browser
        # instead of escaping to the caller as a 500 + Sentry bug (matches
        # the Bugsink FIREFOX_READER_WEB_SERVICE-8 fix). The `with` block
        # guarantees browser close even when navigation raises.
        try:
            with Camoufox(**_build_camoufox_kwargs()) as browser:
                page = browser.new_page()
                # ponytail: 30s ceiling — default navigation timeout is 300s.
                # Keeping it explicit prevents the 120s+ hang observed in
                # Bugsink FIREFOX_READER_WEB_SERVICE-1.
                page.set_default_navigation_timeout(30_000)

                _log.debug(f'Opening: {url} (attempt {attempt}/{MAX_ATTEMPTS})')
                page.goto(url)

                # ponytail: unlike Selenium, Playwright's goto can resolve
                # an about:neterror page without raising (e.g. dead Tor
                # node). Undetected, /ping and /ip would false-positive on
                # Firefox's error page. Treat it as an operational failure.
                if page.url.startswith('about:neterror'):
                    raise PlaywrightError(f'Reached error page: {page.url}')

                _log.debug('Opened')

                if reader:
                    # ponytail: 5s ceiling on the CDN load+parse — a hung
                    # jsdelivr request fails fast instead of blocking.
                    page.set_default_timeout(5_000)
                    try:
                        page.add_script_tag(url=READABILITY_URL)
                    except Exception as e:
                        _log.debug('Readability.js failed to load')
                        _log.debug(f'{e}')
                        return None

                    try:
                        result = page.evaluate(_READABILITY_PARSE)
                        if not result:
                            _log.debug('Reader not found')
                            return None
                        _log.debug('Reader found')
                        return json.loads(result)
                    except Exception as e:
                        _log.debug('Reader parse failed')
                        _log.debug(f'{e}')
                        return None

                return {
                    # ponytail: page.title() returns '' when the page has no
                    # <title> tag, instead of raising — matches the Bugsink
                    # FIREFOX_READER_WEB_SERVICE-4 fix.
                    'title': page.title(),
                    'content': page.inner_html('body'),
                }
        except _OPERATIONAL_EXCEPTIONS as e:
            # Operational failures (timeout, neterror, closed context) — retry
            # on a fresh browser, no Sentry capture. These are expected in
            # production.
            _log.debug(f'operational browser failure (attempt {attempt}/{MAX_ATTEMPTS}): {e}')
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return None

    return None


if __name__ == '__main__':
    print(read_by_firefox('http://ifconfig.me/', False))
