from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.database import Database


def test_database_connection_is_configured_for_concurrent_backend_access(tmp_path):
    db = Database(tmp_path / "agora.db")

    busy_timeout = db.conn.execute("PRAGMA busy_timeout").fetchone()[0]
    journal_mode = db.conn.execute("PRAGMA journal_mode").fetchone()[0]
    synchronous = db.conn.execute("PRAGMA synchronous").fetchone()[0]

    assert busy_timeout == 30_000
    assert journal_mode == "wal"
    assert synchronous == 1


def test_database_connection_serializes_concurrent_writes(tmp_path):
    db = Database(tmp_path / "agora.db")
    db.conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    db.conn.commit()

    def insert_one(index: int) -> None:
        db.conn.execute("INSERT INTO items (value) VALUES (?)", (f"value-{index}",))
        db.conn.commit()

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(insert_one, range(80)))

    count = db.conn.execute("SELECT count(*) FROM items").fetchone()[0]

    assert count == 80
