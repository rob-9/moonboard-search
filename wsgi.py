"""Vercel / WSGI entrypoint.

Vercel auto-detects a Flask instance named `app` at this supported entrypoint.
Serves the committed, read-only SQLite database bundled with the deployment
(Vercel's filesystem is read-only, so the scraper is run locally and the
resulting moonboard.db is committed to the repo).
"""

import os

from moonboard_search.web.app import create_app

DB_PATH = os.path.join(os.path.dirname(__file__), "moonboard.db")

app = create_app(DB_PATH, read_only=True)
