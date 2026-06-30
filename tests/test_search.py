import pytest

from moonboard_search import db
from moonboard_search.web import search


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.init_db(c)
    # Three problems with known holds.
    problems = [
        # api_id, name, grade, angle, benchmark, repeats, moves(coord,start,end)
        (1, "Alpha", "6B", 40, 1, 100,
         [("A5", 1, 0), ("F10", 0, 0), ("K18", 0, 1)]),
        (2, "Beta", "7A", 40, 0, 5,
         [("A5", 1, 0), ("C7", 0, 0), ("K18", 0, 1)]),
        (3, "Gamma", "6B", 25, 0, 50,
         [("B6", 1, 0), ("F10", 0, 0), ("J17", 0, 1)]),
    ]
    for api_id, name, grade, angle, bench, repeats, moves in problems:
        c.execute(
            "INSERT INTO problems (api_id, name, grade, angle, is_benchmark, repeats) "
            "VALUES (?,?,?,?,?,?)",
            (api_id, name, grade, angle, bench, repeats),
        )
        c.executemany(
            "INSERT INTO moves (problem_id, coord, is_start, is_end) VALUES (?,?,?,?)",
            [(api_id, co, s, e) for co, s, e in moves],
        )
    c.commit()
    return c


def ids(rows):
    return {r["api_id"] for r in rows}


def test_required_single_hold(conn):
    assert ids(search.search(conn, required=["F10"])) == {1, 3}


def test_required_multiple_holds_is_superset_match(conn):
    # Only problems containing BOTH A5 and C7.
    assert ids(search.search(conn, required=["A5", "C7"])) == {2}


def test_required_returns_nothing_when_no_superset(conn):
    assert ids(search.search(conn, required=["A5", "B6"])) == set()


def test_excluded_hold_filters_out(conn):
    # A5 climbs are {1,2}; exclude C7 removes 2.
    assert ids(search.search(conn, required=["A5"], excluded=["C7"])) == {1}


def test_start_hold_constraint(conn):
    # B6 is a start hold only on problem 3.
    assert ids(search.search(conn, start=["B6"])) == {3}
    # A5 used as start on 1 and 2.
    assert ids(search.search(conn, start=["A5"])) == {1, 2}


def test_end_hold_constraint(conn):
    assert ids(search.search(conn, end=["K18"])) == {1, 2}


def test_grade_filter(conn):
    assert ids(search.search(conn, grade="6B")) == {1, 3}


def test_angle_filter(conn):
    assert ids(search.search(conn, angle=25)) == {3}


def test_benchmark_filter(conn):
    assert ids(search.search(conn, benchmark=True)) == {1}


def test_min_repeats_filter(conn):
    assert ids(search.search(conn, min_repeats=50)) == {1, 3}


def test_combined_filters(conn):
    rows = search.search(conn, required=["A5"], grade="6B", angle=40)
    assert ids(rows) == {1}


def test_no_filters_returns_all(conn):
    assert ids(search.search(conn)) == {1, 2, 3}


def test_results_include_useful_fields(conn):
    row = search.search(conn, required=["C7"])[0]
    assert row["name"] == "Beta"
    assert row["grade"] == "7A"


def test_get_problem_returns_moves(conn):
    p = search.get_problem(conn, 1)
    assert p["name"] == "Alpha"
    coords = {m["coord"] for m in p["moves"]}
    assert coords == {"A5", "F10", "K18"}
    start = next(m for m in p["moves"] if m["coord"] == "A5")
    assert start["is_start"] == 1


def test_get_problem_missing_returns_none(conn):
    assert search.get_problem(conn, 999) is None
