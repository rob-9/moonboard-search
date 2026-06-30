"""Flask app: serves the board UI and the hold-search JSON API."""

from flask import Flask, abort, g, jsonify, render_template, request

from .. import db
from . import search


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or db.DEFAULT_DB

    def get_conn():
        if "conn" not in g:
            g.conn = db.connect(app.config["DB_PATH"])
        return g.conn

    @app.teardown_appcontext
    def close_conn(exc):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    @app.route("/")
    def index():
        return render_template("board.html")

    @app.route("/api/holds")
    def api_holds():
        conn = get_conn()
        rows = conn.execute(
            "SELECT coord, x, y, hold_number, description FROM holds"
        ).fetchall()
        if rows:
            return jsonify([dict(r) for r in rows])
        # No stored layout — fall back to distinct coords used by climbs so the
        # board still renders (positions derived client-side from the coord).
        coords = conn.execute(
            "SELECT DISTINCT coord FROM moves ORDER BY coord"
        ).fetchall()
        return jsonify(
            [
                {"coord": c["coord"], "x": None, "y": None,
                 "hold_number": None, "description": None}
                for c in coords
            ]
        )

    @app.route("/api/search")
    def api_search():
        rows = search.search(get_conn(), **_parse_search_args(request.args))
        return jsonify([dict(r) for r in rows])

    @app.route("/api/problem/<int:problem_id>")
    def api_problem(problem_id):
        problem = search.get_problem(get_conn(), problem_id)
        if problem is None:
            abort(404)
        return jsonify(problem)

    return app


def _csv(args, key):
    raw = args.get(key, "").strip()
    return [c.strip() for c in raw.split(",") if c.strip()] if raw else None


def _int(args, key):
    val = args.get(key)
    if val in (None, ""):
        return None
    try:
        return int(val)
    except ValueError:
        return None


def _parse_search_args(args):
    return {
        "required": _csv(args, "holds"),
        "excluded": _csv(args, "exclude"),
        "start": _csv(args, "start"),
        "end": _csv(args, "end"),
        "grade": args.get("grade") or None,
        "angle": _int(args, "angle"),
        "benchmark": args.get("benchmark") in ("1", "true", "on"),
        "min_repeats": _int(args, "min_repeats"),
    }
