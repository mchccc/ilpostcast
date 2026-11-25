import os
import sqlite3
from contextlib import contextmanager


DB_FILE = os.environ.get("DB_FILE")

# Bumped whenever init_db() learns a new migration step; stored in PRAGMA user_version.
SCHEMA_VERSION = 1

# Column set of the old one-table-per-podcast layout, used to recognise those tables.
LEGACY_COLUMNS = {"id", "url", "desc", "title", "date", "content_type", "content_length", "image_id"}


@contextmanager
def connect():
    """Open a new connection, commit on success (roll back on error), and always close it.

    Every call gets its own connection, so this is safe from Flask's request
    threads and from the scraper's worker processes alike.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db():
    """Create the schema if needed and migrate data from the old layout once."""
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                podcast        TEXT    NOT NULL,
                id             INTEGER NOT NULL,
                url            TEXT    NOT NULL,
                title          TEXT,
                description    TEXT,
                date           TEXT,
                content_type   TEXT,
                content_length INTEGER,
                image_url      TEXT,
                PRIMARY KEY (podcast, id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS episodes_by_date ON episodes (podcast, date)")
        (version,) = conn.execute("PRAGMA user_version").fetchone()
        if version < 1:
            _migrate_legacy_tables(conn)
        if version < SCHEMA_VERSION:
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _migrate_legacy_tables(conn):
    """Copy every old per-podcast table (plus its images) into `episodes`.

    The old tables are left untouched, so this can't lose data; drop them by
    hand once you're happy with the result. Where the old `image` table has
    several rows for one id (the worker-collision bug), the first one inserted
    wins, since later rows with the same id were the collisions. Rows whose id
    was stored as an integer (API era) win over text ids (old HTML scraper)
    for the same episode.
    """
    tables = [name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    image_url = (
        "(SELECT image.url FROM image WHERE image.id = t.image_id ORDER BY image.rowid LIMIT 1)"
        if "image" in tables else "NULL"
    )
    for table in tables:
        columns = {row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")')}
        if columns != LEGACY_COLUMNS:
            continue
        conn.execute(f"""
            INSERT OR IGNORE INTO episodes
                (podcast, id, url, title, description, date, content_type, content_length, image_url)
            SELECT ?, t.id, t.url, t.title, t."desc", t.date, t.content_type, t.content_length, {image_url}
            FROM "{table}" AS t
            ORDER BY typeof(t.id) = 'integer' DESC
        """, (table,))


def get_all_ids(podcast):
    with connect() as conn:
        return {episode_id for (episode_id,) in conn.execute("SELECT id FROM episodes WHERE podcast = ?", (podcast,))}


def insert_episodes(podcast, episodes):
    """Insert episodes for a podcast in one transaction; already-stored ids are ignored."""
    with connect() as conn:
        conn.executemany("""
            INSERT OR IGNORE INTO episodes
                (podcast, id, url, title, description, date, content_type, content_length, image_url)
            VALUES
                (:podcast, :id, :url, :title, :description, :date, :content_type, :content_length, :image_url)
        """, [{**episode, "podcast": podcast} for episode in episodes])


def get_all_items(podcast):
    with connect() as conn:
        return conn.execute("""
            SELECT id, url, description, title, date, content_type, content_length, image_url
            FROM episodes
            WHERE podcast = ?
            ORDER BY date DESC
        """, (podcast,)).fetchall()
