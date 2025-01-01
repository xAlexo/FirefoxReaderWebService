import socket

import sentry_sdk
from loguru import logger as _log
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait

READER_URL = 'about:reader?url={}'

firefox_options = Options()
firefox_options.add_argument("--headless")
firefox_options.set_preference("permissions.default.image", 2)


def read_by_firefox(url, reader=True):
    _log.debug(f'read_by_firefox: {url}')

    browser = webdriver.Firefox(options=firefox_options)

    try:
        if reader:
            url = READER_URL.format(url)

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
                WebDriverWait(browser, 5).until(
                    ec.presence_of_element_located((By.CLASS_NAME, 'page'))
                )
            except Exception as e:
                _log.debug('Reader not found')
                _log.debug(f'{e}')
                _log.debug(f'{browser.page_source}')
                return

            _log.debug('Reader found')

            return {
                'title': browser.find_element(
                    By.CLASS_NAME, 'reader-title').get_attribute('innerHTML'),
                'content': browser.find_element(
                    By.CLASS_NAME, 'page').get_attribute('innerHTML').strip(),
            }

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
    # print(read_by_firefox('https://www.mirf.ru/serial/harli-kvinn-3-j-sezon-kak-lego-betmen-no-bez-lego/'))
    # print(read_by_firefox('https://300.ya.ru/3fOcYRBL', False))
