import xml.etree.ElementTree as ET

import pytest

import app
import rss
import sqlite_interface as si
from helpers import episode

NS = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd", "atom": "http://www.w3.org/2005/Atom"}

# Sloppy but realistic HTML, including the missing space that broke the old Altre Indagini feed
# and the one sequence a CDATA section can't contain as is.
HOSTILE_HTML = '<p>Q&A</p><br>café &nbsp; &#8217; <p class="x"style="y">no space</p> ]]> <unclosed'

# The URLs people are subscribed to.
SUBSCRIBED = ["morning", "tienimi_bordone", "tienimi_morning", "tienimi_parigi", "indagini",
              "altre_indagini", "ascolta", "sanremo", "eurovision"]


@pytest.fixture
def feed(podcasts):
    """The morning feed, built from deliberately awkward data."""
    podcasts["morning"].update(
        name="Tom &amp; Jerry <live>",
        author="A &quot;quoted&quot; author",
        description="L&#8217;Europa & <b>bold</b> &nbsp;",
        link="https://www.ilpost.it/podcasts/morning/?a=1&b=2",
        image="https://img/c.jpg?x=1&y=2",
    )
    si.init_db()
    si.insert_episodes("morning", [
        episode(1, url="https://cdn/a.mp3?t=1&u=2", description=HOSTILE_HTML, title='Ciao & <arrivederci> \x0b"x"',
                date="2026-11-25T08:07:13+01:00", content_length=123, image_url=None,
                link="https://www.ilpost.it/episodes/a/?x=1&y=2", duration_ms=1478499),
        episode(2, url="https://cdn/b.mp3", description=None, title="Old", date="2023-11-20",
                content_type=None, content_length=None, image_url="https://img/e.jpg"),
    ])
    return rss.get_rss("morning")


def channel(body):
    return ET.fromstring(body).find("channel")  # raises if the XML isn't well-formed


def test_feed_is_valid_xml(feed):
    assert feed.startswith(b'<?xml version="1.0" encoding="UTF-8"?>')
    channel(feed)


def test_description_html_is_sent_verbatim(feed):
    # What a lenient client like Overcast reads: the bytes between the tags are the HTML itself.
    verbatim = HOSTILE_HTML.replace("]]>", "]]]]><![CDATA[>")
    assert f"<description><![CDATA[{verbatim}]]></description>".encode() in feed
    # What a strict XML parser reads: the same HTML string.
    first, old = channel(feed).findall("item")
    assert first.findtext("description") == HOSTILE_HTML
    assert old.findtext("description") == ""


def test_channel_fields(feed):
    ch = channel(feed)
    assert ch.findtext("title") == "Tom & Jerry <live>"
    assert ch.findtext("description") == "L’Europa & <b>bold</b> \xa0", "entities decoded, then escaped"
    assert ch.findtext("itunes:author", namespaces=NS) == 'A "quoted" author'
    assert ch.findtext("link") == "https://www.ilpost.it/podcasts/morning/?a=1&b=2"
    assert ch.find("itunes:image", NS).get("href") == "https://img/c.jpg?x=1&y=2"
    assert ch.find("itunes:category", NS).get("text") == "News"
    assert ch.find("atom:link", NS).get("href") == "https://podcast.mccc.it/morning.xml"


def test_items(feed):
    first, old = channel(feed).findall("item")

    assert first.findtext("title") == 'Ciao & <arrivederci> "x"', "control characters are dropped"
    assert first.findtext("link") == "https://www.ilpost.it/episodes/a/?x=1&y=2"
    assert first.findtext("guid") == "https://cdn/a.mp3?t=1&u=2", "guid is the enclosure URL"
    assert first.find("guid").get("isPermaLink") == "false"
    enclosure = first.find("enclosure")
    assert (enclosure.get("url"), enclosure.get("length"), enclosure.get("type")) == \
        ("https://cdn/a.mp3?t=1&u=2", "123", "audio/mpeg")
    assert first.findtext("pubDate") == "Wed, 25 Nov 2026 08:07:13 +0100"
    assert first.findtext("itunes:duration", namespaces=NS) == "1478"
    assert first.find("itunes:image", NS) is None

    assert old.findtext("title") == "Old", "newest first"
    assert old.find("link") is None and old.find("itunes:duration", NS) is None
    assert old.find("enclosure").get("length") == "0" and old.find("enclosure").get("type") == "audio/mpeg"
    assert old.find("itunes:image", NS).get("href") == "https://img/e.jpg"


# ------------------------------------------------------------------ the Flask app

@pytest.fixture
def client(podcasts, monkeypatch):
    def fake_preload():
        for key, podcast in podcasts.items():
            podcast.update(name=key, author="il Post", description="d", link="https://www.ilpost.it/", image="i")

    monkeypatch.setattr(app, "preload_podcasts", fake_preload)
    return app.create_app().test_client()


@pytest.mark.parametrize("name", SUBSCRIBED)
def test_existing_subscription_urls_still_work(client, name):
    response = client.get(f"/{name}.xml")

    assert response.status_code == 200
    assert response.mimetype == "application/rss+xml"
    assert channel(response.data).find("atom:link", NS).get("href") == f"https://podcast.mccc.it/{name}.xml"


def test_unknown_feed_is_404(client):
    assert client.get("/nope.xml").status_code == 404


def test_podcast_missing_from_the_api_is_503(client, podcasts):
    del podcasts["eurovision"]["name"]

    assert client.get("/eurovision.xml").status_code == 503
