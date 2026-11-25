import re
import xml.etree.ElementTree as ET
import arrow
from sqlite_interface import init_db, get_all_items
from scrape_new import PODCASTS, preload_podcasts

ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM = "http://www.w3.org/2005/Atom"
ET.register_namespace("itunes", ITUNES)
ET.register_namespace("atom", ATOM)

# Control characters that are illegal in XML 1.0 even when escaped.
INVALID_XML_CHARS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")

init_db()  # creates the schema (and migrates old data) if the scraper hasn't yet
preload_podcasts()  # must run to get all the up-to-date informations for podcasts


def add_text(parent, tag, text):
    element = ET.SubElement(parent, tag)
    if text is not None:
        element.text = INVALID_XML_CHARS.sub("", str(text))
    return element


def get_rss(key):
    """Build a podcast's RSS feed as UTF-8 bytes.

    ElementTree escapes all text and attributes, so titles and the HTML
    descriptions can't break the XML.
    """
    podcast = PODCASTS[key]
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, f"{{{ATOM}}}link", href=f"https://podcast.mccc.it/{key}.xml", rel="self", type="application/rss+xml")
    add_text(channel, "title", podcast["name"])
    add_text(channel, "description", podcast["description"])
    add_text(channel, "link", podcast["link"])
    add_text(channel, "language", "it")
    add_text(channel, "copyright", "© il Post")
    ET.SubElement(channel, f"{{{ITUNES}}}image", href=podcast["image"])
    ET.SubElement(channel, f"{{{ITUNES}}}category", text="News")
    add_text(channel, f"{{{ITUNES}}}author", podcast["author"])
    add_text(channel, f"{{{ITUNES}}}explicit", "false")

    for episode in get_all_items(key):
        item = ET.SubElement(channel, "item")
        add_text(item, "title", episode["title"])
        if episode["link"]:
            add_text(item, "link", episode["link"])
        add_text(item, "description", episode["description"])
        # The enclosure URL, not the episode id: apps have been identifying these
        # episodes by enclosure URL while the feed had no guid, so this keeps them
        # from showing every episode again as new.
        add_text(item, "guid", episode["url"]).set("isPermaLink", "false")
        ET.SubElement(
            item, "enclosure",
            length=str(episode["content_length"] or 0),
            type=episode["content_type"] or "audio/mpeg",
            url=episode["url"],
        )
        add_text(item, "pubDate", arrow.get(episode["date"]).format(arrow.FORMAT_RSS))
        if episode["duration_ms"]:
            add_text(item, f"{{{ITUNES}}}duration", round(episode["duration_ms"] / 1000))
        if episode["image_url"]:
            ET.SubElement(item, f"{{{ITUNES}}}image", href=episode["image_url"])

    ET.indent(rss)
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    print(get_rss("morning").decode())
