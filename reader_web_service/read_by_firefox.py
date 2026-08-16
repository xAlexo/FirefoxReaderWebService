import json
import socket

import sentry_sdk
from loguru import logger as _log
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.wait import WebDriverWait

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

    browser = webdriver.Firefox(options=firefox_options)

    try:
        _log.debug(f'Opening: {url}')
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
    except Exception as e:
        sentry_sdk.capture_exception(e)
    finally:
        browser.quit()


if __name__ == '__main__':
    print(read_by_firefox('http://ifconfig.me/', False))
