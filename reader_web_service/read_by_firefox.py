from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from loguru import logger as _log

READER_URL = 'about:reader?url={}'


def read_by_firefox(url, reader=True):
    _log.debug(f'read_by_firefox: {url}')

    display = Display(visible=False, size=(800, 600))
    display.start()

    browser = webdriver.Firefox()

    if reader:
        url = READER_URL.format(url)

    _log.debug(f'Opening: {url}')
    browser.get(url)

    try:
        if reader:
            WebDriverWait(browser, 30).until(
                ec.presence_of_element_located((By.ID, 'article'))
            )
            return {
                'title': browser.find_element(
                    By.CLASS_NAME, 'reader-title').get_attribute('innerHTML'),
                'content': browser.find_element(
                    By.ID, 'article').get_attribute('innerHTML').strip(),
            }

        return {
            'title': browser.find_element(
                By.TAG_NAME, 'title').get_attribute('innerHTML'),
            'content': browser.find_element(
                By.TAG_NAME, 'body').get_attribute('innerHTML').strip(),
        }
    finally:
        browser.quit()
        display.stop()


if __name__ == '__main__':
    print(read_by_firefox('https://www.mirf.ru/serial/harli-kvinn-3-j-sezon-kak-lego-betmen-no-bez-lego/'))
    print(read_by_firefox('https://300.ya.ru/3fOcYRBL', False))
