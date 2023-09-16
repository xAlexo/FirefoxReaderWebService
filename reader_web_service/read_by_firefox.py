from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait

READER_URL = 'about:reader?url={}'


def read_by_firefox(url):
    display = Display(visible=False, size=(800, 600))
    display.start()

    browser = webdriver.Firefox()

    url = READER_URL.format(url)

    browser.get(url)

    try:
        WebDriverWait(browser, 30).until(
            ec.presence_of_element_located((By.ID, 'post-content-body'))
        )
        return browser.find_element(
            By.ID, 'post-content-body').get_attribute('innerHTML')
    finally:
        browser.quit()
        display.stop()
