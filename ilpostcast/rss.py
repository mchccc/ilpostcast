import requests
from datetime import datetime
from sqlite_interface import PODCASTS, get_all_items
from icecream import ic

def get_rss(table_name):
    podcast = PODCASTS[table_name]
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
xmlns:podcast="https://podcastindex.org/namespace/1.0"
xmlns:atom="http://www.w3.org/2005/Atom"
xmlns:content="http://purl.org/rss/1.0/modules/content/">
    <channel>
        <atom:link href="https://podcast.mccc.it/{table_name}.xml" rel="self" type="application/rss+xml" />
        <title>{podcast['name']}</title>
        <description>{podcast['description']}</description>
        <link>{podcast['url']}</link>
        <language>it</language>
        <copyright>&#169; il Post</copyright>
        <itunes:image href="{podcast['image']}" />
        <itunes:category text="News" />
        <itunes:author>{podcast['author']}</itunes:author>
        <itunes:explicit>false</itunes:explicit>"""
    date_format = "%a, %d %b %Y 08:00:00 GMT"  # %H:%M:%S %z"

    for id, url, desc, title, date, content_type, content_length, img_url in get_all_items(table_name):
        feed += f"""
        <item>
            <title>{title}</title>
            <description>{desc}</description>
            <enclosure
                length="{content_length}"
                type="{content_type}"
                url="{url}"
            />
            <pubDate>{datetime.strptime(date, "%Y-%m-%d").strftime(date_format)}</pubDate>
            <itunes:image href="{img_url}" />
        </item>"""
    feed += """
    </channel>
</rss>"""

    return feed


if __name__ == "__main__":
    ic(get_rss("morning"))
