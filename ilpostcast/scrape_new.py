import sys
import html
import time
import traceback
import arrow
import requests
from icecream import ic
from multiprocessing import Pool
from sqlite_interface import init_db, get_all_ids, insert_episodes

BASE_URL = "https://api-prod.ilpost.it/podcast/v1/podcast"
PODCASTS = {
    "morning": {
        "slug": "morning",
    },
    "tienimi_bordone": {
        "slug": "tienimi-bordone",
    },
    "tienimi_morning": {
        "slug": "tienimi_morning",
    },
    "tienimi_parigi": {
        "slug": "tienimi-parigi",
    },
    "indagini": {
        "slug": "indagini",
    },
    "altreindagini": {
        "slug": "altre-indagini",
    },
    "sanremo": {
        "slug": "il-podcast-del-post-su-sanremo",
    },
    "eurovision": {
        "slug": "podcast-eurovision",
    },
    "ascolta": {
        "slug": "ascolta",
    },
}

TIMEOUT = (10, 60)  # seconds: (connect, read)
MAX_ATTEMPTS = 4  # waits 2s, 4s, 8s between attempts
RETRY_STATUSES = {429, 500, 502, 503, 504}


def request(method, url, **kwargs):
    """Send an HTTP request with a timeout, retrying transient failures with backoff.

    Raises immediately on other error statuses, and with the last error once
    the attempts run out.
    """
    for attempt in range(MAX_ATTEMPTS):
        if attempt:
            time.sleep(2 ** attempt)
        try:
            response = requests.request(method, url, timeout=TIMEOUT, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as error:
            last_error = error
            continue
        if response.status_code not in RETRY_STATUSES:
            response.raise_for_status()
            return response
        last_error = requests.HTTPError(f"{response.status_code} for {url}", response=response)
    raise last_error


def get_all(url, page=1, max_pages=1):
    data = []
    hits = 100
    fetched = 0
    last_page = False
    while not last_page and (max_pages is None or fetched < max_pages):
        response = request("GET", url, params={"pg": page, "hits": hits}).json()
        data += response["data"]
        head = response["head"]["data"]
        last_page = not response["data"] or head["pg"] * head["hits"] >= head["total"]
        ic(url, page, hits, last_page)
        page += 1
        fetched += 1
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


def get_audio_headers(url):
    """Return (content_type, content_length) for an episode's audio, or None if it's unreachable."""
    try:
        headers = request("HEAD", url).headers
    except requests.RequestException as error:
        ic("audio unreachable, will retry next run", url, error)
        return None
    return headers.get("Content-Type", "audio/mpeg"), headers.get("Content-Length", 0)


def get_new_episodes_list(url, existing_ids):
    """Fetch the episodes we don't have yet.

    Pages come newest first, so stop after the first page that contains an
    episode we already have.
    """
    episodes = []
    page = 1
    while True:
        episodes_data, last_page = get_all(url, page=page)
        new_episodes = [e for e in episodes_data if e["id"] not in existing_ids]
        for e in new_episodes:
            audio = get_audio_headers(e["episode_raw_url"])
            if audio is None:
                continue
            content_type, content_length = audio
            episodes.append({
                "id": e["id"],
                "url": e["episode_raw_url"],
                "description": e["content_html"],
                "image_url": e["image"],
                "title": html.unescape(e["title"]),
                "date": e["date"],
                "content_type": content_type,
                "content_length": content_length,
            })
        ic(len(new_episodes), len(episodes_data))
        if len(new_episodes) < len(episodes_data) or last_page:
            break
        page += 1
    return episodes


def scrape_podcast(item):
    """Fetch and store one podcast's new episodes.

    Runs in a worker process and never raises, so one broken podcast can't
    stop the others: returns (key, dates of new episodes, error or None).
    """
    key, podcast = item
    try:
        if "url" not in podcast:
            raise LookupError(f"slug {podcast['slug']!r} not found in the API's podcast list")
        episodes = get_new_episodes_list(podcast["url"], get_all_ids(key))
        insert_episodes(key, episodes)
        return key, [arrow.get(e["date"]).format(arrow.FORMAT_RSS) for e in episodes], None
    except Exception:
        return key, [], traceback.format_exc()


def main():
    preload_podcasts()
    init_db()

    with Pool(4) as p:
        results = p.map(scrape_podcast, PODCASTS.items())

    report = {key: dates for key, dates, error in results if dates}
    ic(report)
    errors = {key: error for key, _, error in results if error}
    for key, error in errors.items():
        print(f"{key} failed:\n{error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
