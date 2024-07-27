import os
import sqlite3
from icecream import ic


DB_FILE = os.environ.get("DB_FILE")
DOMAIN = "https://ilpost.it"
PODCASTS = {
    "morning": {
        "name": "Morning",
        "table_name": "morning",
        "author": "Francesco Costa",
        "description": "Comincia la giornata con la rassegna stampa di Francesco Costa, ogni mattina, prima delle 8. Altrimenti non sarebbe Morning.",
        "url": f"{DOMAIN}/episodes/podcasts/morning/",
        "image": f"{DOMAIN}/wp-content/uploads/2021/05/evening-1.png"
    },
    "tienimi_bordone": {
        "name": "Tienimi Bordone",
        "table_name": "tienimi_bordone",
        "author": "Matteo Bordone",
        "description": "Il podcast quotidiano di Matteo Bordone. Tutto quello che non sapevi di voler sapere.",
        "url": f"{DOMAIN}/episodes/podcasts/tienimi-bordone/",
        "image": f"{DOMAIN}/wp-content/uploads/2021/04/app-tb.jpg"
    },
    "tienimi_morning": {
        "name": "Tienimi Morning",
        "table_name": "tienimi_morning",
        "author": "Matteo Bordone & Francesco Costa",
        "description": "Sabato 24 settembre 2022 durante una delle giornate di incontri dal vivo organizzate dal Post a Faenza, Matteo Bordone e Francesco Costa, titolari dei podcast del Post Tienimi Bordone e Morning, avevano deciso di fare un incontro insieme. Quel primo Tienimi Morning, così lo avevano chiamato, lo avevamo registrato e pubblicato: e visti gli apprezzamenti ricevuti appena c'è stata occasione lo abbiamo rifatto.",
        "url": f"{DOMAIN}/episodes/podcasts/tienimi_morning/",
        "image": f"{DOMAIN}/wp-content/uploads/2022/09/25/1664102867-tm.png"
    },
    "tienimi_parigi": {
        "name": "Tienimi Parigi",
        "table_name": "tienimi_parigi",
        "author": "Matteo Bordone",
        "description": "Il podcast di Matteo Bordone sulle Olimpiadi di Parigi: tutti i giorni, dal 26 luglio al 12 agosto.",
        "url": f"{DOMAIN}/episodes/podcasts/tienimi-parigi/",
        "image": f"{DOMAIN}/wp-content/uploads/2024/07/16/1721164092-Articolo1200x600-3.jpg"
    },
    "indagini": {
        "name": "Indagini",
        "table_name": "indagini",
        "author": "Stefano Nazzi",
        "description": "Cosa è successo dopo alcuni dei più noti casi di cronaca nera italiana. Una storia ogni mese, il primo del mese. Di Stefano Nazzi.",
        "url": f"{DOMAIN}/episodes/podcasts/indagini/",
        "image": f"{DOMAIN}/wp-content/uploads/2022/03/Image-from-iOS-1.jpg.webp"
    },
    "altreindagini": {
        "name": "Altre Indagini",
        "table_name": "altreindagini",
        "author": "Stefano Nazzi",
        "description": "Le puntate speciali di Indagini che raccontano le grandi vicende della storia italiana, di Stefano Nazzi.",
        "url": f"{DOMAIN}/episodes/podcasts/altre-indagini/",
        "image": f"{DOMAIN}/wp-content/uploads/2024/04/09/1712670309-Altre_Indagini_676x355.jpg"
    },
    "sanremo": {
        "name": "L'Indomabile Podcast del Post su Sanremo",
        "table_name": "sanremo",
        "author": "Matteo Bordone, Giulia Balducci, Luca Misculin, Stefano Vizio",
        "description": "Indomabile.",
        "url": f"{DOMAIN}/episodes/podcasts/il-podcast-del-post-su-sanremo/",
        "image": f"{DOMAIN}/wp-content/uploads/2024/02/01/1706806182-copertina676x355.jpg"
    },
    "eurovision": {
        "name": "L'Ineludibile Podcast del Post sull'Eurovision Song Contest",
        "table_name": "eurovision",
        "author": "Matteo Bordone, Giulia Balducci, Stefano Vizio, Luca Misculin",
        "description": "Ineludibile.",
        "url": f"{DOMAIN}/episodes/podcasts/podcast-eurovision/",
        "image": f"{DOMAIN}/wp-content/uploads/2024/04/30/1714468634-copertina676x355.jpg"
    },
    "ascolta": {
        "name": "Ascolta",
        "table_name": "ascolta",
        "author": "Redazione ilPost",
        "description": "Gli articoli del Post, letti e spiegati da chi li ha scritti",
        "url": f"{DOMAIN}/episodes/podcasts/ascolta/",
        "image": f"{DOMAIN}/wp-content/uploads/2024/05/31/1717170298-copertina676x355-autori.jpg"
    },
}

class DB:
    _conn = None

    @staticmethod
    def commit():
        if DB._conn is not None:
            DB._conn.commit()

    def __enter__(self):
        DB._conn = sqlite3.connect(DB_FILE)
        cur = DB._conn.cursor()
        return cur

    def __exit__(self, exc_type, exc_value, exc_tb):
        DB._conn.close()


def create_table(name, drop=False):
    with DB() as db:
        if drop:
            db.execute(f"DROP TABLE IF EXISTS {name};")
        db.execute(f"""
            CREATE TABLE IF NOT EXISTS {name}(id, url, desc, title, date, content_type, content_length, image_id INTEGER);
        """)
        ic(name, drop)


def create_images_table(drop=False):
    with DB() as db:
        if drop:
            db.execute(f"DROP TABLE IF EXISTS image;")
        db.execute(f"""
            CREATE TABLE IF NOT EXISTS image(id INTEGER, url);
        """)
        ic("image", drop)


def insert_data(data, table):
    data = [
        (d["id"], d["url"], d["desc"], d["title"], d["date"], d["content_type"], d["content_length"], d["image_id"])
        for d in data
    ]
    with DB() as db:
        db.executemany(f"INSERT INTO {table} VALUES(?, ?, ?, ?, ?, ?, ?, ?)", data)
        DB.commit()
        ic(len(data), table)


def insert_image_data(id, url):
    with DB() as db:
        db.execute(f"INSERT INTO image VALUES('{id}', '{url}')")
        DB.commit()
        ic(id, url)


def insert_image_id(table, id, image_id):
    with DB() as db:
        db.execute(f"UPDATE {table} SET image_id = '{image_id}' WHERE id = '{id}'")
        DB.commit()
        ic(table, image_id)


def get_all_ids(table):
    with DB() as db:
        res = db.execute(f"SELECT id FROM {table}")
        return [i for (i,) in res.fetchall()]


def get_all_images():
    with DB() as db:
        res = db.execute(f"SELECT id, url FROM image")
        return {u: i for (i, u) in res.fetchall()}


def get_all_items(table):
    with DB() as db:
        res = db.execute(f"SELECT {table}.id, {table}.url, desc, title, date, content_type, content_length, image.url FROM {table} INNER JOIN image ON {table}.image_id = image.id ORDER BY date DESC")
        return res.fetchall()
