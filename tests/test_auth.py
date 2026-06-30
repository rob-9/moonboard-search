import pytest
import requests
import responses

from moonboard_search.scraper import auth


@responses.activate
def test_get_token_returns_access_token():
    responses.add(
        responses.POST,
        auth.TOKEN_URL,
        json={"access_token": "abc123", "token_type": "bearer", "expires_in": 3600},
        status=200,
    )

    token = auth.get_token("user", "pass")

    assert token == "abc123"


@responses.activate
def test_get_token_sends_password_grant_payload():
    responses.add(
        responses.POST,
        auth.TOKEN_URL,
        json={"access_token": "abc123"},
        status=200,
    )

    auth.get_token("alice", "secret")

    body = responses.calls[0].request.body
    assert "grant_type=password" in body
    assert "client_id=com.moonclimbing.mb" in body
    assert "username=alice" in body
    assert "password=secret" in body


@responses.activate
def test_get_token_wraps_network_error_as_autherror():
    responses.add(
        responses.POST,
        auth.TOKEN_URL,
        body=requests.exceptions.ConnectionError("boom"),
    )
    with pytest.raises(auth.AuthError):
        auth.get_token("user", "pass")


@responses.activate
def test_get_token_wraps_non_json_success_as_autherror():
    responses.add(
        responses.POST,
        auth.TOKEN_URL,
        body="<html>maintenance</html>",
        status=200,
        content_type="text/html",
    )
    with pytest.raises(auth.AuthError):
        auth.get_token("user", "pass")


@responses.activate
def test_get_token_raises_on_invalid_grant():
    responses.add(
        responses.POST,
        auth.TOKEN_URL,
        json={"error": "invalid_grant", "error_description": "bad creds"},
        status=400,
    )

    with pytest.raises(auth.AuthError):
        auth.get_token("user", "wrong")
