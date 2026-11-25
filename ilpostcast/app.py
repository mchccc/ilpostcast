"""
Serves il Post podcasts as RSS feeds, one per entry in scrape_new.PODCASTS,
from the SQLite database (DB_FILE) that scrape_new.py fills.

Run locally from this directory with:

    DB_FILE=../ilpostcast.db flask run

then subscribe to http://localhost:5000/<podcast>.xml, e.g. /morning.xml.
In Docker it runs under gunicorn (see Dockerfile.server).
"""
from flask import Flask, Response, abort
from rss import get_rss
from scrape_new import PODCASTS

# Feed names that differ from the podcast's key; kept so existing subscriptions work.
FEED_ALIASES = {"altre_indagini": "altreindagini"}

app = Flask(__name__)


@app.route("/<name>.xml")
def get_feed(name):
    key = FEED_ALIASES.get(name, name)
    if key not in PODCASTS:
        abort(404)
    if "name" not in PODCASTS[key]:
        abort(503, f"{key} wasn't in il Post's podcast list when the server started")
    return Response(get_rss(key, feed_name=name), mimetype="application/rss+xml")


if __name__ == "__main__":
    app.run(debug=True)
