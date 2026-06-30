"""SQLite connection and schema initialization."""

import os
import sqlite3

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

DEFAULT_DB = os.environ.get("MOONBOARD_DB", "moonboard.db")


def connect(path=DEFAULT_DB):
    """Open a SQLite connection with row-as-mapping access and FKs enabled."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    """Create tables and indexes if they do not exist. Idempotent."""
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        conn.executescript(fh.read())
    conn.commit()
