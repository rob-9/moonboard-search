"""Orchestrate a scrape: fetch, filter to the 2024 board, upsert into SQLite.

Re-running is idempotent: existing problems are replaced and their moves
rebuilt, new problems inserted. Only successful completion updates sync_meta.
"""

import datetime
import logging
import os

from .. import db
from . import auth
from .client import MoonBoardClient

log = logging.getLogger(__name__)

# MoonBoard 2024 hold-set identifier (BoardLib BOARD_IDS["moon2024"]).
MOON2024_SETUP_ID = 21

# moonBoardConfigurationId -> wall angle in degrees (BoardLib ANGLES_TO_IDS).
CONFIG_TO_ANGLE = {2: 25, 3: 40}


def parse_problem(raw, setup_id=MOON2024_SETUP_ID):
    """Normalize a raw API problem dict, or return None to skip it.

    Skips problems that are not on the given board or lack an id.
    Tolerates unknown/extra fields (schema drift).
    """
    api_id = raw.get("apiId")
    if api_id is None:
        return None

    holdsetup = raw.get("holdsetup") or {}
    if holdsetup.get("apiId") != setup_id:
        return None

    config_id = raw.get("moonBoardConfigurationId")
    moves = []
    for m in raw.get("moves") or []:
        coord = m.get("description")
        if not coord:
            continue
        moves.append(
            {
                "coord": coord,
                "is_start": 1 if m.get("isStart") else 0,
                "is_end": 1 if m.get("isEnd") else 0,
            }
        )

    return {
        "api_id": api_id,
        "name": raw.get("name"),
        "grade": raw.get("grade"),
        "user_grade": raw.get("userGrade"),
        "user_rating": raw.get("userRating"),
        "is_benchmark": 1 if raw.get("isBenchmark") else 0,
        "repeats": raw.get("repeats") or 0,
        "setby": raw.get("setby"),
        "config_id": config_id,
        "angle": CONFIG_TO_ANGLE.get(config_id),
        "moves": moves,
    }


def upsert_problem(conn, problem):
    """Insert or replace a single problem and rebuild its moves."""
    conn.execute(
        """
        INSERT OR REPLACE INTO problems
            (api_id, name, grade, user_grade, user_rating,
             is_benchmark, repeats, setby, config_id, angle)
        VALUES (:api_id, :name, :grade, :user_grade, :user_rating,
                :is_benchmark, :repeats, :setby, :config_id, :angle)
        """,
        problem,
    )
    conn.execute("DELETE FROM moves WHERE problem_id = ?", (problem["api_id"],))
    conn.executemany(
        "INSERT INTO moves (problem_id, coord, is_start, is_end) "
        "VALUES (?, ?, ?, ?)",
        [
            (problem["api_id"], m["coord"], m["is_start"], m["is_end"])
            for m in problem["moves"]
        ],
    )


def sync_problems(conn, raw_problems, setup_id=MOON2024_SETUP_ID):
    """Parse and upsert an iterable of raw problems. Returns count stored."""
    count = 0
    for raw in raw_problems:
        problem = parse_problem(raw, setup_id=setup_id)
        if problem is None:
            continue
        upsert_problem(conn, problem)
        count += 1
    conn.commit()
    return count


def parse_holds(holdsetup_payload, setup_id=MOON2024_SETUP_ID):
    """Extract hold coordinates and positions for the given board setup."""
    holds = {}
    for setup in holdsetup_payload or []:
        if setup.get("id") != setup_id:
            continue
        for holdset in setup.get("holdsets") or []:
            for hold in holdset.get("holds") or []:
                loc = hold.get("location") or {}
                coord = loc.get("description") or loc.get("holdNumber")
                if not coord:
                    continue
                holds[coord] = {
                    "coord": coord,
                    "x": loc.get("x"),
                    "y": loc.get("y"),
                    "hold_number": loc.get("holdNumber"),
                    "description": loc.get("description"),
                }
    return list(holds.values())


def save_holds(conn, holds):
    """Insert or replace hold layout rows."""
    conn.executemany(
        "INSERT OR REPLACE INTO holds (coord, x, y, hold_number, description) "
        "VALUES (:coord, :x, :y, :hold_number, :description)",
        holds,
    )
    conn.commit()


def set_sync_meta(conn, count):
    """Record a successful sync timestamp and problem count."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.executemany(
        "INSERT OR REPLACE INTO sync_meta (key, value) VALUES (?, ?)",
        [("last_sync", now), ("problem_count", str(count))],
    )
    conn.commit()


def run(username, password, conn):
    """Full scrape: auth, fetch holds + problems, store, record meta."""
    token = auth.get_token(username, password)
    client = MoonBoardClient(token)

    log.info("fetching hold setup")
    holds = parse_holds(client.get_holdsetup())
    save_holds(conn, holds)
    log.info("saved %d holds", len(holds))

    log.info("fetching problems")
    count = sync_problems(conn, client.iter_problems())
    set_sync_meta(conn, count)
    log.info("stored %d 2024 problems", count)
    return count


def main():  # pragma: no cover - thin CLI wrapper
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    username = os.environ.get("MOONBOARD_USER")
    password = os.environ.get("MOONBOARD_PASS")
    if not username or not password:
        raise SystemExit("Set MOONBOARD_USER and MOONBOARD_PASS (see .env.example)")

    conn = db.connect()
    db.init_db(conn)
    run(username, password, conn)


if __name__ == "__main__":  # pragma: no cover
    main()
