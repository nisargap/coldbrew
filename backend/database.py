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
            id                TEXT PRIMARY KEY,
            feed_name         TEXT NOT NULL,
            file_path         TEXT NOT NULL,
            status            TEXT NOT NULL DEFAULT 'processing',
            error_message     TEXT,
            analysis_mode     TEXT NOT NULL DEFAULT 'standard',
            confidence_level  TEXT NOT NULL DEFAULT 'low',
            created_at        TEXT NOT NULL,
            event_count       INTEGER DEFAULT 0,
            stream_url        TEXT,
            nomadic_stream_id TEXT,
            session_id        TEXT
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

        CREATE TABLE IF NOT EXISTS personas (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            role        TEXT NOT NULL,
            category    TEXT,
            created_at  TEXT NOT NULL
        );
        """
    )

    # Seed default personas if table is empty
    count = conn.execute("SELECT COUNT(*) FROM personas").fetchone()[0]
    if count == 0:
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn.executemany(
            "INSERT INTO personas (id, name, role, category, created_at) VALUES (?, ?, ?, ?, ?)",
            [
                ("alex-rivera", "Alex Rivera", "Warehouse Manager", None, now),
                ("sam-okafor", "Sam Okafor", "Maintenance Technician", "Equipment", now),
                ("jordan-lin", "Jordan Lin", "Dock Supervisor", "Shipment", now),
                ("priya-desai", "Priya Desai", "Safety Officer", "Safety", now),
            ],
        )
        conn.commit()

    conn.close()
