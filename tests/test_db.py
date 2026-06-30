import sqlite3

import pytest

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


def test_readonly_connection_allows_reads_blocks_writes(tmp_path):
    path = tmp_path / "ro.db"
    conn = db.connect(str(path))
    db.init_db(conn)
    conn.execute("INSERT INTO problems (api_id, name) VALUES (1, 'X')")
    conn.commit()
    conn.close()

    ro = db.connect(str(path), read_only=True)
    assert ro.execute("SELECT name FROM problems").fetchone()["name"] == "X"
    with pytest.raises(sqlite3.OperationalError):
        ro.execute("INSERT INTO problems (api_id, name) VALUES (2, 'Y')")


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
