"""Builds a tree file from a YAML description (used for the Villa Diodati demo).

    python -m backend.seed data/villa-diodati.yaml trees/villa-diodati.db
"""

import sys
from pathlib import Path

import yaml

from .db import connect


def seed(yaml_path: str | Path, db_path: str | Path, include_optional: bool = True):
    data = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = connect(db_path)
    ids = {}

    for p in data["people"]:
        if p.get("optional") and not include_optional:
            continue
        cur = conn.execute(
            "INSERT INTO person (name, birth_name, also_known_as, sex, notes) VALUES (?, ?, ?, ?, ?)",
            (p["name"], p.get("birth_name"), p.get("also_known_as"), p.get("sex", "U"), p.get("notes")),
        )
        ids[p["id"]] = cur.lastrowid
        for kind in ("birth", "death"):
            if kind in p:
                e = p[kind]
                conn.execute(
                    "INSERT INTO event (person_id, type, date_text, place, description, source) VALUES (?, ?, ?, ?, ?, ?)",
                    (ids[p["id"]], kind, e.get("date"), e.get("place"), e.get("description"), p.get("source")),
                )

    for f in data["families"]:
        p1, p2 = (ids.get(x) if x else None for x in f["partners"])
        cur = conn.execute(
            "INSERT INTO family (partner1_id, partner2_id, union_type, notes) VALUES (?, ?, ?, ?)",
            (p1, p2, f.get("union", "unknown"), f.get("notes")),
        )
        fid = cur.lastrowid
        for c in f.get("children", []):
            if c["id"] in ids:
                conn.execute(
                    "INSERT INTO family_child (family_id, child_id, relation) VALUES (?, ?, ?)",
                    (fid, ids[c["id"]], c.get("relation", "birth")),
                )
        if "marriage" in f:
            m = f["marriage"]
            conn.execute(
                "INSERT INTO event (family_id, type, date_text, place) VALUES (?, 'marriage', ?, ?)",
                (fid, m.get("date"), m.get("place")),
            )

    conn.commit()
    return conn, ids


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "data/villa-diodati.yaml"
    dst = sys.argv[2] if len(sys.argv) > 2 else "trees/villa-diodati.db"
    conn, ids = seed(src, dst)
    print(f"Created {dst}: {len(ids)} people")
