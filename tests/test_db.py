import sqlite3

from moonboard_search import db


def test_init_db_creates_tables(tmp_path):
    path = tmp_path / "test.db"
    conn = db.connect(str(path))
    db.init_db(conn)

    names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert {"problems", "moves", "holds", "sync_meta"} <= names


def test_init_db_is_idempotent(tmp_path):
    path = tmp_path / "test.db"
    conn = db.connect(str(path))
    db.init_db(conn)
    db.init_db(conn)  # second run must not raise
    count = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
    assert count == 0


def test_connect_returns_rows_as_mappings(tmp_path):
    conn = db.connect(str(tmp_path / "test.db"))
    db.init_db(conn)
    conn.execute(
        "INSERT INTO problems (api_id, name, grade) VALUES (1, 'Test', '6B')"
    )
    row = conn.execute("SELECT name, grade FROM problems").fetchone()
    assert row["name"] == "Test"
    assert row["grade"] == "6B"


def test_moves_index_exists(tmp_path):
    conn = db.connect(str(tmp_path / "test.db"))
    db.init_db(conn)
    indexes = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
    }
    assert any("moves" in name and "coord" in name for name in indexes)
