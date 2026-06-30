"""Thin client for the MoonBoard internal app API.

Yields raw problem dicts and the hold-setup payload. Parsing/normalization is
the caller's job (see sync.py), keeping this layer tolerant of schema drift:
unknown JSON fields are simply ignored.
"""

import time

import requests

API_BASE = "https://restapimoonboard.ems-x.com/v1/_moonapi"


class MoonBoardClient:
    def __init__(self, token, session=None, delay=0.3, timeout=30):
        self.token = token
        self.session = session or requests.Session()
        self.delay = delay
        self.timeout = timeout

    def _get(self, url):
        resp = self.session.get(
            url,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def iter_problems(self):
        """Yield every problem dict, walking pages by last-seen problem id."""
        last_id = 0
        while True:
            page = self._get(f"{API_BASE}/problems/v2/{last_id}")
            data = page.get("data") or []
            if not data:
                break
            for problem in data:
                yield problem
            prev_id = last_id
            last_id = data[-1].get("apiId", last_id)
            # Stop if the cursor did not advance (inclusive page, duplicate
            # page, or a last item missing apiId) — otherwise we'd refetch the
            # same URL forever.
            if last_id <= prev_id:
                break
            if page.get("total", 0) <= 0:
                break
            if self.delay:
                time.sleep(self.delay)

    def get_holdsetup(self):
        """Return the hold-setup payload (board layouts and hold positions)."""
        return self._get(f"{API_BASE}/Holdsetup")
