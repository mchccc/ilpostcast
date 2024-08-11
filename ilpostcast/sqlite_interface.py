import os
import sqlite3
from icecream import ic


DB_FILE = os.environ.get("DB_FILE")


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
