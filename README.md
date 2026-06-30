# MoonBoard 2024 hold-search

Scrape MoonBoard 2024 hold-set problems into a local SQLite database and search
climbs by hold through a web UI. No Bluetooth, no physical board.

Click holds on a rendered 2024 board to require or exclude them, mark start /
finish holds, filter by grade / angle / benchmark / repeats, and click any match
to light up its full move sequence.

## How it works

- **Scraper** authenticates to MoonBoard's internal app API (OAuth2 password
  grant) and pages through every problem, keeping the 2024 hold set
  (`setupId 21`).
- **SQLite** stores problems, their moves (one row per hold), and the board
  layout — normalized so "climbs using hold X" is a SQL set operation.
- **Flask app** serves a JSON search API and an SVG board front end.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit with your MoonBoard login
```

`.env`:

```
MOONBOARD_USER=your_username
MOONBOARD_PASS=your_password
MOONBOARD_DB=moonboard.db      # optional, defaults to ./moonboard.db
```

## Scrape

```bash
python -m moonboard_search.scraper.sync
```

Walks the API and fills `moonboard.db`. Re-run any time to pick up new problems —
it is idempotent (existing problems are updated, new ones inserted).

## Run the web app

```bash
flask --app moonboard_search.web.app:create_app run
# open http://127.0.0.1:5000
```

## Search API

| Endpoint | Description |
| --- | --- |
| `GET /api/holds` | Board layout (falls back to coords used by climbs). |
| `GET /api/search` | Climbs matching the query (see params below). |
| `GET /api/problem/<id>` | One climb with its full move list. |

`/api/search` query params (all optional, combine freely):

- `holds=A5,F10` — climb must use **all** of these holds
- `exclude=C7,D9` — climb must use **none** of these
- `start=A5` / `end=K18` — start / finish holds must include these
- `grade=6B+` — exact grade
- `angle=25` or `angle=40` — wall angle
- `benchmark=1` — benchmarks only
- `min_repeats=20` — minimum repeat count

## Deploy to Vercel (use it on your phone)

Vercel's filesystem is read-only, so the scraper runs **locally** and the
resulting database is committed and served read-only. Credentials never leave
your machine.

1. **Scrape locally** so `moonboard.db` exists:
   ```bash
   python -m moonboard_search.scraper.sync
   ```
2. **Commit the database** (`.gitignore` already allows `moonboard.db`):
   ```bash
   git add moonboard.db && git commit -m "data: bundle scraped 2024 problems"
   ```
3. **Deploy** (`wsgi.py` is the entrypoint; `vercel.json` is included):
   ```bash
   npm i -g vercel
   vercel        # preview
   vercel --prod # production
   ```
4. **Make it private** — in the Vercel dashboard: Project → Settings →
   Deployment Protection → enable **Vercel Authentication**. Only your Vercel
   account can then open the URL. (Recommended: deploying republishes scraped
   MoonBoard data, so keep it behind auth.)

Re-syncing later = re-run the scraper, commit the updated `moonboard.db`,
`vercel --prod` again.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

All network calls are mocked; the suite needs no MoonBoard account.

## Notes / caveats

- This uses Moon Climbing's **private** API, which their terms of service do not
  authorize. Keep it to personal use, don't hammer the API, and don't
  redistribute the scraped database. Credentials live in a gitignored `.env`.
- The 2024 board identifiers (`setupId 21`, configs `2`→25°, `3`→40°) and the
  endpoint shapes are derived from
  [BoardLib](https://github.com/lemeryfertitta/BoardLib) and
  [moonboard-rs](https://github.com/rroohhh/moonboard-rs). If Moon changes its
  API, the scraper's lenient parsing tolerates added fields, but renamed/removed
  fields may need updating in `scraper/sync.py`.
