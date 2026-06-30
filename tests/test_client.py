import re

import responses

from moonboard_search.scraper import client

API = "https://restapimoonboard.ems-x.com/v1/_moonapi"


def _problems_url_matcher():
    return re.compile(re.escape(f"{API}/problems/v2/") + r"\d+")


@responses.activate
def test_iter_problems_walks_pages_by_last_id():
    # Page 1: lastId=0 -> two problems, total still > 0
    responses.add(
        responses.GET,
        f"{API}/problems/v2/0",
        json={"total": 1, "data": [{"apiId": 10}, {"apiId": 20}]},
        status=200,
    )
    # Page 2: lastId=20 -> one problem, total now 0 -> stop
    responses.add(
        responses.GET,
        f"{API}/problems/v2/20",
        json={"total": 0, "data": [{"apiId": 30}]},
        status=200,
    )

    c = client.MoonBoardClient("tok", delay=0)
    ids = [p["apiId"] for p in c.iter_problems()]

    assert ids == [10, 20, 30]


@responses.activate
def test_iter_problems_stops_on_empty_data():
    responses.add(
        responses.GET,
        f"{API}/problems/v2/0",
        json={"total": 999, "data": []},  # claims more but sends nothing
        status=200,
    )

    c = client.MoonBoardClient("tok", delay=0)
    assert list(c.iter_problems()) == []


@responses.activate
def test_iter_problems_sends_bearer_token():
    responses.add(
        responses.GET,
        f"{API}/problems/v2/0",
        json={"total": 0, "data": [{"apiId": 1}]},
        status=200,
    )

    c = client.MoonBoardClient("mytoken", delay=0)
    list(c.iter_problems())

    assert responses.calls[0].request.headers["Authorization"] == "Bearer mytoken"


@responses.activate
def test_get_holdsetup_returns_payload():
    responses.add(
        responses.GET,
        f"{API}/Holdsetup",
        json=[{"id": 21, "holdsets": []}],
        status=200,
    )

    c = client.MoonBoardClient("tok", delay=0)
    assert c.get_holdsetup() == [{"id": 21, "holdsets": []}]
