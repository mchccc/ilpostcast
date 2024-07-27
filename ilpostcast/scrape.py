import re
import time
import requests
import arrow
import asyncio
import logging
from icecream import ic
from bs4 import BeautifulSoup as bs
from multiprocessing import Pool
from selenium.webdriver import Firefox, FirefoxOptions as Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.firefox.service import Service
from fake_useragent import UserAgent
from sqlite_interface import DOMAIN, PODCASTS, create_table, insert_data, get_all_ids, get_all_images, insert_image_data, create_images_table

# logging.basicConfig(filename='example.log', encoding='utf-8', level=logging.DEBUG)

ua = UserAgent()
user_agent = ic(ua.random)

email = "mciccozz@gmail.com"
password = ""
url_login = "https://abbonati.ilpost.it/mio-account/"
url_404 = f"{DOMAIN}/404"

IMAGES = {}
PRELOAD = False

def get_logged_in_cookies():
    with requests.session() as session:
        r = session.get(url_login)
        soup = bs(r.content, "lxml")
        nonce = soup.find(id="woocommerce-login-nonce")["value"]
        payload ={
            "username": email,
            "password": password,
            "woocommerce-login-nonce": nonce,
            "_wp_http_referer": "/mio-account/",
            "login": "Log+in"
        }
        r = session.post(url_login, data=payload)
        soup = bs(r.content, "lxml")
        ic(soup.find("body", class_="logged-in").name == "body")
        return session.cookies

class LoggedInBrowser:
    def __init__(self, cookies):
        self.cookies = cookies

    @staticmethod
    def get_browser():
        options = Options()
        options.add_argument('--headless')
        options.add_argument(f'--user-agent="{user_agent}"')
        browser = Firefox(
            service=Service(
                executable_path="/bin/geckodriver"
            ),
            options=options
        )
        return browser

    @staticmethod
    def get_browser_with_cookies(cookies=None):
        browser = LoggedInBrowser.get_browser()
        browser.get(url_404)
        for cookie in cookies:
            browser.add_cookie({"name": cookie.name, "value": cookie.value})
        return browser

    def __enter__(self):
        self._browser = LoggedInBrowser.get_browser_with_cookies(cookies=self.cookies)
        return self._browser

    def __exit__(self, exc_type, exc_value, exc_tb):
        self._browser.close()


def get_date_from_desc(desc):
    date_str = desc.split(" - ")[0]
    date_obj = arrow.get(date_str, "DD MMM YYYY", locale="it")
    return date_obj.format("YYYY-MM-DD")


def extract_single_link(content):
    global IMAGES
    soup = bs(content, "lxml")
    link = soup.select_one(".ilpostPlayer[data-file]")
    url = link["data-file"]
    head = requests.head(url).headers
    desc = soup.select_one(".ilpostPlayer > p.date").text
    pic = soup.select_one(".ilpostContent > img.imageEvidence")["src"].split("?")[0]
    if pic not in IMAGES:
        image_id = len(IMAGES) + 1
        insert_image_data(image_id, pic)
        IMAGES[pic] = image_id
    else:
        image_id = IMAGES[pic]
    data = {
        "id": link["data-id"],
        "url": url,
        "desc": desc,
        "image_id": image_id,
        "title": soup.select_one(".ilpostPlayer > h2.title").text,
        "date": get_date_from_desc(desc),
        "content_type": head["Content-Type"],
        "content_length": head["Content-Length"],
    }
    return data


def extract_links(content, existing_ids={}):
    soup = bs(content, "lxml")
    links = soup.select(".play[data-file]")
    data = []
    for l in links:
        if l["data-id"] not in existing_ids:
            url = l["data-file"]
            head = requests.head(url).headers
            data.append(
                {
                    "id": l["data-id"],
                    "url": url,
                    "desc": l["data-desc"],
                    "title": l["data-title"],
                    "date": get_date_from_desc(l["data-desc"]),
                    "content_type": head["Content-Type"],
                    "content_length": head["Content-Length"],
                }
            )
    return data


def get_data(url, existing_ids={}):
    content = None
    attempts = 0
    while content is None:
        attempts += 1
        with LoggedInBrowser() as browser:
            browser.get(url)
            if EC.text_to_be_present_in_element_attribute(
                    (By.XPATH, "//a[@data-file and @aria-label='Play']"),
                    attribute_="data-file",
                    text_="https"
                )(browser):
                content = browser.page_source
                data = extract_links(content, existing_ids)
                try:
                    next_url = browser.find_element(
                        By.CLASS_NAME, "next"
                    ).get_attribute("href")
                except NoSuchElementException:
                    next_url = None
                ic(data, attempts, next_url)
    return data, next_url


def get_data_single_page(url, cookies):
    data = None
    attempts = 0
    while data is None:
        attempts += 1
        with LoggedInBrowser(cookies) as browser:
            browser.get(url)
            audio_locator = (By.XPATH, "//div[@class='ilpostPlayer' and @data-file]")
            audio_present = EC.text_to_be_present_in_element_attribute(
                    audio_locator,
                    attribute_="data-file",
                    text_="https"
                )
            try:
                WebDriverWait(browser, 5).until(audio_present)
                data = extract_single_link(browser.page_source)
                ic(data, attempts)
            except TimeoutException:
                pass
    return data


def get_page_source(driver, url):
    browser.get(url)
    content = browser.page_source
    return content


def get_episodes_list(url, existing_ids, cookies):
    links = {}
    with LoggedInBrowser(cookies) as browser:
        while url is not None:
            page_links = {}
            ic(url)
            browser.get(url)
            content = browser.page_source
            soup = bs(content, "lxml")
            episodes = soup.find_all(id=re.compile("episode_"))
            for e in episodes:
                episode_id = e["id"].split("_")[1]
                if episode_id not in existing_ids:
                    page_links[episode_id] = e.h2.a["href"]
            ic(url, page_links)
            url = browser.find_element(
                By.CLASS_NAME, "next"
            ).get_attribute("href") if PRELOAD or len(episodes) == len(page_links) else None
            links.update(page_links)
    return links


def populate_tables():
    for table_name, podcast in PODCASTS.items():
        create_table(name=table_name, drop=False)
        existing_ids = set(get_all_ids(table=table_name))
        next_url = podcast["url"]
        while next_url is not None:
            data, next_url = get_data(next_url, existing_ids)
            if not data:
                if not PRELOAD:
                    break
            else:
                insert_data(data, table=table_name)


def get_links_new_episodes(params_tuple):
    cookies, podcast = params_tuple
    create_table(name=podcast["table_name"], drop=False)
    existing_ids = set(get_all_ids(table=podcast["table_name"]))
    links = get_episodes_list(podcast["url"], existing_ids, cookies)
    return links, podcast["table_name"]


def main():
    global IMAGES
    create_images_table()
    IMAGES = get_all_images()
    cookies = get_logged_in_cookies()

    with Pool(4) as p:
        new_episodes = p.map(
            get_links_new_episodes,
            [(cookies, podcast) for podcast in PODCASTS.values()],
            chunksize=2
        )

    report = {}
    for links, table_name in new_episodes:
        ic(links, table_name)
        dates = []
        for episode_id, link in links.items():
            data = get_data_single_page(link, cookies)
            insert_data([data], table=table_name)
            dates.append(data["date"])
        if dates:
            report[table_name] = dates
    ic(report)

if __name__ == "__main__":
    main()
