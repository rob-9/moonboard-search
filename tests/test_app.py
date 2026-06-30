import pytest

from moonboard_search import db
from moonboard_search.web.app import create_app


@pytest.fixture
def client(tmp_path):
    path = tmp_path / "app.db"
    conn = db.connect(str(path))
    db.init_db(conn)
    conn.execute(
        "INSERT INTO problems (api_id, name, grade, angle, is_benchmark, repeats) "
        "VALUES (1, 'Alpha', '6B', 40, 1, 100)"
    )
    conn.executemany(
        "INSERT INTO moves (problem_id, coord, is_start, is_end) VALUES (?,?,?,?)",
        [(1, "A5", 1, 0), (1, "F10", 0, 0), (1, "K18", 0, 1)],
    )
    conn.execute(
        "INSERT INTO holds (coord, x, y) VALUES ('A5', 10, 20), ('F10', 30, 40)"
    )
    conn.commit()
    conn.close()

    app = create_app(str(path))
    app.config["TESTING"] = True
    return app.test_client()


def test_index_serves_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"<svg" in resp.data or b"board" in resp.data.lower()


def test_api_holds_returns_layout(client):
    resp = client.get("/api/holds")
    assert resp.status_code == 200
    data = resp.get_json()
    coords = {h["coord"] for h in data}
    assert coords == {"A5", "F10"}


def test_api_search_by_hold(client):
    resp = client.get("/api/search?holds=F10")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["name"] == "Alpha"


def test_api_search_no_match(client):
    resp = client.get("/api/search?holds=Z9")
    assert resp.get_json() == []


def test_api_search_passes_filters(client):
    # Grade filter that excludes the only problem.
    assert client.get("/api/search?grade=8A").get_json() == []
    assert len(client.get("/api/search?grade=6B").get_json()) == 1


def test_api_search_benchmark_and_angle(client):
    assert len(client.get("/api/search?benchmark=1&angle=40").get_json()) == 1
    assert client.get("/api/search?angle=25").get_json() == []


def test_api_problem_returns_moves(client):
    resp = client.get("/api/problem/1")
    data = resp.get_json()
    assert data["name"] == "Alpha"
    assert {m["coord"] for m in data["moves"]} == {"A5", "F10", "K18"}


def test_api_problem_404(client):
    assert client.get("/api/problem/999").status_code == 404
