import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "coldbrew.db")


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def create_tables():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS feeds (
            id             TEXT PRIMARY KEY,
            feed_name      TEXT NOT NULL,
            file_path      TEXT NOT NULL,
            status         TEXT NOT NULL DEFAULT 'processing',
            error_message  TEXT,
            analysis_mode  TEXT NOT NULL DEFAULT 'standard',
            created_at     TEXT NOT NULL,
            event_count    INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS events (
            id            TEXT PRIMARY KEY,
            feed_id       TEXT NOT NULL REFERENCES feeds(id),
            timestamp     TEXT NOT NULL,
            category      TEXT NOT NULL,
            severity      TEXT NOT NULL,
            title         TEXT NOT NULL,
            description   TEXT NOT NULL,
            source_feed   TEXT NOT NULL,
            thumbnail_url TEXT,
            confidence    REAL NOT NULL,
            status        TEXT NOT NULL DEFAULT 'new',
            created_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id          TEXT PRIMARY KEY,
            message     TEXT NOT NULL,
            sent_to     TEXT NOT NULL,
            event_ids   TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );
        """
    )
    conn.close()
