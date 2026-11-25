"""Test helpers: a fake HTTP layer, a fake il Post API, and small database utilities."""
import sqlite3

import requests


class FakeResponse:
    def __init__(self, status=200, json_data=None, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self._json = json_data

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code), response=self)


class FakeHTTP:
    """Replaces requests.request. Set `handler(method, url, params)` to return a FakeResponse or raise."""

    def __init__(self):
        self.handler = None
        self.calls = []
        self.sleeps = []

    def request(self, method, url, timeout=None, **kwargs):
        assert timeout is not None, "every request must have a timeout"
        self.calls.append((method, url, kwargs.get("params")))
        return self.handler(method, url, kwargs.get("params"))

    def pages_requested(self):
        return [params["pg"] for method, _, params in self.calls if method == "GET"]

    def count(self, method):
        return sum(m == method for m, _, _ in self.calls)


def api_episode(episode_id):
    """An episode as the il Post API returns it."""
    return {
        "id": episode_id,
        "episode_raw_url": f"https://cdn/{episode_id}.mp3",
        "content_html": f"<p>{episode_id}</p>",
        "image": "https://img/x.jpg",
        "title": f"Ep &amp; {episode_id}",
        "date": f"2026-01-01T00:00:{episode_id % 60:02}+01:00",
        "share_url": f"https://www.ilpost.it/episodes/{episode_id}/",
        "milliseconds": episode_id * 1000 + 499,
    }


def fake_api(total=250, head=None, broken_slugs=()):
    """A FakeHTTP handler serving episodes `total`..1, newest first, in pages.

    `head(url)` overrides the default HEAD response; listing a slug in
    `broken_slugs` returns 404.
    """
    ids = list(range(total, 0, -1))

    def handler(method, url, params):
        if method == "HEAD":
            if head:
                return head(url)
            return FakeResponse(headers={"Content-Type": "audio/mpeg", "Content-Length": "42"})
        if any(url.endswith(slug) for slug in broken_slugs):
            return FakeResponse(404)
        page, hits = params["pg"], params["hits"]
        return FakeResponse(json_data={
            "data": [api_episode(i) for i in ids[(page - 1) * hits: page * hits]],
            "head": {"data": {"pg": page, "hits": hits, "total": total}},
        })

    return handler


def episode(episode_id, **fields):
    """An episode as insert_episodes() takes it, with a default for every column."""
    return {
        "id": episode_id, "url": f"https://cdn/{episode_id}.mp3", "title": f"t{episode_id}",
        "description": "d", "date": "2026-01-01", "content_type": "audio/mpeg", "content_length": 1,
        "image_url": "i", "link": None, "duration_ms": None,
        **fields,
    }


def query(path, sql, *params):
    """Run a query against a database file and return the rows as dicts."""
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in con.execute(sql, params)]
    finally:
        con.close()
