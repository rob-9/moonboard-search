"""Search climbs by hold and metadata against the local SQLite database.

Pure data layer: takes a connection and filter args, returns problem rows.
No HTTP knowledge, so it is unit-testable on a fixture database.
"""


def _superset_clause(coords, *, start_only=False, end_only=False):
    """SQL subquery: problem ids whose moves include ALL given coords."""
    placeholders = ",".join("?" for _ in coords)
    extra = ""
    if start_only:
        extra = " AND is_start = 1"
    elif end_only:
        extra = " AND is_end = 1"
    sql = (
        f"SELECT problem_id FROM moves WHERE coord IN ({placeholders}){extra} "
        f"GROUP BY problem_id HAVING COUNT(DISTINCT coord) = ?"
    )
    return sql, list(coords) + [len(set(coords))]


def search(
    conn,
    required=None,
    excluded=None,
    start=None,
    end=None,
    grade=None,
    angle=None,
    benchmark=None,
    min_repeats=None,
    limit=500,
):
    """Return problem rows matching the given constraints.

    - required: climb must use every one of these holds (superset match)
    - excluded: climb must use none of these holds
    - start / end: climb's start / end holds must include all of these
    - grade, angle: exact match
    - benchmark: if truthy, only benchmark problems
    - min_repeats: minimum repeat count
    """
    conditions = []
    params = []

    if required:
        sub, sub_params = _superset_clause(required)
        conditions.append(f"p.api_id IN ({sub})")
        params += sub_params

    if excluded:
        placeholders = ",".join("?" for _ in excluded)
        conditions.append(
            f"p.api_id NOT IN (SELECT problem_id FROM moves "
            f"WHERE coord IN ({placeholders}))"
        )
        params += list(excluded)

    if start:
        sub, sub_params = _superset_clause(start, start_only=True)
        conditions.append(f"p.api_id IN ({sub})")
        params += sub_params

    if end:
        sub, sub_params = _superset_clause(end, end_only=True)
        conditions.append(f"p.api_id IN ({sub})")
        params += sub_params

    if grade:
        conditions.append("p.grade = ?")
        params.append(grade)

    if angle is not None:
        conditions.append("p.angle = ?")
        params.append(angle)

    if benchmark:
        conditions.append("p.is_benchmark = 1")

    if min_repeats is not None:
        conditions.append("p.repeats >= ?")
        params.append(min_repeats)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = (
        f"SELECT * FROM problems p {where} "
        f"ORDER BY p.repeats DESC, p.api_id LIMIT ?"
    )
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def get_problem(conn, problem_id):
    """Return one problem with its moves, or None."""
    row = conn.execute(
        "SELECT * FROM problems WHERE api_id = ?", (problem_id,)
    ).fetchone()
    if row is None:
        return None
    moves = conn.execute(
        "SELECT coord, is_start, is_end FROM moves WHERE problem_id = ?",
        (problem_id,),
    ).fetchall()
    result = dict(row)
    result["moves"] = [dict(m) for m in moves]
    return result
