from moonboard_search import db
from moonboard_search.scraper import sync


def _raw_problem(api_id=1, setup_id=21, config_id=3, **over):
    p = {
        "apiId": api_id,
        "name": "Test Problem",
        "grade": "6B+",
        "userGrade": "6C",
        "userRating": 3,
        "isBenchmark": True,
        "repeats": 42,
        "setby": "someone",
        "moonBoardConfigurationId": config_id,
        "holdsetup": {"apiId": setup_id, "description": "MoonBoard 2024"},
        "moves": [
            {"description": "A5", "isStart": True, "isEnd": False},
            {"description": "K18", "isStart": False, "isEnd": True},
        ],
    }
    p.update(over)
    return p


def test_parse_problem_extracts_fields_and_angle():
    out = sync.parse_problem(_raw_problem(config_id=2))
    assert out["api_id"] == 1
    assert out["grade"] == "6B+"
    assert out["is_benchmark"] == 1
    assert out["repeats"] == 42
    assert out["angle"] == 25  # config 2 -> 25 degrees
    assert {m["coord"] for m in out["moves"]} == {"A5", "K18"}
    start = next(m for m in out["moves"] if m["coord"] == "A5")
    assert start["is_start"] == 1 and start["is_end"] == 0


def test_parse_problem_rejects_non_2024_board():
    assert sync.parse_problem(_raw_problem(setup_id=17)) is None  # 2019 board


def test_parse_problem_skips_malformed():
    assert sync.parse_problem({"name": "no id"}) is None


def test_sync_inserts_only_2024_problems():
    conn = db.connect(":memory:")
    db.init_db(conn)
    raws = [
        _raw_problem(api_id=1, setup_id=21),
        _raw_problem(api_id=2, setup_id=17),  # not 2024
        _raw_problem(api_id=3, setup_id=21),
    ]
    n = sync.sync_problems(conn, raws)
    assert n == 2
    ids = {r["api_id"] for r in conn.execute("SELECT api_id FROM problems")}
    assert ids == {1, 3}


def test_sync_is_idempotent():
    conn = db.connect(":memory:")
    db.init_db(conn)
    raws = [_raw_problem(api_id=1)]
    sync.sync_problems(conn, raws)
    sync.sync_problems(conn, raws)  # run again
    assert conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0] == 1
    # moves not duplicated either
    assert conn.execute("SELECT COUNT(*) FROM moves").fetchone()[0] == 2


def test_sync_updates_changed_problem():
    conn = db.connect(":memory:")
    db.init_db(conn)
    sync.sync_problems(conn, [_raw_problem(api_id=1, repeats=1)])
    sync.sync_problems(conn, [_raw_problem(api_id=1, repeats=99)])
    row = conn.execute("SELECT repeats FROM problems WHERE api_id=1").fetchone()
    assert row["repeats"] == 99


def test_parse_holds_extracts_coordinates():
    payload = [
        {
            "id": 21,
            "description": "MoonBoard Masters 2024",
            "holdsets": [
                {
                    "holds": [
                        {
                            "location": {
                                "description": "A5",
                                "holdNumber": "A5",
                                "x": 10.0,
                                "y": 200.0,
                            }
                        },
                        {
                            "location": {
                                "description": "B7",
                                "holdNumber": "B7",
                                "x": 30.0,
                                "y": 150.0,
                            }
                        },
                    ]
                }
            ],
        },
        {"id": 17, "holdsets": [{"holds": [{"location": {"description": "Z9", "x": 1, "y": 1}}]}]},
    ]
    holds = sync.parse_holds(payload, setup_id=21)
    coords = {h["coord"]: h for h in holds}
    assert set(coords) == {"A5", "B7"}  # only 2024 setup, not 2019
    assert coords["A5"]["x"] == 10.0 and coords["A5"]["y"] == 200.0


def test_save_holds_is_idempotent():
    conn = db.connect(":memory:")
    db.init_db(conn)
    holds = [{"coord": "A5", "x": 1.0, "y": 2.0, "hold_number": "A5", "description": "A5"}]
    sync.save_holds(conn, holds)
    sync.save_holds(conn, holds)
    assert conn.execute("SELECT COUNT(*) FROM holds").fetchone()[0] == 1


def test_sync_records_meta():
    conn = db.connect(":memory:")
    db.init_db(conn)
    sync.sync_problems(conn, [_raw_problem(api_id=1)])
    sync.set_sync_meta(conn, count=1)
    meta = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM sync_meta")}
    assert meta["problem_count"] == "1"
    assert "last_sync" in meta
