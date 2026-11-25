import copy
import types

import pytest
import requests

import scrape_new
import sqlite_interface
from helpers import FakeHTTP


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    """Every test gets its own empty database file (no schema yet); this is its path."""
    path = tmp_path / "ilpostcast.db"
    monkeypatch.setattr(sqlite_interface, "DB_FILE", str(path))
    return path


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("tests must not make real HTTP requests; use the `http` fixture")

    monkeypatch.setattr(requests, "request", refuse)
    monkeypatch.setattr(requests.Session, "request", refuse)


@pytest.fixture(autouse=True)
def podcasts():
    """scrape_new.PODCASTS (shared with rss and app), restored after each test."""
    saved = copy.deepcopy(scrape_new.PODCASTS)
    yield scrape_new.PODCASTS
    scrape_new.PODCASTS.clear()
    scrape_new.PODCASTS.update(saved)


@pytest.fixture
def http(monkeypatch):
    """A fake HTTP layer for scrape_new: set `http.handler`. Backoff sleeps are recorded, not slept."""
    fake = FakeHTTP()
    monkeypatch.setattr(requests, "request", fake.request)
    monkeypatch.setattr(scrape_new, "time", types.SimpleNamespace(sleep=fake.sleeps.append))
    return fake
