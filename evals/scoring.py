"""Scoring: does Gemma's answer contain the expected operations?"""


def _norm(value):
    if isinstance(value, list):
        return sorted(str(v).casefold().strip() for v in value)
    return str(value).casefold().strip()


def op_matches(expected: dict, actual: dict) -> bool:
    """Every field we expect must be in the answer with the same value (case and order ignored)."""
    return all(key in actual and _norm(actual[key]) == _norm(value) for key, value in expected.items())


def score_ops(expected_ops: list[dict], actual_ops: list[dict]) -> dict:
    remaining = list(actual_ops)
    missing = []
    for exp in expected_ops:
        hit = next((a for a in remaining if op_matches(exp, a)), None)
        if hit is None:
            missing.append(exp)
        else:
            remaining.remove(hit)
    extra = [a for a in remaining if a["op"] != "person"]   # describing a person is always allowed
    return {"ok": not missing and not extra, "missing": missing, "extra": extra}
