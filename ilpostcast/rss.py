import re
import html
from xml.sax.saxutils import escape, quoteattr
import arrow
from sqlite_interface import init_db, get_all_items
from scrape_new import PODCASTS, preload_podcasts

# Control characters that are illegal in XML 1.0, even escaped or inside CDATA.
INVALID_XML_CHARS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean(value):
    return INVALID_XML_CHARS.sub("", "" if value is None else str(value))


def text(value):
    """Escape a plain-text value for use as element content."""
    return escape(clean(value))


def attr(value):
    """Escape and quote a value for use as an attribute (the quotes are included)."""
    return quoteattr(clean(value))


def cdata(value):
    """Wrap HTML in a CDATA section.

    The bytes between the tags stay exactly the HTML, which is what podcast
    apps render as show notes, and the feed is still valid XML whatever the
    HTML looks like. A literal "]]>" is split across two sections.
    """
    return "<![CDATA[" + clean(value).replace("]]>", "]]]]><![CDATA[>") + "]]>"


def render_item(episode):
    lines = [f"<title>{text(episode['title'])}</title>"]
    if episode["link"]:
        lines.append(f"<link>{text(episode['link'])}</link>")
    lines += [
        f"<description>{cdata(episode['description'])}</description>",
        # The enclosure URL, not the episode id: apps have been identifying these
        # episodes by enclosure URL while the feed had no guid, so this keeps them
        # from showing every episode again as new.
        f'<guid isPermaLink="false">{text(episode["url"])}</guid>',
        f'<enclosure length={attr(episode["content_length"] or 0)}'
        f' type={attr(episode["content_type"] or "audio/mpeg")} url={attr(episode["url"])} />',
        f"<pubDate>{arrow.get(episode['date']).format(arrow.FORMAT_RSS)}</pubDate>",
    ]
    if episode["duration_ms"]:
        lines.append(f"<itunes:duration>{round(episode['duration_ms'] / 1000)}</itunes:duration>")
    if episode["image_url"]:
        lines.append(f"<itunes:image href={attr(episode['image_url'])} />")
    body = "\n            ".join(lines)
    return f"""
        <item>
            {body}
        </item>"""


def get_rss(key, feed_name=None):
    """Build a podcast's RSS feed as UTF-8 bytes.

    Needs preload_podcasts() to have run (app.create_app() does it).
    `feed_name` is the name in the feed's URL (defaults to `key`), used for the
    self link. Every value goes through text(), attr() or cdata(), so nothing
    coming from the API can break the XML. The API's podcast name, author and
    description are plain text with HTML entities (e.g. "&#8217;"), so they're
    decoded before being escaped.
    """
    podcast = PODCASTS[key]
    self_url = f"https://podcast.mccc.it/{feed_name or key}.xml"
    items = "".join(render_item(episode) for episode in get_all_items(key))
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
xmlns:atom="http://www.w3.org/2005/Atom">
    <channel>
        <atom:link href={attr(self_url)} rel="self" type="application/rss+xml" />
        <title>{text(html.unescape(podcast['name']))}</title>
        <description>{text(html.unescape(podcast['description']))}</description>
        <link>{text(podcast['link'])}</link>
        <language>it</language>
        <copyright>© il Post</copyright>
        <itunes:image href={attr(podcast['image'])} />
        <itunes:category text="News" />
        <itunes:author>{text(html.unescape(podcast['author']))}</itunes:author>
        <itunes:explicit>false</itunes:explicit>{items}
    </channel>
</rss>
"""
    return feed.encode("utf-8")


if __name__ == "__main__":
    init_db()
    preload_podcasts()
    print(get_rss("morning").decode())
