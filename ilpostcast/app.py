"""
Simple app that generates a podcasst XML feed for Radicalized

To be fair this could be easily adapted to any audiobook / set of NP3s - you'd
just need to change the image, the path to the music and all the descriptions.

Requires:

- feedgen
- flask

Run using:

FLASK_APP=podcast_app FLASK_ENV=production flask run --host 0.0.0.0 --port 80

Then connect your podcast app to your computer's IP/index.xml and you're good
to go (i.e. http://<ipaddr>/index.xml).
"""
import pathlib
from rss import get_rss
from flask import Flask, Response


# Create the flask server
app = Flask(__name__)


@app.route('/morning.xml')
def get_morning_feed():
    return Response(get_rss("morning"), mimetype='application/rss+xml')


@app.route('/tienimi_bordone.xml')
def get_tienimi_bordone_feed():
    return Response(get_rss("tienimi_bordone"), mimetype='application/rss+xml')


@app.route('/tienimi_morning.xml')
def get_tienimi_morning_feed():
    return Response(get_rss("tienimi_morning"), mimetype='application/rss+xml')


@app.route('/tienimi_parigi.xml')
def get_tienimi_parigi_feed():
    return Response(get_rss("tienimi_parigi"), mimetype='application/rss+xml')


@app.route('/indagini.xml')
def get_indagini_feed():
    return Response(get_rss("indagini"), mimetype='application/rss+xml')


@app.route('/altre_indagini.xml')
def get_altre_indagini_feed():
    return Response(get_rss("altreindagini"), mimetype='application/rss+xml')


@app.route('/ascolta.xml')
def get_ascolta_feed():
    return Response(get_rss("ascolta"), mimetype='application/rss+xml')


@app.route('/sanremo.xml')
def get_sanremo_feed():
    return Response(get_rss("sanremo"), mimetype='application/rss+xml')


@app.route('/eurovision.xml')
def get_eurovision_feed():
    return Response(get_rss("eurovision"), mimetype='application/rss+xml')


if __name__ == "__main__":
    app.run(debug=True)
