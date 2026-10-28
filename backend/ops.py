"""The operation format shared by Gemma, the planner and the tests."""

OP_TYPES = ("person", "union", "child", "siblings", "event", "relation_hint")
EVENT_TYPES = ("birth", "death", "marriage", "divorce", "residence", "occupation", "other")
UNION_TYPES = ("marriage", "partnership", "unknown")
CHILD_RELATIONS = ("birth", "adopted", "step", "unknown")
SIBLING_KINDS = ("full", "half", "step", "unspecified")
HINT_KINDS = ("grandparent", "grandchild", "aunt_uncle", "niece_nephew", "cousin", "in_law", "other")

# Fields each op needs to be usable
REQUIRED = {
    "person": ["name"],
    "union": ["partners"],
    "child": ["child", "parents"],
    "siblings": ["people"],
    "event": ["type"],
    "relation_hint": ["a", "b", "kind"],
}

LIST_FIELDS = ("partners", "parents", "people")
LOWERCASE_FIELDS = ("op", "type", "relation", "kind")


def normalize_op(raw: dict) -> tuple[dict | None, str | None]:
    """Cleans one op: drops empty fields, trims text. Returns (op, problem)."""
    if not isinstance(raw, dict):
        return None, f"not an object: {raw!r}"
    op = {}
    for key, value in raw.items():
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
            if key in LOWERCASE_FIELDS:
                value = value.lower()
            if key == "sex":
                value = value.upper()
        elif isinstance(value, list):
            value = [v.strip() for v in value if isinstance(v, str) and v.strip()]
            if not value:
                continue
        op[key] = value
    kind = op.get("op")
    if kind not in OP_TYPES:
        return None, f"unknown op: {raw!r}"
    for f in REQUIRED[kind]:
        if f not in op:
            return None, f"{kind} without {f}: {raw!r}"
    if kind == "union" and len(op["partners"]) != 2:
        return None, f"union needs two partners: {raw!r}"
    if kind == "event" and "person" not in op and len(op.get("partners", [])) != 2:
        return None, f"event needs a person or two partners: {raw!r}"
    if kind == "siblings" and len(op["people"]) < 2:
        return None, f"siblings needs two people: {raw!r}"
    return op, None


def normalize_ops(raw_ops: list) -> tuple[list[dict], list[str]]:
    ops, problems = [], []
    for raw in raw_ops or []:
        op, problem = normalize_op(raw)
        if op:
            ops.append(op)
        else:
            problems.append(problem)
    return ops, problems
