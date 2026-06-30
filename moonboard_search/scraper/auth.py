"""Authenticate to the MoonBoard internal app API (OAuth2 password grant)."""

import requests

TOKEN_URL = "https://restapimoonboard.ems-x.com/token"
CLIENT_ID = "com.moonclimbing.mb"


class AuthError(Exception):
    """Raised when authentication fails."""


def get_token(username, password, timeout=30):
    """Exchange MoonBoard credentials for a bearer access token.

    Returns the access_token string. Raises AuthError on failure.
    """
    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "username": username,
                "password": password,
                "grant_type": "password",
                "client_id": CLIENT_ID,
            },
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise AuthError(f"MoonBoard login request failed: {exc}") from exc

    if resp.status_code != 200:
        detail = _error_detail(resp)
        raise AuthError(f"MoonBoard login failed ({resp.status_code}): {detail}")

    try:
        body = resp.json()
    except ValueError as exc:
        raise AuthError("MoonBoard login returned a non-JSON response") from exc

    token = body.get("access_token")
    if not token:
        raise AuthError("MoonBoard login returned no access_token")
    return token


def _error_detail(resp):
    try:
        body = resp.json()
        return body.get("error_description") or body.get("error") or resp.text
    except ValueError:
        return resp.text
