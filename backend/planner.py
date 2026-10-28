"""Turns operations into a checked preview, and saves it only when confirmed.

Gemma proposes operations; this module decides:
  - who each name refers to (and asks when a name is ambiguous),
  - whether the result is possible (no one is their own ancestor, dates make sense),
  - what exactly would change in the tree.
"""

import copy
import re
from dataclasses import dataclass, field

from .ops import EVENT_TYPES
from .tree import PARENT_LINKS, Claim, Event, Family, Person, Tree, date_parts, year_of


@dataclass
class Plan:
    status: str = "save"                  # save | ask | reject
    changes: list = field(default_factory=list)
    summary: list = field(default_factory=list)    # what would be added, in plain words
    known: list = field(default_factory=list)      # facts already in the tree
    questions: list = field(default_factory=list)  # {name, candidates}
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[\w']+", text.casefold()))


class Planner:
    def __init__(self, tree: Tree, choices: dict | None = None):
        self.tree = copy.deepcopy(tree)          # never touch the real tree while planning
        self.choices = {k.casefold(): v for k, v in (choices or {}).items()}
        self.plan = Plan()
        self._next_tmp = -1
        self._asked = set()

    # ---------- helpers ----------

    def _tmp_id(self) -> int:
        self._next_tmp -= 1
        return self._next_tmp

    def name(self, pid) -> str:
        return self.tree.people[pid].name

    def resolve(self, name: str) -> int | None:
        """Person id for a name: existing, newly created, or None if we must ask."""
        key = name.casefold()
        if key in self.choices:
            choice = self.choices[key]
            if choice == "new":
                return self._new_person(name)
            return choice
        people = list(self.tree.people.values())
        exact = [p for p in people if any(n.casefold() == key for n in p.all_names())]
        if len(exact) == 1:
            return exact[0].id
        candidates = exact or [p for p in people if any(_tokens(name) <= _tokens(n) for n in p.all_names())]
        if len(candidates) == 1:
            return candidates[0].id
        if len(candidates) > 1:
            if key not in self._asked:
                self._asked.add(key)
                self.plan.questions.append({
                    "kind": "person",
                    "name": name,
                    "candidates": [{"id": p.id, "name": p.name, "born": self.tree.year(p.id, "birth")} for p in candidates],
                })
            return None
        return self._new_person(name)

    def _new_person(self, name: str) -> int:
        pid = self._tmp_id()
        self.tree.people[pid] = Person(pid, name)
        self.plan.changes.append({"action": "add_person", "tmp": pid, "name": name, "sex": "U"})
        self.plan.summary.append(f"New person: {name}")
        return pid

    def _set_person(self, pid: int, **fields):
        person = self.tree.people[pid]
        for k, v in fields.items():
            setattr(person, k, v)
        if pid < 0:   # still in this plan: update the pending add_person
            for c in self.plan.changes:
                if c["action"] == "add_person" and c["tmp"] == pid:
                    c.update(fields)
        else:
            self.plan.changes.append({"action": "update_person", "id": pid, "fields": fields})

    def _find_union(self, a: int, b: int) -> Family | None:
        for f in self.tree.families.values():
            if set(f.partners) == {a, b}:
                return f
        return None

    def _new_family(self, partners: list, union_type: str = "unknown") -> Family:
        partners = (list(partners) + [None, None])[:2]
        fid = self._tmp_id()
        fam = Family(fid, partners, union_type, {})
        self.tree.families[fid] = fam
        self.plan.changes.append({"action": "add_family", "tmp": fid, "partners": partners, "union_type": union_type})
        return fam

    def _add_child(self, fam: Family, child: int, relation: str):
        fam.children[child] = relation
        self.plan.changes.append({"action": "add_child", "family": fam.id, "child": child, "relation": relation})

    def _union(self, a: int, b: int, union_type: str = "unknown") -> Family:
        fam = self._find_union(a, b)
        if fam is None:
            fam = self._new_family([a, b], union_type)
            label = {"marriage": "married", "partnership": "partners"}.get(union_type, "a couple")
            self.plan.summary.append(f"{self.name(a)} and {self.name(b)}: {label}")
        elif union_type != "unknown" and fam.union_type == "unknown":
            fam.union_type = union_type
            self.plan.changes.append({"action": "update_family", "id": fam.id, "fields": {"union_type": union_type}})
            self.plan.summary.append(f"{self.name(a)} and {self.name(b)}: {union_type}")
        elif fam.id > 0:   # existed before this sentence
            self.plan.known.append(f"{self.name(a)} and {self.name(b)} are already a couple")
        return fam

    # ---------- operations ----------

    def op_person(self, op):
        pid = self.resolve(op["name"])
        if pid is None:
            return
        person = self.tree.people[pid]
        updates = {}
        if op.get("sex") in ("F", "M") and person.sex == "U":
            updates["sex"] = op["sex"]
        if op.get("birth_name") and not person.birth_name:
            updates["birth_name"] = op["birth_name"]
        if updates:
            self._set_person(pid, **updates)

    def op_union(self, op):
        a, b = (self.resolve(n) for n in op["partners"])
        if a is None or b is None:
            return
        if a == b:
            self.plan.errors.append(f"{self.name(a)} can't be in a couple with themselves.")
            return
        union_type = op.get("type") if op.get("type") in ("marriage", "partnership") else "unknown"
        self._union(a, b, union_type)

    def op_child(self, op):
        child = self.resolve(op["child"])
        parents = [self.resolve(n) for n in op["parents"][:2]]
        if child is None or None in parents:
            return
        relation = op.get("relation") if op.get("relation") in ("birth", "adopted", "step", "unknown") else "birth"
        for p in parents:
            if p == child:
                self.plan.errors.append(f"{self.name(p)} can't be their own parent.")
                return
            if child in self.tree.ancestors(p) or child == p:
                self.plan.errors.append(
                    f"{self.name(child)} is already an ancestor of {self.name(p)}: "
                    f"{self.name(p)} can't also be {self.name(child)}'s parent."
                )
                return
        if relation in PARENT_LINKS and not self._dates_ok_for_parents(child, parents):
            return
        if relation == "step":
            fam = self._family_for_parents(parents)
            self._add_child(fam, child, "step")
            self.plan.summary.append(f"{self.name(child)}: stepchild of {' and '.join(self.name(p) for p in parents)}")
            return

        wanted = set(parents)
        existing = self.tree.birth_families(child)
        if existing:
            fam = existing[0]
            known = fam.known_partners()
            if wanted <= known:
                self.plan.known.append(f"{self.name(child)}'s parents are already in the tree")
                return
            free = [i for i, p in enumerate(fam.partners) if p is None]
            missing = list(wanted - known)
            if known <= wanted and len(missing) <= len(free):
                for slot, p in zip(free, missing):
                    fam.partners[slot] = p
                self.plan.changes.append({"action": "update_family", "id": fam.id, "fields": {"partners": list(fam.partners)}})
                self.plan.summary.append(f"{self.name(child)}: {' and '.join(self.name(p) for p in missing)} added as parent")
                return
            names = " and ".join(self.name(p) for p in known) or "other parents"
            self.plan.errors.append(f"{self.name(child)} already has {names} as parents in the tree.")
            return

        fam = self._family_for_parents(parents)
        self._add_child(fam, child, relation)
        word = "adopted child" if relation == "adopted" else "child"
        self.plan.summary.append(f"{self.name(child)}: {word} of {' and '.join(self.name(p) for p in parents)}")

    def _family_for_parents(self, parents: list) -> Family:
        if len(parents) == 2:
            return self._find_union(*parents) or self._new_family(parents)
        for f in self.tree.families.values():
            if set(f.partners) == {parents[0], None}:
                return f
        return self._new_family(parents)

    def _dates_ok_for_parents(self, child: int, parents: list) -> bool:
        born = self.tree.year(child, "birth")
        if born is None:
            return True
        for p in parents:
            p_born = self.tree.year(p, "birth")
            if p_born is not None and p_born >= born:
                self.plan.errors.append(
                    f"{self.name(p)} (born {p_born}) can't be the parent of {self.name(child)} (born {born})."
                )
                return False
            if p_born is not None and born - p_born < 12:
                self.plan.warnings.append(f"{self.name(p)} would have been {born - p_born} at {self.name(child)}'s birth.")
            p_died = self.tree.year(p, "death")
            if p_died is not None and p_died < born - 1:
                self.plan.errors.append(
                    f"{self.name(p)} died in {p_died}, before {self.name(child)} was born ({born})."
                )
                return False
        return True

    def op_siblings(self, op):
        people = [self.resolve(n) for n in op["people"]]
        if None in people:
            return
        kind = op.get("kind") if op.get("kind") in ("full", "half", "step") else "unspecified"
        first = people[0]
        for other in people[1:]:
            if other == first:
                continue
            current = self.tree.sibling_kind(first, other)
            pair = f"{self.name(first)} and {self.name(other)}"
            if current:
                if kind in ("unspecified", current):
                    self.plan.known.append(f"{pair} are already {current} siblings in the tree")
                    self._check_shared_parent(first, other, op.get("shared_parent"))
                else:
                    self.plan.errors.append(f"The tree says {pair} are {current} siblings, not {kind}.")
                continue
            if kind in ("full", "unspecified"):
                fa, fb = self.tree.birth_families(first), self.tree.birth_families(other)
                if fa and not fb:
                    self._add_child(fa[0], other, "birth")
                elif fb and not fa:
                    self._add_child(fb[0], first, "birth")
                elif not fa and not fb:
                    fam = self._new_family([])
                    self._add_child(fam, first, "birth")
                    self._add_child(fam, other, "birth")
                else:
                    self._claim(first, other, f"{kind}_sibling")
                    continue
                self.plan.summary.append(f"{pair}: siblings")
            else:
                self._claim(first, other, f"{kind}_sibling")

    def _check_shared_parent(self, a: int, b: int, role: str | None):
        if role not in ("mother", "father"):
            return
        sex = "F" if role == "mother" else "M"
        shared = self.tree.parents(a) & self.tree.parents(b)
        if shared and not any(self.tree.people[p].sex in (sex, "U") for p in shared):
            self.plan.errors.append(f"{self.name(a)} and {self.name(b)} don't share a {role} in the tree.")

    def _claim(self, a: int, b: int, kind: str):
        self.tree.claims.append(Claim(self._tmp_id(), a, b, kind))
        self.plan.changes.append({"action": "add_claim", "a": a, "b": b, "kind": kind})
        self.plan.summary.append(
            f"{self.name(a)} and {self.name(b)}: {kind.replace('_', ' ')} (saved as a note until their parents are in the tree)"
        )

    def op_event(self, op):
        etype = op["type"] if op["type"] in EVENT_TYPES else "other"
        if "person" in op:
            pid = self.resolve(op["person"])
            if pid is None:
                return
            if not self._event_dates_ok(pid, etype, year_of(op.get("date"))):
                return
            target = {"person": pid}
            who = self.name(pid)
        else:
            a, b = (self.resolve(n) for n in op["partners"][:2])
            if a is None or b is None:
                return
            fam = self._union(a, b, "marriage" if etype == "marriage" else "unknown")
            target = {"family": fam.id}
            who = f"{self.name(a)} and {self.name(b)}"
        details = ", ".join(x for x in (op.get("date"), op.get("place"), op.get("description")) if x)
        if self._event_known(target, etype, op):
            self.plan.known.append(f"{who}: {etype}" + (f" ({details})" if details else "") + " is already in the tree")
            return
        event = {
            "action": "add_event", **target, "type": etype,
            "date_text": op.get("date"), "place": op.get("place"), "description": op.get("description"),
        }
        self.tree.events.append(Event(self._tmp_id(), etype, target.get("person"), target.get("family"),
                                      op.get("date"), op.get("place"), op.get("description")))
        self.plan.changes.append(event)
        self.plan.summary.append(f"{who}: {etype}" + (f" ({details})" if details else ""))

    def _event_known(self, target: dict, etype: str, op: dict) -> bool:
        """True when an event already in the tree says everything this one says
        (same day written differently, or less detail). New details are always added."""
        new = date_parts(op.get("date"))
        for e in self.tree.events:
            if e.type != etype or e.person_id != target.get("person") or e.family_id != target.get("family"):
                continue
            old = date_parts(e.date_text)
            if any(n is not None and n != o for n, o in zip(new, old)):
                continue
            if all(_contains(getattr(e, f), op.get(f)) for f in ("place", "description")):
                return True
        return False

    def _event_dates_ok(self, pid: int, etype: str, year: int | None) -> bool:
        if year is None:
            return True
        name = self.name(pid)
        born, died = self.tree.year(pid, "birth"), self.tree.year(pid, "death")
        if etype == "birth":
            if born is not None and born != year:
                self.plan.errors.append(f"{name} is already recorded as born in {born}, not {year}.")
                return False
            if died is not None and year > died:
                self.plan.errors.append(f"{name} died in {died}, so can't be born in {year}.")
                return False
            for c in self.tree.children(pid):
                cb = self.tree.year(c, "birth")
                if cb is not None and cb <= year:
                    self.plan.errors.append(f"{name} can't be born in {year}: their child {self.name(c)} was born in {cb}.")
                    return False
        elif etype == "death":
            if died is not None and died != year:
                self.plan.errors.append(f"{name} is already recorded as dead in {died}, not {year}.")
                return False
            if born is not None and year < born:
                self.plan.errors.append(f"{name} was born in {born}, so can't die in {year}.")
                return False
        elif born is not None and year < born:
            self.plan.errors.append(f"{name} was born in {born}: nothing can happen to them in {year}.")
            return False
        return True

    def op_relation_hint(self, op):
        a, b = self.resolve(op["a"]), self.resolve(op["b"])
        if a is None or b is None:
            return
        current = self.tree.relation(a, b)
        kind = op["kind"]
        label = kind.replace("_", "/")
        if current and current[0] == kind:
            self.plan.known.append(f"{self.name(a)} is already {self.name(b)}'s {label} in the tree")
        elif current:
            self.plan.errors.append(
                f"The tree says {self.name(a)} is {self.name(b)}'s {current[0].replace('_', '/')}, not {label}."
            )
        else:
            self._claim(a, b, kind)

    def op_ambiguous(self, op):
        """A word with more than one meaning ("nipote", "sorellastra").

        1. The user already chose a meaning: use it.
        2. The tree already explains exactly one meaning: use it, nothing to ask.
        3. Otherwise: ask.
        """
        options = op["options"]
        chosen = self.choices.get(f"meaning:{op['word']}".casefold())
        if chosen is not None:
            match = [o for o in options if o["label"] == chosen]
            if match:
                self._run_ops(match[0]["ops"])
                return
        names = [op["person"], *op["of"]]
        before = len(self.plan.questions)
        ids = [self.resolve(n) for n in names]
        if None in ids:
            return
        already_true = []
        for option in options:
            trial = Planner(self.tree, self.choices)
            trial._next_tmp = self._next_tmp
            trial._run_ops(option["ops"])
            if not trial.plan.errors and not trial.plan.changes:
                already_true.append(option)
        if len(already_true) == 1:
            self._run_ops(already_true[0]["ops"])
            self.plan.known.append(f'"{op["word"]}" read as {already_true[0]["label"]}, as the tree already shows')
            return
        if len(self.plan.questions) == before:
            self.plan.questions.append({
                "kind": "meaning",
                "word": op["word"],
                "person": op["person"],
                "of": op["of"],
                "options": [o["label"] for o in options],
            })

    def _run_ops(self, ops: list[dict]):
        # people first, so that sex and birth names are known before the checks
        for op in sorted(ops, key=lambda o: o["op"] != "person"):
            getattr(self, f"op_{op['op']}")(op)

    def run(self, ops: list[dict]) -> Plan:
        self._run_ops(ops)
        if self.plan.errors:
            self.plan.status = "reject"
        elif self.plan.questions:
            self.plan.status = "ask"
        return self.plan


def _contains(known: str | None, new: str | None) -> bool:
    return not new or (known is not None and new.strip().lower() in known.lower())


def make_plan(tree: Tree, ops: list[dict], choices: dict | None = None) -> Plan:
    return Planner(tree, choices).run(ops)


def apply_plan(conn, plan: Plan, sentence: str | None = None) -> dict:
    """Writes a confirmed plan. Temporary (negative) ids become real ids."""
    if plan.status != "save":
        raise ValueError(f"Can't save a plan with status '{plan.status}'.")
    ids = {}
    real = lambda x: ids.get(x, x) if x is not None else None  # noqa: E731
    source = f'From: "{sentence}"' if sentence else None
    with conn:
        for c in plan.changes:
            a = c["action"]
            if a == "add_person":
                cur = conn.execute("INSERT INTO person (name, sex, birth_name) VALUES (?, ?, ?)",
                                   (c["name"], c.get("sex", "U"), c.get("birth_name")))
                ids[c["tmp"]] = cur.lastrowid
            elif a == "update_person":
                for k, v in c["fields"].items():
                    conn.execute(f"UPDATE person SET {k} = ? WHERE id = ?", (v, real(c["id"])))
            elif a == "add_family":
                p1, p2 = (real(p) for p in c["partners"])
                cur = conn.execute("INSERT INTO family (partner1_id, partner2_id, union_type) VALUES (?, ?, ?)",
                                   (p1, p2, c["union_type"]))
                ids[c["tmp"]] = cur.lastrowid
            elif a == "update_family":
                fields = c["fields"]
                if "union_type" in fields:
                    conn.execute("UPDATE family SET union_type = ? WHERE id = ?", (fields["union_type"], real(c["id"])))
                if "partners" in fields:
                    p1, p2 = (real(p) for p in fields["partners"])
                    conn.execute("UPDATE family SET partner1_id = ?, partner2_id = ? WHERE id = ?", (p1, p2, real(c["id"])))
            elif a == "add_child":
                conn.execute("INSERT OR REPLACE INTO family_child (family_id, child_id, relation) VALUES (?, ?, ?)",
                             (real(c["family"]), real(c["child"]), c["relation"]))
            elif a == "add_event":
                conn.execute(
                    "INSERT INTO event (person_id, family_id, type, date_text, place, description, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (real(c.get("person")), real(c.get("family")), c["type"], c["date_text"], c["place"], c["description"], source),
                )
            elif a == "add_claim":
                conn.execute("INSERT INTO claim (a_id, b_id, kind, sentence) VALUES (?, ?, ?, ?)",
                             (real(c["a"]), real(c["b"]), c["kind"], sentence))
    return ids
