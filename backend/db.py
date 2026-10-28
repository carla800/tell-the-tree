"""SQLite storage: one file per family tree."""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS person (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    birth_name    TEXT,
    also_known_as TEXT,
    sex           TEXT CHECK (sex IN ('F', 'M', 'U')) DEFAULT 'U',
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS family (
    id          INTEGER PRIMARY KEY,
    partner1_id INTEGER REFERENCES person(id),
    partner2_id INTEGER REFERENCES person(id),
    union_type  TEXT CHECK (union_type IN ('marriage', 'partnership', 'unknown')) DEFAULT 'unknown',
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS family_child (
    family_id INTEGER NOT NULL REFERENCES family(id) ON DELETE CASCADE,
    child_id  INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    relation  TEXT CHECK (relation IN ('birth', 'adopted', 'step', 'unknown')) DEFAULT 'birth',
    PRIMARY KEY (family_id, child_id)
);

CREATE TABLE IF NOT EXISTS event (
    id          INTEGER PRIMARY KEY,
    person_id   INTEGER REFERENCES person(id) ON DELETE CASCADE,
    family_id   INTEGER REFERENCES family(id) ON DELETE CASCADE,
    type        TEXT NOT NULL,
    date_text   TEXT,
    place       TEXT,
    description TEXT,
    source      TEXT
);

-- Relationships we were told about but can't place in the tree yet
-- (e.g. "Claire was Mary's stepsister" when their parents are unknown)
CREATE TABLE IF NOT EXISTS claim (
    id       INTEGER PRIMARY KEY,
    a_id     INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    b_id     INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    kind     TEXT NOT NULL,
    sentence TEXT
);

-- One picture per person, inside the tree file: the whole tree stays one file you can copy
CREATE TABLE IF NOT EXISTS photo (
    person_id INTEGER PRIMARY KEY REFERENCES person(id) ON DELETE CASCADE,
    mime      TEXT NOT NULL,
    data      BLOB NOT NULL,
    updated   TEXT NOT NULL
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    """Opens (and creates if needed) a tree file."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
