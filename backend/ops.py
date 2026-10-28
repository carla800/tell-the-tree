"""Operation formats.

Two formats:
  - Gemma's format (what the model writes): person, relation, event.
    `relation` copies the relation word as written: {"person": "Fanny", "word": "half-sister", "of": ["Mary"]}.
  - The tree format (what the planner understands): person, union, child, siblings, event, relation_hint.
    backend/words.py turns the first into the second.
"""

MODEL_OP_TYPES = ("person", "relation", "event")
OP_TYPES = ("person", "union", "child", "siblings", "event", "relation_hint")
EVENT_TYPES = ("birth", "death", "marriage", "divorce", "residence", "occupation", "other")

# Fields each op needs to be usable
MODEL_REQUIRED = {
    "person": ["name"],
    "relation": ["person", "word", "of"],
    "event": ["type"],
}
REQUIRED = {
    "person": ["name"],
    "union": ["partners"],
    "child": ["child", "parents"],
    "siblings": ["people"],
    "event": ["type"],
    "relation_hint": ["a", "b", "kind"],
}

LOWERCASE_FIELDS = ("op", "type", "relation", "kind")


def _clean(raw: dict) -> dict:
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
    if op.get("shared_parent") == "unknown":
        del op["shared_parent"]
    return op


def normalize_op(raw: dict, types=OP_TYPES, required=REQUIRED) -> tuple[dict | None, str | None]:
    """Cleans one op: drops empty fields, trims text. Returns (op, problem)."""
    if not isinstance(raw, dict):
        return None, f"not an object: {raw!r}"
    op = _clean(raw)
    kind = op.get("op")
    if kind not in types:
        return None, f"unknown op: {raw!r}"
    for f in required[kind]:
        if f not in op:
            return None, f"{kind} without {f}: {raw!r}"
    if kind == "union" and len(op["partners"]) != 2:
        return None, f"union needs two partners: {raw!r}"
    if kind == "event" and "person" not in op and len(op.get("partners", [])) != 2:
        return None, f"event needs a person or two partners: {raw!r}"
    if kind == "siblings" and len(op["people"]) < 2:
        return None, f"siblings needs two people: {raw!r}"
    if kind == "relation" and op["person"].casefold() in (o.casefold() for o in op["of"]):
        return None, f"relation of a person with themselves: {raw!r}"
    return op, None


def normalize_ops(raw_ops: list, types=OP_TYPES, required=REQUIRED) -> tuple[list[dict], list[str]]:
    ops, problems = [], []
    for raw in raw_ops or []:
        op, problem = normalize_op(raw, types, required)
        if op:
            ops.append(op)
        else:
            problems.append(problem)
    return ops, problems


def normalize_model_ops(raw_ops: list) -> tuple[list[dict], list[str]]:
    return normalize_ops(raw_ops, MODEL_OP_TYPES, MODEL_REQUIRED)
