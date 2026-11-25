import sqlite3
import threading

import sqlite_interface as si
from helpers import episode, query


def make_legacy_db(path):
    """A database in the old one-table-per-podcast layout, with the quirks real ones have."""
    con = sqlite3.connect(path)
    for table in ("morning", "altreindagini"):
        con.execute(f"CREATE TABLE {table}(id, url, desc, title, date, content_type, content_length, image_id INTEGER)")
    con.execute("CREATE TABLE image(id INTEGER, url)")
    # Image id 2 was handed out twice by two scraper workers; the first row is the original.
    con.executemany("INSERT INTO image VALUES(?, ?)", [("1", "img-morning"), ("2", "img-altre"), ("2", "img-collision")])
    con.executemany("INSERT INTO morning VALUES(?,?,?,?,?,?,?,?)", [
        # The same episode stored by the old HTML scraper (text id) and by the API scraper (int id).
        ("100", "u100-old", "20 nov 2026 - x", "HTML-era copy", "2026-11-20", "audio/mpeg", "123", 1),
        (100, "u100", "<p>a & b</p>", "API era", "2026-11-20T08:00:00+01:00", "audio/mpeg", "123", 1),
        ("99", "u99", "19 nov 2026 - y", "HTML era only", "2026-11-19", "audio/mpeg", "456", 1),
        # No image: the old feed's INNER JOIN hid this one.
        (98, "u98", "d", "no image", "2026-11-18T08:00:00+01:00", "audio/mpeg", "789", None),
    ])
    con.execute("INSERT INTO altreindagini VALUES(7, 'u7', 'd7', 'altre', '2026-11-01', 'audio/mpeg', '1', 2)")
    con.execute("CREATE TABLE unrelated(x, y)")
    con.commit()
    con.close()


def test_migration_copies_the_old_tables(db):
    make_legacy_db(db)
    si.init_db()

    rows = {(r["podcast"], r["id"]): r for r in query(db, "SELECT * FROM episodes")}
    assert set(rows) == {("morning", 100), ("morning", 99), ("morning", 98), ("altreindagini", 7)}
    assert rows["morning", 100]["title"] == "API era", "the API-era row wins over the text-id duplicate"
    assert rows["morning", 100]["description"] == "<p>a & b</p>"
    assert rows["morning", 100]["image_url"] == "img-morning"
    assert rows["morning", 99]["id"] == 99, "text ids become integers"
    assert rows["morning", 99]["content_length"] == 456
    assert rows["morning", 98]["image_url"] is None
    assert rows["altreindagini", 7]["image_url"] == "img-altre", "the first image row wins on a collision"
    assert query(db, "PRAGMA user_version") == [{"user_version": si.SCHEMA_VERSION}]
    assert query(db, "SELECT count(*) AS n FROM morning") == [{"n": 4}], "old tables are left untouched"


def test_migration_runs_only_once(db):
    make_legacy_db(db)
    si.init_db()
    con = sqlite3.connect(db)
    con.execute("INSERT INTO morning VALUES(1, 'late', 'd', 't', '2020-01-01', 'audio/mpeg', 1, 1)")
    con.commit()
    con.close()

    si.init_db()

    assert query(db, "SELECT count(*) AS n FROM episodes") == [{"n": 4}]


def test_fresh_database(db):
    si.init_db()
    si.init_db()

    assert si.get_all_ids("morning") == set()
    assert query(db, "PRAGMA user_version") == [{"user_version": si.SCHEMA_VERSION}]


def test_version_1_database_gains_the_new_columns(db):
    con = sqlite3.connect(db)
    con.execute("""
        CREATE TABLE episodes (podcast TEXT NOT NULL, id INTEGER NOT NULL, url TEXT NOT NULL, title TEXT,
                               description TEXT, date TEXT, content_type TEXT, content_length INTEGER,
                               image_url TEXT, PRIMARY KEY (podcast, id))
    """)
    con.execute("INSERT INTO episodes VALUES ('morning', 1, 'u', 't', 'd', '2026-01-01', 'audio/mpeg', 1, 'i')")
    con.execute("PRAGMA user_version = 1")
    con.commit()
    con.close()

    si.init_db()

    [row] = si.get_all_items("morning")
    assert row["title"] == "t" and row["link"] is None and row["duration_ms"] is None
    assert query(db, "PRAGMA user_version") == [{"user_version": 2}]


def test_a_request_finishing_does_not_close_another_requests_connection():
    """Flask serves requests in threads; they used to share one connection and close it under each other.

    Deterministic version of that race: both threads hold a connection, the first
    one finishes, and the second must still be able to use its own.
    """
    si.init_db()
    both_open = threading.Barrier(2, timeout=5)
    first_closed = threading.Event()
    errors = []

    def first_request():
        try:
            with si.connect():
                both_open.wait()
        except Exception as error:  # noqa: BLE001 - collect everything, assert below
            errors.append(f"first: {error!r}")
        finally:
            first_closed.set()

    def second_request():
        try:
            with si.connect() as conn:
                both_open.wait()
                first_closed.wait(timeout=5)
                conn.execute("SELECT count(*) FROM episodes").fetchone()
        except Exception as error:  # noqa: BLE001
            errors.append(f"second: {error!r}")

    threads = [threading.Thread(target=first_request), threading.Thread(target=second_request)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []


def test_insert_ignores_episodes_already_stored():
    si.init_db()
    si.insert_episodes("morning", [episode(1, title="first")])
    si.insert_episodes("morning", [episode(1, title="second"), episode(2)])
    si.insert_episodes("indagini", [episode(1)])

    assert si.get_all_ids("morning") == {1, 2}
    assert si.get_all_ids("indagini") == {1}
    assert {r["id"]: r["title"] for r in si.get_all_items("morning")}[1] == "first"
