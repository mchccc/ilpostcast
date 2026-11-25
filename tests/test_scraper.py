import pytest
import requests

import scrape_new as sn
import sqlite_interface as si
from helpers import FakeResponse, episode, fake_api


# ------------------------------------------------------------------ HTTP retries

def test_non_retryable_status_fails_immediately(http):
    http.handler = lambda method, url, params: FakeResponse(404)

    with pytest.raises(requests.HTTPError):
        sn.get_all("https://api/x")

    assert len(http.calls) == 1 and http.sleeps == []


def test_transient_status_is_retried_with_backoff_then_fails(http):
    http.handler = lambda method, url, params: FakeResponse(503)

    with pytest.raises(requests.HTTPError):
        sn.get_all("https://api/x", max_pages=None)

    assert len(http.calls) == sn.MAX_ATTEMPTS
    assert http.sleeps == [2, 4, 8]


def test_recovers_from_transient_failures(http):
    answers = iter([
        requests.ConnectionError("boom"),
        FakeResponse(429),
        FakeResponse(json_data={"data": [{"id": 1}], "head": {"data": {"pg": 1, "hits": 100, "total": 1}}}),
    ])

    def handler(method, url, params):
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    http.handler = handler

    assert sn.get_all("https://api/x") == ([{"id": 1}], True)
    assert http.sleeps == [2, 4]


# ------------------------------------------------------------------ fetching episodes

def test_new_episode_fields(http):
    http.handler = fake_api(total=1)

    assert sn.get_new_episodes_list("https://api/podcast/x", existing_ids=set()) == [{
        "id": 1,
        "url": "https://cdn/1.mp3",
        "description": "<p>1</p>",
        "image_url": "https://img/x.jpg",
        "title": "Ep & 1",
        "date": "2026-01-01T00:00:01+01:00",
        "content_type": "audio/mpeg",
        "content_length": "42",
        "link": "https://www.ilpost.it/episodes/1/",
        "duration_ms": 1499,
    }]


def test_stops_after_the_first_page_with_a_known_episode(http):
    http.handler = fake_api(total=250)

    episodes = sn.get_new_episodes_list("https://api/podcast/x", existing_ids=set(range(1, 151)))

    assert http.pages_requested() == [1, 2]
    assert sorted(e["id"] for e in episodes) == list(range(151, 251))


def test_first_run_walks_every_page(http):
    http.handler = fake_api(total=250)

    episodes = sn.get_new_episodes_list("https://api/podcast/x", existing_ids=set())

    assert len(episodes) == 250
    assert http.pages_requested() == [1, 2, 3]


def test_unreachable_audio_is_skipped_and_missing_headers_get_defaults(http):
    flaky = [FakeResponse(503), FakeResponse(headers={"Content-Type": "audio/mpeg", "Content-Length": "7"})]

    def head(url):
        if url == "https://cdn/200.mp3":
            raise requests.ConnectionError("dead")
        if url == "https://cdn/201.mp3":
            return flaky.pop(0)
        if url == "https://cdn/202.mp3":
            return FakeResponse(headers={})
        return FakeResponse(headers={"Content-Type": "audio/mpeg", "Content-Length": "42"})

    http.handler = fake_api(total=250, head=head)

    episodes = {e["id"]: e for e in sn.get_new_episodes_list("https://api/podcast/x", existing_ids=set(range(1, 151)))}

    assert 200 not in episodes and len(episodes) == 99, "unreachable audio is skipped, to be retried next run"
    assert episodes[201]["content_length"] == "7", "a transient HEAD failure is retried"
    assert episodes[202]["content_type"] == "audio/mpeg" and episodes[202]["content_length"] == 0


def test_one_failing_podcast_does_not_lose_the_others(http):
    si.init_db()
    podcasts = {
        "good": {"slug": "good", "api_url": "https://api/podcast/good"},
        "broken": {"slug": "broken", "api_url": "https://api/podcast/broken"},
        "gone": {"slug": "gone"},  # not in the API's podcast list
    }
    http.handler = fake_api(total=5, broken_slugs=("broken",))

    results = {key: (dates, error) for key, dates, error in map(sn.scrape_podcast, podcasts.items())}

    assert len(results["good"][0]) == 5 and results["good"][1] is None
    assert "HTTPError" in results["broken"][1]
    assert "not found in the API" in results["gone"][1]
    assert si.get_all_ids("good") == {1, 2, 3, 4, 5}

    http.handler = fake_api(total=7)
    _, dates, error = sn.scrape_podcast(("good", podcasts["good"]))

    assert error is None and len(dates) == 2, "the next run picks up only the new episodes"
    assert si.get_all_ids("good") == set(range(1, 8))


# ------------------------------------------------------------------ backfill

def test_backfill_fills_only_missing_details(http, podcasts, monkeypatch):
    si.init_db()
    si.insert_episodes("x", [episode(3), episode(2, link="kept"), episode(999)])  # 999 isn't in the API
    podcasts.clear()
    podcasts.update({"x": {"slug": "x", "api_url": "https://api/podcast/x"}, "gone": {"slug": "gone"}})
    monkeypatch.setattr(sn, "preload_podcasts", lambda: None)
    http.handler = fake_api(total=250)

    assert sn.backfill_details() == 0

    assert http.count("HEAD") == 0, "backfill never touches the audio files"
    rows = {r["id"]: r for r in si.get_all_items("x")}
    assert (rows[3]["link"], rows[3]["duration_ms"]) == ("https://www.ilpost.it/episodes/3/", 3499)
    assert (rows[2]["link"], rows[2]["duration_ms"]) == ("kept", 2499)
    assert (rows[999]["link"], rows[999]["duration_ms"]) == (None, None)
