"""In-memory family tree and the relationships derived from it.

Siblings, half-siblings, step-siblings, grandparents and nieces are never stored:
they are derived here from families (a union of up to two partners plus children).
"""

import re
import sqlite3
from dataclasses import dataclass, field

PARENT_LINKS = ("birth", "adopted")   # links that make someone a parent


@dataclass
class Person:
    id: int
    name: str
    birth_name: str | None = None
    also_known_as: str | None = None
    sex: str = "U"
    notes: str | None = None

    def all_names(self) -> list[str]:
        names = [self.name]
        if self.birth_name:
            names.append(self.birth_name)
        if self.also_known_as:
            names += [n.strip() for n in self.also_known_as.split(",") if n.strip()]
        return names


@dataclass
class Family:
    id: int
    partners: list            # two slots, each a person id or None (unknown)
    union_type: str = "unknown"
    children: dict = field(default_factory=dict)   # child id -> relation
    notes: str | None = None

    def known_partners(self) -> set[int]:
        return {p for p in self.partners if p is not None}


@dataclass
class Event:
    id: int
    type: str
    person_id: int | None = None
    family_id: int | None = None
    date_text: str | None = None
    place: str | None = None
    description: str | None = None
    source: str | None = None


@dataclass
class Claim:
    id: int
    a_id: int
    b_id: int
    kind: str
    sentence: str | None = None


@dataclass
class Tree:
    people: dict = field(default_factory=dict)      # id -> Person
    families: dict = field(default_factory=dict)    # id -> Family
    events: list = field(default_factory=list)
    claims: list = field(default_factory=list)

    # ---------- basic links ----------

    def birth_families(self, pid: int) -> list[Family]:
        return [f for f in self.families.values() if f.children.get(pid) in PARENT_LINKS]

    def parents(self, pid: int) -> set[int]:
        result = set()
        for f in self.birth_families(pid):
            result |= f.known_partners()
        return result

    def children(self, pid: int) -> set[int]:
        result = set()
        for f in self.families.values():
            if pid in f.partners:
                result |= {c for c, rel in f.children.items() if rel in PARENT_LINKS}
        return result

    def ancestors(self, pid: int) -> set[int]:
        seen, todo = set(), list(self.parents(pid))
        while todo:
            p = todo.pop()
            if p not in seen:
                seen.add(p)
                todo += list(self.parents(p))
        return seen

    def partners_of(self, pid: int) -> set[int]:
        result = set()
        for f in self.families.values():
            if pid in f.partners:
                result |= f.known_partners() - {pid}
        return result

    def year(self, pid: int, event_type: str) -> int | None:
        for e in self.events:
            if e.person_id == pid and e.type == event_type:
                return year_of(e.date_text)
        return None

    # ---------- derived relationships ----------

    def sibling_kind(self, a: int, b: int) -> str | None:
        """'full', 'half', 'step' or None, from a's point of view towards b."""
        if a == b:
            return None
        fa = {f.id for f in self.birth_families(a)}
        fb = {f.id for f in self.birth_families(b)}
        if fa & fb:
            return "full"
        if self.parents(a) & self.parents(b):
            return "half"
        for pa in self.parents(a):
            if self.partners_of(pa) & self.parents(b):
                return "step"
        return None

    def relation(self, a: int, b: int) -> tuple[str, str | None] | None:
        """How a is related to b, e.g. ('grandchild', None) or ('niece_nephew', 'step')."""
        if b in self.parents(a):
            return ("child", None)
        if a in self.parents(b):
            return ("parent", None)
        if b in self.partners_of(a):
            return ("partner", None)
        kind = self.sibling_kind(a, b)
        if kind:
            return ("sibling", kind)
        grandparents_a = {g for p in self.parents(a) for g in self.parents(p)}
        if b in grandparents_a:
            return ("grandchild", None)
        grandparents_b = {g for p in self.parents(b) for g in self.parents(p)}
        if a in grandparents_b:
            return ("grandparent", None)
        for p in self.parents(a):
            kind = self.sibling_kind(p, b)
            if kind:
                return ("niece_nephew", None if kind == "full" else kind)
        for p in self.parents(b):
            kind = self.sibling_kind(a, p)
            if kind:
                return ("aunt_uncle", None if kind == "full" else kind)
        return None


def year_of(date_text: str | None) -> int | None:
    """First four-digit year in a free-text date: 'about 1815' -> 1815."""
    if not date_text:
        return None
    m = re.search(r"\b(1\d{3}|20\d{2})\b", str(date_text))
    return int(m.group(1)) if m else None


MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7,
    "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}


def date_parts(date_text: str | None) -> tuple[int | None, int | None, int | None]:
    """(year, month, day), each None when the text doesn't say it.
    '1816-12-30', '30 December 1816' and '30 dicembre 1816' are the same day."""
    if not date_text:
        return (None, None, None)
    text = str(date_text).lower()
    iso = re.search(r"\b(\d{4})-(\d{2})(?:-(\d{2}))?\b", text)
    if iso:
        return (int(iso.group(1)), int(iso.group(2)), int(iso.group(3)) if iso.group(3) else None)
    year = year_of(text)
    month = next((n for word, n in MONTHS.items() if re.search(rf"\b{word}\b", text)), None)
    day = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", re.sub(r"\b\d{4}\b", "", text)) if month else None
    return (year, month, int(day.group(1)) if day else None)


def load_tree(conn: sqlite3.Connection) -> Tree:
    tree = Tree()
    for r in conn.execute("SELECT * FROM person"):
        tree.people[r["id"]] = Person(r["id"], r["name"], r["birth_name"], r["also_known_as"], r["sex"] or "U", r["notes"])
    for r in conn.execute("SELECT * FROM family"):
        tree.families[r["id"]] = Family(r["id"], [r["partner1_id"], r["partner2_id"]], r["union_type"] or "unknown", {}, r["notes"])
    for r in conn.execute("SELECT * FROM family_child"):
        tree.families[r["family_id"]].children[r["child_id"]] = r["relation"]
    for r in conn.execute("SELECT * FROM event"):
        tree.events.append(Event(r["id"], r["type"], r["person_id"], r["family_id"], r["date_text"], r["place"], r["description"], r["source"]))
    for r in conn.execute("SELECT * FROM claim"):
        tree.claims.append(Claim(r["id"], r["a_id"], r["b_id"], r["kind"], r["sentence"]))
    return tree
