import json
import socket

import sentry_sdk
from loguru import logger as _log
from selenium import webdriver
from selenium.common.exceptions import NoSuchWindowException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.wait import WebDriverWait

# Operational Selenium failures (page-load timeout, discarded browsing context)
# are expected in production — they must NOT be captured to Sentry as bugs.
# They ARE retried: a transient timeout or crashed context often succeeds on a
# fresh browser instance.
_OPERATIONAL_EXCEPTIONS = (TimeoutException, NoSuchWindowException)
MAX_ATTEMPTS = 3

READABILITY_URL = 'https://cdn.jsdelivr.net/npm/@mozilla/readability@0.5.0/Readability.js'

_READABILITY_PARSE = """
try {
    var doc = document.cloneNode(true);
    var reader = new Readability(doc);
    var article = reader.parse();
    if (article) {
        return JSON.stringify({title: article.title, content: article.content});
    }
    return null;
} catch(e) {
    return null;
}
"""

firefox_options = Options()
firefox_options.add_argument("--headless")
firefox_options.set_preference("permissions.default.image", 2)


def read_by_firefox(url, reader=True):
    _log.debug(f'read_by_firefox: {url}')

    for attempt in range(1, MAX_ATTEMPTS + 1):
        browser = webdriver.Firefox(options=firefox_options)
        # ponytail: 30s ceiling — default Selenium page-load timeout is 300s (geckodriver
        # transport raises ReadTimeoutError at 120s). Keeping it explicit prevents the
        # 120s hang observed in Bugsink FIREFOX_READER_WEB_SERVICE-1.
        browser.set_page_load_timeout(30)

        try:
            _log.debug(f'Opening: {url} (attempt {attempt}/{MAX_ATTEMPTS})')
            ip = socket.gethostbyname('ifconfig.me')
            _log.debug(f'IP: {ip}')
            _log.debug('Opening by IP')
            browser.get(f'http://{ip}/')
            _log.debug('Opening by URL')
            browser.get(url)
            _log.debug('Opened')

            if reader:
                try:
                    browser.execute_script(
                        'var s = document.createElement("script"); s.src = arguments[0]; document.head.appendChild(s);',
                        READABILITY_URL,
                    )
                    WebDriverWait(browser, 5).until(
                        lambda d: d.execute_script('return typeof Readability !== "undefined"')
                    )
                    _log.debug('Readability.js loaded')
                except Exception as e:
                    _log.debug('Readability.js failed to load')
                    _log.debug(f'{e}')
                    return

                try:
                    result = browser.execute_script(_READABILITY_PARSE)
                    if not result:
                        _log.debug('Reader not found')
                        return
                    _log.debug('Reader found')
                    return json.loads(result)
                except Exception as e:
                    _log.debug('Reader parse failed')
                    _log.debug(f'{e}')
                    return

            return {
                'title': browser.find_element(
                    By.TAG_NAME, 'title').get_attribute('innerHTML'),
                'content': browser.find_element(
                    By.TAG_NAME, 'body').get_attribute('innerHTML').strip(),
            }
        except _OPERATIONAL_EXCEPTIONS as e:
            # Operational failures (timeout, discarded context) — retry on a fresh
            # browser, no Sentry capture. These are expected in production.
            _log.debug(f'operational selenium failure (attempt {attempt}/{MAX_ATTEMPTS}): {e}')
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return None
        finally:
            browser.quit()

    return None


if __name__ == '__main__':
    print(read_by_firefox('http://ifconfig.me/', False))
