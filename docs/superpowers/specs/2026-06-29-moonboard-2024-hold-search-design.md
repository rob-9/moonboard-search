# MoonBoard 2024 Hold-Search — Design

**Date:** 2026-06-29
**Status:** Approved (pending spec review)

## Goal

Scrape all MoonBoard 2024 hold-set problems from Moon's internal app API into a
local database, and serve a web UI where the user clicks holds on a board and
gets back every climb that uses those holds. No Bluetooth, no physical board.

## Scope

**In scope**
- Authenticate to the internal app API with the user's MoonBoard account.
- Download all 2024 hold-set problems (both 25° and 40° configs) + the board
  hold layout.
- Store normalized in SQLite.
- Flask app: search-by-hold API + an SVG board UI to pick holds and view matches.
- Incremental re-sync (re-run scraper to pick up new problems).

**Out of scope (YAGNI)**
- Other board years (2016/2017/2019/2020) — code stays parameterizable but only
  2024 is wired up and tested.
- Bluetooth / LED control.
- User logbook, comments, repeats sync (the API supports it; not needed for
  hold search).
- Auth/accounts in the web UI — single local user.
- Grade prediction / problem generation.

## Legal / ToS note

This uses Moon Climbing's private API, which their ToS does not authorize.
Build constraints: personal use only, polite rate limiting (sequential requests,
small delay), no redistribution of the scraped database, credentials kept in a
local `.env` (gitignored).

## Verified API mechanics

Confirmed from `rroohhh/moonboard-rs` and `lemeryfertitta/BoardLib` source.

**Auth** — OAuth2 password grant (ASP.NET):
```
POST https://restapimoonboard.ems-x.com/token
Content-Type: application/x-www-form-urlencoded
body: username, password, grant_type=password, client_id=com.moonclimbing.mb
→ { access_token, expires_in, refresh_token, ... }
```
Use `access_token` as `Authorization: Bearer <token>` on subsequent calls.
Token has an expiry; for a single scrape run one token is enough (no refresh
needed initially).

**Problems** — paginated by last-seen id:
```
GET https://restapimoonboard.ems-x.com/v1/_moonapi/problems/v2/{lastProblemId}
→ { "total": <remaining>, "data": [ Problem, ... ] }
```
Start at `lastProblemId = 0`. After each page, set `lastProblemId` to the last
problem's `apiId`. Stop when `total <= 0`. (Mirrors moonboard-rs
`download_problem`.)

Each `Problem` (camelCase JSON) includes at minimum:
- `apiId` (int, problem id)
- `name`, `grade`, `userGrade`, `userRating`
- `isBenchmark`, `repeats`, `setby`
- `moonBoardConfigurationId` (angle config — see below)
- `holdsetup` `{ apiId, description }` (which board/hold-set)
- `moves`: list of `{ description: "A5", isStart: bool, isEnd: bool }`
  — `description` is the hold coordinate (column letter + row number).

**Board layout** — hold positions:
```
GET https://restapimoonboard.ems-x.com/v1/_moonapi/Holdsetup
→ hold setups with holds: { location: { x, y, holdNumber, description }, ... }
```
Used to draw the SVG grid and place clickable holds at real coordinates.

**2024 identifiers** (from BoardLib):
- Board/hold-set: `setupId = 21` (`moon2024`).
- Angle configs: `moonBoardConfigurationId` 2 → 25°, 3 → 40°.

**Robustness lesson:** moonboard-rs breaks on the 2024 board because it uses
strict schema validation (`deny_unknown_fields`). Our parser reads only the
fields it needs from plain dicts and ignores unknown fields, so Moon adding new
JSON keys does not break the scraper.

## Architecture

```
scraper/                SQLite (moonboard.db)        web/ (Flask)
  auth.py        ─┐       problems                    app.py
  client.py       ├──►    moves            ◄────────  search.py  ──► /api/search
  sync.py        ─┘       holds                       templates/board.html
  models/schema           sync_meta                   static/board.js, board.css
```

Three units, each independently testable:

### 1. Scraper (`moonboard_search/scraper/`)
- `auth.py` — `get_token(username, password) -> str`. One function, hits `/token`,
  returns bearer string. Raises on bad creds.
- `client.py` — thin API client holding the token: `iter_problems()` (generator,
  handles pagination), `get_holdsetup()`. Lenient dict parsing. Sleeps a small
  fixed delay between pages.
- `sync.py` — orchestration: auth → fetch holdsetup → fetch problems → filter to
  2024 (`holdsetup.apiId == 21`) → upsert into SQLite → record sync timestamp.
  Idempotent: re-running updates existing rows and inserts new ones.
- CLI entry: `python -m moonboard_search.scraper.sync` (reads creds from env).

### 2. Storage (`moonboard_search/db.py` + `schema.sql`)
Normalized so hold search is a SQL set operation.

```sql
problems(
  api_id INTEGER PRIMARY KEY, name TEXT, grade TEXT, user_grade TEXT,
  user_rating INTEGER, is_benchmark INTEGER, repeats INTEGER, setby TEXT,
  config_id INTEGER,            -- 2 = 25°, 3 = 40°
  angle INTEGER                 -- derived: 25 or 40
)
moves(
  problem_id INTEGER, coord TEXT, is_start INTEGER, is_end INTEGER,
  FOREIGN KEY(problem_id) REFERENCES problems(api_id)
)
holds(coord TEXT PRIMARY KEY, x REAL, y REAL, hold_number TEXT, description TEXT)
sync_meta(key TEXT PRIMARY KEY, value TEXT)   -- last_sync, problem_count
```
Indexes: `moves(coord)`, `moves(problem_id)`, `problems(grade)`,
`problems(angle)`.

### 3. Search + Web (`moonboard_search/web/`)
- `search.py` — pure function `search(required, excluded, start, end, grade,
  angle, benchmark, min_repeats) -> list[problem]`. "Required holds" = problems
  whose move set is a superset of the selected coords (SQL: `GROUP BY problem_id
  HAVING COUNT(DISTINCT coord matched) == n_required`). Optional excluded holds,
  start/end constraints, grade/angle/benchmark/repeat filters. Returns problem
  rows. No HTTP knowledge — unit-testable against a fixture DB.
- `app.py` — Flask. Routes:
  - `GET /` → board page.
  - `GET /api/holds` → hold layout JSON for rendering.
  - `GET /api/search?holds=A5,B7&exclude=&start=&end=&grade=&angle=&benchmark=&min_repeats=`
    → `search()` results as JSON.
  - `GET /api/problem/<id>` → full move set for highlighting.
- `templates/board.html` + `static/board.js`/`board.css` — render the 2024 grid
  as SVG from `/api/holds`, click a hold to cycle states
  (unselected → required → excluded), separate toggles for start/end, show match
  list; clicking a match highlights its full move set on the board.

## Data flow

1. `sync.py` run once: populates `holds`, `problems`, `moves`.
2. Browser loads `/`, fetches `/api/holds`, draws board.
3. User clicks holds → JS builds query → `GET /api/search` → renders match list.
4. User clicks a match → `GET /api/problem/<id>` → board highlights start/middle/
   end holds for that climb.

## Error handling

- **Bad creds / 401 on token** → scraper exits with a clear message.
- **Token expiry mid-scrape** → unlikely in one run; if a 401 appears during
  pagination, re-auth once and continue.
- **Schema drift** → ignored unknown fields; a missing *required* field on a
  problem logs a warning and skips that problem rather than crashing the run.
- **Empty/partial sync** → `sync_meta` only updated on successful completion;
  search works against whatever is in the DB.
- **Web: no DB yet** → `/` shows a "run the scraper first" message.
- **Rate limiting / network** → fixed small delay between pages; on a request
  error, retry a couple times with backoff, then fail the run with the last id
  reached (re-run resumes since upserts are idempotent).

## Testing

- `auth.py` — mock the `/token` POST: success returns token; 400 raises.
- `client.py` — mock paginated responses: verify it walks pages by last id and
  stops on `total <= 0`; verify lenient parsing ignores unknown fields and a
  malformed problem is skipped.
- `sync.py` — against a temp SQLite: verify 2024 filter, upsert idempotency
  (run twice → no duplicates), `sync_meta` written.
- `search.py` — fixture DB with a handful of problems: required-holds superset
  logic, excluded holds, start/end, grade/angle/benchmark/min_repeats filters,
  combinations.
- `app.py` — Flask test client: routes return expected JSON shapes; `/api/search`
  passes params through to `search()`.

## Tech / deps

Python 3.11+, `requests`, `Flask`, stdlib `sqlite3`. Vanilla JS + SVG frontend
(no build step). `pytest` + `responses` (or `requests-mock`) for tests.
Creds in `.env` (`python-dotenv`), gitignored.

## Open questions / assumptions

- Exact move-coord grid (columns A–K vs A–L, 18 rows) is **derived from the
  Holdsetup response at runtime**, not hardcoded — avoids guessing 2024 geometry.
- Problem count for 2024 is unknown but bounded; full scrape is a one-time
  sequential walk, expected minutes, well under any practical limit.
