# Data model (draft v0)

One SQLite file per family tree (`villa-diodati.db`, `rossi.db`...). Backing up a tree means copying one file.

The model follows the same idea as GEDCOM, the standard genealogy format: people are linked through **families** (a union of up to two partners, plus their children). This makes export to GEDCOM straightforward and handles the hard cases without special code.

## Tables

```sql
-- A person in the tree
CREATE TABLE person (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,        -- "Mary Shelley", as people call them
    birth_name    TEXT,                 -- "Mary Wollstonecraft Godwin" (optional)
    also_known_as TEXT,                 -- other names, comma-separated
    sex           TEXT CHECK (sex IN ('F', 'M', 'U')) DEFAULT 'U',
    notes         TEXT
);

-- A family: a union of up to two partners (either can be unknown)
CREATE TABLE family (
    id          INTEGER PRIMARY KEY,
    partner1_id INTEGER REFERENCES person(id),   -- NULL = unknown
    partner2_id INTEGER REFERENCES person(id),   -- NULL = unknown
    union_type  TEXT CHECK (union_type IN ('marriage', 'partnership', 'unknown')) DEFAULT 'unknown',
    notes       TEXT
);

-- Who is a child of which family, and how
CREATE TABLE family_child (
    family_id   INTEGER NOT NULL REFERENCES family(id),
    child_id    INTEGER NOT NULL REFERENCES person(id),
    relation    TEXT CHECK (relation IN ('birth', 'adopted', 'step', 'unknown')) DEFAULT 'birth',
    PRIMARY KEY (family_id, child_id)
);

-- Anything that happened: birth, death, marriage, a move, a job...
CREATE TABLE event (
    id          INTEGER PRIMARY KEY,
    person_id   INTEGER REFERENCES person(id),   -- individual events
    family_id   INTEGER REFERENCES family(id),   -- union events (marriage, divorce)
    type        TEXT NOT NULL,      -- birth, death, marriage, divorce, residence, occupation, other
    date_text   TEXT,               -- as given: "1797", "30 Aug 1797", "about 1815"
    date_sort   TEXT,               -- normalised by code for sorting and checks: "1797-08-30"
    place       TEXT,
    description TEXT,               -- free text: "moved to Paris after the war"
    source      TEXT                -- where the information comes from: the sentence it was told in
);

-- A relationship we were told about but can't place in the tree yet,
-- e.g. "Claire was Mary's stepsister" while their parents are unknown
CREATE TABLE claim (
    id       INTEGER PRIMARY KEY,
    a_id     INTEGER NOT NULL REFERENCES person(id),
    b_id     INTEGER NOT NULL REFERENCES person(id),
    kind     TEXT NOT NULL,         -- step_sibling, half_sibling, grandchild...
    sentence TEXT
);
```

Dates are stored as written ("about 1815", "nel 1960", "probably 1890"): the code extracts the year only when it needs to compare dates.

## How sentences map to the model

| Sentence | What the code stores |
| --- | --- |
| "Maria is Marco's wife" | a `family` with Maria and Marco as partners, `union_type = marriage` |
| "Giuseppe is their son" | `family_child(that family, Giuseppe, birth)` |
| "Marco is Roberta's brother" (parents unknown) | a `family` with **both partners unknown**, Marco and Roberta as its children. When the parents are added later, the code fills in that family instead of creating a new one |
| "Claire is Mary's stepsister" | Mary and Claire are children of **different** families whose parents later married each other. Step-siblings are derived, never stored. If their parents aren't in the tree yet, the statement is kept as a `claim` |
| "Fanny is Mary's half-sister" | the two families share one parent (Mary Wollstonecraft) |
| "Roberta lived in Padova, then moved to Paris" | two `event` rows of type `residence` |

Siblings, half-siblings, step-siblings, cousins and grandparents are never stored directly: the code **derives** them from families. This way there is only one truth, and it can't contradict itself.

## What the code checks before saving (first list)

- A person has at most one birth family.
- Nobody is their own ancestor.
- A child is born after both birth parents were born, and not long after a parent died (with a tolerance for fathers).
- Death comes after birth.
- A name that matches more than one person is never guessed: the app asks which one.
