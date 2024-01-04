from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from loguru import logger as _log

READER_URL = 'about:reader?url={}'


def read_by_firefox(url):
    _log.debug(f'read_by_firefox: {url}')

    display = Display(visible=False, size=(800, 600))
    display.start()

    browser = webdriver.Firefox()

    url = READER_URL.format(url)
    _log.debug(f'Opening: {url}')

    browser.get(url)

    try:
        WebDriverWait(browser, 30).until(
            ec.presence_of_element_located((By.ID, 'post-content-body'))
        )
        return {
            'title': browser.find_element(
                By.CLASS, 'reader-title').get_attribute('innerHTML'),
            'content': browser.find_element(
                By.ID, 'article').get_attribute('innerHTML')
        }
    finally:
        browser.quit()
        display.stop()
