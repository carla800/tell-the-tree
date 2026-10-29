"""GEDCOM 5.5.1: the standard file every genealogy program can open.

Export writes the whole tree (names, birth names, events, sources, couples, children, adoptions)
so that the family history is never locked inside this app. Import reads the same things back.
Photos are not exported: GEDCOM only points to image files, it can't carry them.
"""

import re
from datetime import date

from .messages import Message
from .tree import date_parts

GED_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
EN_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]
PERSON_TAGS = {"birth": "BIRT", "death": "DEAT", "residence": "RESI", "occupation": "OCCU",
               "baptism": "BAPM", "christening": "CHR", "burial": "BURI", "other": "EVEN"}
FAMILY_TAGS = {"marriage": "MARR", "divorce": "DIV", "other": "EVEN"}
PARTICLES = {"de", "di", "da", "del", "della", "dei", "degli", "van", "von", "der", "den", "du", "la", "le", "lo", "dos", "das"}
MAX_BYTES = 15_000_000


class GedcomError(ValueError):
    """A problem with the file, said in the interface's language (see backend/messages.py)."""

    def __init__(self, key: str, **params):
        self.message = Message(key, **params)
        super().__init__(str(self.message))


# ---------- dates ----------

QUALIFIERS = {
    "ABT": r"about|abt\.?|circa|ca\.|c\.|around|intorno al|verso il",
    "BEF": r"before|prima del|prima di",
    "AFT": r"after|dopo il|dopo",
}


def to_ged_date(text: str | None) -> str | None:
    """'30 December 1816', '1816-12-30', '30 dicembre 1816' -> '30 DEC 1816'; 'about 1815' -> 'ABT 1815'.
    A date with other words keeps them: '19 or 20 April 1822' -> 'INT 19 APR 1822 (19 or 20 April 1822)'."""
    if not text or not text.strip():
        return None
    original = text.strip()
    lower = original.lower()
    qualifier = None
    for tag, pattern in QUALIFIERS.items():
        match = re.match(rf"^(?:{pattern})\s+", lower)
        if match:
            qualifier, lower = tag, lower[match.end():]
            break
    year, month, day = date_parts(lower)
    if year is None:
        return f"({original})"
    core = " ".join(x for x in (str(day) if day else None, GED_MONTHS[month - 1] if month else None, str(year)) if x)
    iso = re.fullmatch(r"\d{4}-\d{2}(?:-\d{2})?", lower)
    words = re.fullmatch(r"(?:\d{1,2}(?:st|nd|rd|th)?\s+)?(?:[a-zà-ú]+\s+)?\d{4}", lower)
    if not (iso or (words and (month is not None or not re.search(r"[a-z]", lower)))):
        return f"INT {core} ({original})"
    return f"{qualifier} {core}" if qualifier else core


def from_ged_date(value: str | None) -> str | None:
    """'30 DEC 1816' -> '1816-12-30' (the interface shows it in its language); 'DEC 1816' -> '1816-12';
    'ABT 1815' -> 'about 1815'; 'INT 1816 (spring 1816)' or '(spring 1816)' -> 'spring 1816'."""
    if not value or not value.strip():
        return None
    value = value.strip()
    phrase = re.search(r"\((.*)\)\s*$", value)
    if phrase and (value.startswith("(") or value.upper().startswith("INT ")):
        return phrase.group(1).strip()
    words = {"ABT": "about", "EST": "about", "CAL": "about", "BEF": "before", "AFT": "after"}
    match = re.fullmatch(r"(?:(ABT|EST|CAL|BEF|AFT)\s+)?(?:(\d{1,2})\s+)?(?:([A-Z]{3})\s+)?(\d{4})", value.upper())
    if match and (match.group(3) is None or match.group(3) in GED_MONTHS):
        qualifier, day, month, year = match.groups()
        iso = year + (f"-{GED_MONTHS.index(month) + 1:02d}" if month else "") + (f"-{int(day):02d}" if day and month else "")
        return f"{words[qualifier]} {iso}" if qualifier else iso
    return " ".join(EN_MONTHS[GED_MONTHS.index(t.upper())] if t.upper() in GED_MONTHS
                    else words.get(t.upper(), t) for t in value.split())


# ---------- export ----------

def _ged_name(name: str) -> str:
    """'Mary Shelley' -> 'Mary /Shelley/', 'Ludwig van Beethoven' -> 'Ludwig /van Beethoven/'.
    The slashes tell other programs which part is the surname."""
    words = name.split()
    if len(words) < 2 or "/" in name:
        return name
    start = len(words) - 1
    while start > 1 and words[start - 1].lower() in PARTICLES:
        start -= 1
    return f"{' '.join(words[:start])} /{' '.join(words[start:])}/"


def _split(value: str, size: int = 200) -> list[str]:
    """GEDCOM lines are short: long text continues with CONC, never splitting next to a space."""
    parts = []
    while len(value) > size:
        cut = size
        while cut > 1 and (value[cut - 1] == " " or value[cut] == " "):
            cut -= 1
        parts.append(value[:cut])
        value = value[cut:]
    parts.append(value)
    return parts


class _Writer:
    def __init__(self):
        self.lines = []

    def line(self, level: int, tag: str, value=None):
        if value is None or str(value) == "":
            self.lines.append(f"{level} {tag}")
            return
        text_lines = str(value).replace("\r", "").split("\n")
        for n, text_line in enumerate(text_lines):
            chunks = _split(text_line)
            self.lines.append(f"{level} {tag} {chunks[0]}".rstrip() if n == 0 else f"{level + 1} CONT {chunks[0]}".rstrip())
            for chunk in chunks[1:]:
                self.lines.append(f"{level + 1} CONC {chunk}")

    def event(self, level: int, tag: str, e):
        value = e["description"] if tag == "OCCU" else None
        self.line(level, tag, value)
        if tag == "EVEN":
            self.line(level + 1, "TYPE", e["description"] or "Event")
        if e["date_text"]:
            self.line(level + 1, "DATE", to_ged_date(e["date_text"]))
        if e["place"]:
            self.line(level + 1, "PLAC", e["place"])
        if e["description"] and tag not in ("OCCU", "EVEN"):
            self.line(level + 1, "NOTE", e["description"])
        if e["source"]:
            self.line(level + 1, "SOUR", e["source"])


def export(conn, app_name: str = "Family tree") -> bytes:
    people = conn.execute("SELECT * FROM person ORDER BY id").fetchall()
    sex = {p["id"]: p["sex"] for p in people}
    names = {p["id"]: p["name"] for p in people}
    families = conn.execute("SELECT * FROM family ORDER BY id").fetchall()
    children = {}
    for r in conn.execute("SELECT * FROM family_child ORDER BY family_id, child_id"):
        children.setdefault(r["family_id"], []).append((r["child_id"], r["relation"]))

    w = _Writer()
    w.line(0, "HEAD")
    w.line(1, "SOUR", "FAMILY_TREE_KIT")
    w.line(2, "NAME", app_name)
    w.line(1, "DATE", date.today().strftime("%d %b %Y").upper())
    w.line(1, "SUBM", "@U1@")
    w.line(1, "GEDC")
    w.line(2, "VERS", "5.5.1")
    w.line(2, "FORM", "LINEAGE-LINKED")
    w.line(1, "CHAR", "UTF-8")
    w.line(0, "@U1@ SUBM")
    w.line(1, "NAME", app_name)

    for p in people:
        pid = p["id"]
        w.line(0, f"@I{pid}@ INDI")
        w.line(1, "NAME", _ged_name(p["name"]))
        if p["birth_name"] and p["birth_name"] != p["name"]:
            w.line(1, "NAME", _ged_name(p["birth_name"]))
            w.line(2, "TYPE", "birth")
        if p["also_known_as"]:
            w.line(1, "NAME", p["also_known_as"])
            w.line(2, "TYPE", "aka")
        w.line(1, "SEX", p["sex"] if p["sex"] in ("M", "F") else "U")
        for e in conn.execute("SELECT * FROM event WHERE person_id=? ORDER BY id", (pid,)):
            w.event(1, PERSON_TAGS.get(e["type"], "EVEN"), e)
        for f in families:
            if pid in (f["partner1_id"], f["partner2_id"]):
                w.line(1, "FAMS", f"@F{f['id']}@")
        for f in families:
            for child, relation in children.get(f["id"], []):
                if child == pid:
                    w.line(1, "FAMC", f"@F{f['id']}@")
                    if relation == "adopted":
                        w.line(2, "PEDI", "adopted")
        if p["notes"]:
            w.line(1, "NOTE", p["notes"])
        for c in conn.execute("SELECT * FROM claim WHERE a_id=? ORDER BY id", (pid,)):
            # relationships the tree can't place yet travel as notes
            w.line(1, "NOTE", f"{c['kind'].replace('_', ' ')} of {names.get(c['b_id'], '?')} (not placed in the tree yet)")

    for f in families:
        w.line(0, f"@F{f['id']}@ FAM")
        partners = [x for x in (f["partner1_id"], f["partner2_id"]) if x is not None]
        # GEDCOM 5.5.1 has a husband and a wife: put each partner in the right one when we know their sex
        if len(partners) == 2 and sex[partners[0]] == "F" and sex[partners[1]] != "F":
            partners.reverse()
        elif len(partners) == 1 and sex[partners[0]] == "F":
            partners = [None, partners[0]]
        for tag, pid in zip(("HUSB", "WIFE"), partners):
            if pid is not None:
                w.line(1, tag, f"@I{pid}@")
        for child, relation in children.get(f["id"], []):
            w.line(1, "CHIL", f"@I{child}@")
            if relation in ("adopted", "step"):
                w.line(2, "_FREL", relation.capitalize())
                w.line(2, "_MREL", relation.capitalize())
        events = conn.execute("SELECT * FROM event WHERE family_id=? ORDER BY id", (f["id"],)).fetchall()
        for e in events:
            w.event(1, FAMILY_TAGS.get(e["type"], "EVEN"), e)
        if f["union_type"] == "marriage" and not any(e["type"] == "marriage" for e in events):
            w.line(1, "MARR", "Y")
        if f["union_type"] == "partnership":
            w.line(1, "_UNION", "partnership")
    w.line(0, "TRLR")
    return ("\n".join(w.lines) + "\n").encode("utf-8")


# ---------- import ----------

LINE = re.compile(r"^(\d+)\s+(?:(@[^@\s]+@)\s+)?(\S+)(?:\s(.*))?$")


def _decode(raw: bytes) -> str:
    if len(raw) > MAX_BYTES:
        raise GedcomError("gedcom_too_big")
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise GedcomError("gedcom_encoding")


def _records(text: str) -> list[dict]:
    records, stack = [], []
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        match = LINE.match(line)
        if not match:
            raise GedcomError("gedcom_bad_line", line=number)
        level, pointer, tag, value = match.groups()
        level = int(level)
        node = {"id": pointer, "tag": tag.upper(), "value": value or "", "children": []}
        if level == 0:
            records.append(node)
            stack = [node]
        else:
            if not stack or level > len(stack):
                raise GedcomError("gedcom_bad_level", line=number)
            stack = stack[:level]
            stack[-1]["children"].append(node)
            stack.append(node)
    return records


def _text(node) -> str:
    """A value with its CONT (new line) and CONC (same line) continuations."""
    value = node["value"]
    for child in node["children"]:
        if child["tag"] == "CONT":
            value += "\n" + child["value"]
        elif child["tag"] == "CONC":
            value += child["value"]
    return value


def _first(node, tag):
    return next((n for n in node["children"] if n["tag"] == tag), None)


def _plain_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("/", " ")).strip()


def parse(raw: bytes) -> dict:
    records = _records(_decode(raw))
    notes = {r["id"]: _text(r) for r in records if r["tag"] == "NOTE" and r["id"]}
    sources = {r["id"]: _text(_first(r, "TITL")) if _first(r, "TITL") else r["id"] for r in records if r["tag"] == "SOUR" and r["id"]}

    def note_text(node):
        value = _text(node)
        return notes.get(value.strip(), "") if value.strip().startswith("@") else value

    def event(node, kind):
        date_node, place_node, source_node = _first(node, "DATE"), _first(node, "PLAC"), _first(node, "SOUR")
        description = None
        if node["tag"] == "OCCU":
            description = _text(node) or None
        elif node["tag"] == "EVEN":
            type_node = _first(node, "TYPE")
            description = (_text(type_node) if type_node else _text(node)) or None
        else:
            note = _first(node, "NOTE")
            description = note_text(note) if note else None
        source = None
        if source_node:
            value = _text(source_node).strip()
            source = sources.get(value, value) if value.startswith("@") else value
        return {"type": kind, "date_text": from_ged_date(_text(date_node)) if date_node else None,
                "place": _text(place_node) if place_node else None, "description": description, "source": source}

    people, families, adopted = {}, {}, set()
    person_kinds = {tag: kind for kind, tag in PERSON_TAGS.items()}
    family_kinds = {"MARR": "marriage", "DIV": "divorce", "EVEN": "other"}
    for r in records:
        if r["tag"] == "INDI" and r["id"]:
            person = {"name": None, "birth_name": None, "also_known_as": None, "sex": "U", "notes": [], "events": []}
            for node in r["children"]:
                if node["tag"] == "NAME":
                    kind = (_text(_first(node, "TYPE")) if _first(node, "TYPE") else "").lower()
                    value = _plain_name(_text(node))
                    if kind in ("birth", "maiden") and value:
                        person["birth_name"] = value
                    elif kind == "aka" and value:
                        person["also_known_as"] = value
                    elif not person["name"] and value:
                        person["name"] = value
                elif node["tag"] == "SEX":
                    person["sex"] = node["value"].strip().upper() if node["value"].strip().upper() in ("M", "F") else "U"
                elif node["tag"] == "NOTE":
                    text = note_text(node)
                    if text:
                        person["notes"].append(text)
                elif node["tag"] in person_kinds:
                    person["events"].append(event(node, person_kinds[node["tag"]]))
                elif node["tag"] == "FAMC" and _first(node, "PEDI") and _first(node, "PEDI")["value"].lower() == "adopted":
                    adopted.add((node["value"].strip(), r["id"]))
            person["name"] = person["name"] or person["birth_name"] or "?"
            people[r["id"]] = person
        elif r["tag"] == "FAM" and r["id"]:
            family = {"partners": [], "children": [], "events": [], "union_type": "unknown"}
            for node in r["children"]:
                if node["tag"] in ("HUSB", "WIFE"):
                    family["partners"].append(node["value"].strip())
                elif node["tag"] == "CHIL":
                    relations = {(_first(node, t) or {}).get("value", "").lower() for t in ("_FREL", "_MREL")}
                    relation = "adopted" if "adopted" in relations else "step" if "step" in relations else "birth"
                    family["children"].append((node["value"].strip(), relation))
                elif node["tag"] in family_kinds:
                    if node["tag"] == "MARR":
                        family["union_type"] = "marriage"
                    if node["tag"] != "MARR" or node["children"]:      # "1 MARR Y" alone just says they married
                        family["events"].append(event(node, family_kinds[node["tag"]]))
                elif node["tag"] == "_UNION" and node["value"].strip() in ("partnership", "marriage"):
                    family["union_type"] = node["value"].strip()
            families[r["id"]] = family
    for family_id, child in adopted:
        if family_id in families:
            families[family_id]["children"] = [(c, "adopted" if c == child else rel) for c, rel in families[family_id]["children"]]
    if not people:
        raise GedcomError("gedcom_no_people")
    return {"people": people, "families": families}


def preview(raw: bytes) -> dict:
    data = parse(raw)
    return {"people": len(data["people"]), "families": len(data["families"]),
            "sample": [p["name"] for p in list(data["people"].values())[:8]]}


def import_into(conn, raw: bytes) -> dict:
    data = parse(raw)
    ids = {}
    for key, p in data["people"].items():
        cur = conn.execute("INSERT INTO person (name, birth_name, also_known_as, sex, notes) VALUES (?, ?, ?, ?, ?)",
                           (p["name"], p["birth_name"], p["also_known_as"], p["sex"], "\n".join(p["notes"]) or None))
        ids[key] = cur.lastrowid
        for e in p["events"]:
            conn.execute("INSERT INTO event (person_id, type, date_text, place, description, source) VALUES (?, ?, ?, ?, ?, ?)",
                         (ids[key], e["type"], e["date_text"], e["place"], e["description"], e["source"] or "GEDCOM import"))
    count = 0
    for f in data["families"].values():
        partners = [ids[x] for x in f["partners"] if x in ids][:2]
        kids = [(ids[c], rel) for c, rel in f["children"] if c in ids and ids[c] not in partners]
        if not partners and not kids:
            continue
        partners += [None] * (2 - len(partners))
        cur = conn.execute("INSERT INTO family (partner1_id, partner2_id, union_type) VALUES (?, ?, ?)",
                           (partners[0], partners[1], f["union_type"]))
        count += 1
        for child, relation in dict(kids).items():
            conn.execute("INSERT INTO family_child (family_id, child_id, relation) VALUES (?, ?, ?)", (cur.lastrowid, child, relation))
        for e in f["events"]:
            conn.execute("INSERT INTO event (family_id, type, date_text, place, description, source) VALUES (?, ?, ?, ?, ?, ?)",
                         (cur.lastrowid, e["type"], e["date_text"], e["place"], e["description"], e["source"] or "GEDCOM import"))
    return {"people": len(ids), "families": count}
