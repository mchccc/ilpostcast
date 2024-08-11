import re
import time
import requests
import html
import arrow
import asyncio
import logging
from icecream import ic
from multiprocessing import Pool
from fake_useragent import UserAgent
from sqlite_interface import create_table, insert_data, get_all_ids, get_all_images, insert_image_data, create_images_table

# logging.basicConfig(filename='example.log', encoding='utf-8', level=logging.DEBUG)

DOMAIN = "https://ilpost.it"
BASE_URL = "https://api-prod.ilpost.it/podcast/v1/podcast"
PODCASTS = {
    "morning": {
        "table_name": "morning",
        "slug": "morning",
    },
    "tienimi_bordone": {
        "table_name": "tienimi_bordone",
        "slug": "tienimi-bordone",
    },
    "tienimi_morning": {
        "table_name": "tienimi_morning",
        "slug": "tienimi_morning",
    },
    "tienimi_parigi": {
        "table_name": "tienimi_parigi",
        "slug": "tienimi-parigi",
    },
    "indagini": {
        "table_name": "indagini",
        "slug": "indagini",
    },
    "altreindagini": {
        "table_name": "altreindagini",
        "slug": "altre-indagini",
    },
    "sanremo": {
        "table_name": "sanremo",
        "slug": "il-podcast-del-post-su-sanremo",
    },
    "eurovision": {
        "table_name": "eurovision",
        "slug": "podcast-eurovision",
    },
    "ascolta": {
        "table_name": "ascolta",
        "slug": "ascolta",
    },
}


IMAGES = {}
PRELOAD = False


def get_all(url, page=1, max_pages=1):
    data = []
    hits=100
    iter = 1
    last_page = False
    while not last_page and (max_pages is None or iter <= max_pages):
        response = requests.get(f"{url}?pg={page}&hits={hits}")
        if 200 <= response.status_code < 300:
            response = response.json()
            data += response["data"]
            if response["head"]["data"]["pg"] * response["head"]["data"]["hits"] >= response["head"]["data"]["total"]:
                last_page = True
            ic(url, page, hits, last_page)
            page += 1
            iter += 1
        else:
            print(response)
    return data, last_page


def preload_podcasts():
    global PODCASTS
    podcasts_data, _ = get_all(BASE_URL, max_pages=None)
    for key, podcast in PODCASTS.items():
        for podcast_data in podcasts_data:
            if podcast_data["slug"] == podcast["slug"]:
                podcast["name"] = podcast_data["title"]
                podcast["author"] = podcast_data["author"]
                podcast["description"] = podcast_data["description"]
                podcast["url"] = f"{BASE_URL}/{podcast_data['slug']}"
                podcast["image"] = podcast_data["image_web"]
                PODCASTS[key] = podcast


def get_image_id(image_url):
    global IMAGES
    if image_url not in IMAGES:
        image_id = len(IMAGES) + 1
        insert_image_data(image_id, image_url)
        IMAGES[image_url] = image_id
    else:
        image_id = IMAGES[image_url]
    return image_id

def get_new_episodes_list(url, existing_ids):
    episodes = {}
    page = 1
    while True:
        episodes_data, last_page = get_all(url, page=page)
        episodes_local = {}
        for e in episodes_data:
            episode_id = e["id"]
            if episode_id not in existing_ids:
                head = requests.head(e["episode_raw_url"]).headers
                episodes_local[episode_id] = {
                    "id": episode_id,
                    "url": e["episode_raw_url"],
                    "desc": e["content_html"],
                    "image_id": get_image_id(e["image"]),
                    "title": html.unescape(e["title"]),
                    "date": e["date"],
                    "content_type": head["Content-Type"],
                    "content_length": head["Content-Length"],
                }
        episodes.update(episodes_local)
        if ic(len(episodes_local)) < ic(len(episodes_data)) or last_page:
            break
        page += 1
    return episodes


def get_links_new_episodes(podcast):
    create_table(name=podcast["table_name"], drop=False)
    existing_ids = set(get_all_ids(table=podcast["table_name"]))
    links = get_new_episodes_list(podcast["url"], existing_ids)
    return links, podcast["table_name"]


def main():
    global IMAGES
    preload_podcasts()
    create_images_table()
    IMAGES = get_all_images()

    with Pool(4) as p:
        new_episodes = p.map(
            get_links_new_episodes,
            [podcast for podcast in PODCASTS.values()],
            chunksize=4
        )

    report = {}
    for links, table_name in new_episodes:
        ic(len(links), table_name)
        dates = []
        for episode_id, data in links.items():
            insert_data([data], table=table_name)
            dates.append(arrow.get(data["date"]).format(arrow.FORMAT_RSS))
        if dates:
            report[table_name] = dates
    ic(report)

if __name__ == "__main__":
    main()
