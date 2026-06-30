-- MoonBoard 2024 hold-search schema.
-- Normalized so "climbs using hold X" is a SQL set operation over `moves`.

CREATE TABLE IF NOT EXISTS problems (
    api_id        INTEGER PRIMARY KEY,
    name          TEXT,
    grade         TEXT,
    user_grade    TEXT,
    user_rating   INTEGER,
    is_benchmark  INTEGER NOT NULL DEFAULT 0,
    repeats       INTEGER NOT NULL DEFAULT 0,
    setby         TEXT,
    config_id     INTEGER,   -- moonBoardConfigurationId (2 = 25 deg, 3 = 40 deg)
    angle         INTEGER    -- derived: 25 or 40
);

CREATE TABLE IF NOT EXISTS moves (
    problem_id  INTEGER NOT NULL,
    coord       TEXT NOT NULL,     -- hold coordinate, e.g. "A5"
    is_start    INTEGER NOT NULL DEFAULT 0,
    is_end      INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (problem_id) REFERENCES problems (api_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS holds (
    coord        TEXT PRIMARY KEY,  -- e.g. "A5"
    x            REAL,
    y            REAL,
    hold_number  TEXT,
    description  TEXT
);

CREATE TABLE IF NOT EXISTS sync_meta (
    key    TEXT PRIMARY KEY,
    value  TEXT
);

CREATE INDEX IF NOT EXISTS idx_moves_coord ON moves (coord);
CREATE INDEX IF NOT EXISTS idx_moves_problem ON moves (problem_id);
CREATE INDEX IF NOT EXISTS idx_problems_grade ON problems (grade);
CREATE INDEX IF NOT EXISTS idx_problems_angle ON problems (angle);
