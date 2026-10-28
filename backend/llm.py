"""Gemma turns one sentence into operations. It never touches the database."""

import json
import os
import time

import ollama

from .ops import normalize_ops

MODEL = os.getenv("FAMILY_TREE_MODEL", "gemma4:e2b-it-qat")
PROMPT_VERSION = "p2"

SYSTEM = """You read one sentence about a family and turn it into operations for a family-tree app.
Answer with JSON only: {"ops": [...]}. Use an empty list if the sentence contains no family facts.

Which operation to use:
- mother, father, son, daughter, child, adopted child -> "child" (the child and their parents)
- brother, sister, half-sister, stepbrother, fratello, sorellastra... -> "siblings"
- wife, husband, partner, married, never married -> "union"
- born, died, married on/in, lived in, moved to, worked as -> "event", always with a "type":
  birth, death, marriage, divorce, residence, occupation or other. A marriage event has "partners" instead of "person".
- grandparent, grandchild, aunt, uncle, niece, nephew, cousin, in-law -> "relation_hint" (a is b's <kind>).
  Never use relation_hint for parents, children, siblings or couples.
- "person" only when the sentence says something about the person themselves: sex or birth name.

Rules:
1. Copy every name exactly as written. Never complete, guess or translate a name: "Mary" stays "Mary".
2. Words that describe the person's relation to the speaker are not part of the name: "nonna Lucia" -> "Lucia", "my uncle Tom" -> "Tom". Titles stay: "Lord Byron".
3. Copy dates and places as written, including words like "about", "probably", "verso", "forse".
4. Siblings: "full" only if the sentence says they share both parents; "unspecified" for a plain brother or sister.
5. Only write what the sentence says. Do not add facts you know from elsewhere.
6. Translate a sentence faithfully even if it seems wrong: another part of the app checks it."""

EXAMPLES = [
    (
        "Elena Bianchi, nata a Torino nel 1931, era la madre di Paolo e di sua sorella Giulia.",
        {"ops": [
            {"op": "person", "name": "Elena Bianchi", "sex": "F"},
            {"op": "event", "person": "Elena Bianchi", "type": "birth", "date": "1931", "place": "Torino"},
            {"op": "child", "child": "Paolo", "parents": ["Elena Bianchi"], "relation": "birth"},
            {"op": "child", "child": "Giulia", "parents": ["Elena Bianchi"], "relation": "birth"},
            {"op": "siblings", "people": ["Paolo", "Giulia"], "kind": "unspecified"},
        ]},
    ),
    (
        "Anna Ford and James Hill lived together for years but never married; their son Sam moved to Boston.",
        {"ops": [
            {"op": "union", "partners": ["Anna Ford", "James Hill"], "type": "partnership"},
            {"op": "child", "child": "Sam", "parents": ["Anna Ford", "James Hill"], "relation": "birth"},
            {"op": "event", "person": "Sam", "type": "residence", "place": "Boston", "description": "moved to Boston"},
        ]},
    ),
    (
        "Luca era il fratellastro di Sara da parte di padre, e sposò Irene a Napoli nel 1950.",
        {"ops": [
            {"op": "siblings", "people": ["Luca", "Sara"], "kind": "half", "shared_parent": "father"},
            {"op": "union", "partners": ["Luca", "Irene"], "type": "marriage"},
            {"op": "event", "partners": ["Luca", "Irene"], "type": "marriage", "date": "1950", "place": "Napoli"},
        ]},
    ),
    (
        "My great-uncle Thomas Hale probably died in Genoa around 1890.",
        {"ops": [
            {"op": "event", "person": "Thomas Hale", "type": "death", "date": "around 1890", "place": "probably Genoa"},
        ]},
    ),
    (
        "The family house had a big garden with lemon trees.",
        {"ops": []},
    ),
]

_STR = {"type": "string"}


def _names(min_items: int, max_items: int | None = None) -> dict:
    schema = {"type": "array", "items": {"type": "string"}, "minItems": min_items}
    if max_items:
        schema["maxItems"] = max_items
    return schema


def _op(op_name: str, required: list[str], /, **props) -> dict:
    """One kind of operation: only its own fields, and the ones it can't work without are required."""
    return {
        "type": "object",
        "properties": {"op": {"type": "string", "enum": [op_name]}, **props},
        "required": ["op", *required],
        "additionalProperties": False,
    }


EVENT_FIELDS = {"date": _STR, "place": _STR, "description": _STR}

SCHEMA = {
    "type": "object",
    "properties": {
        "ops": {
            "type": "array",
            "items": {"anyOf": [
                _op("person", ["name"], name=_STR, sex={"type": "string", "enum": ["F", "M", "U"]}, birth_name=_STR),
                _op("union", ["partners", "type"], partners=_names(2, 2),
                    type={"type": "string", "enum": ["marriage", "partnership", "unknown"]}),
                _op("child", ["child", "parents", "relation"], child=_STR, parents=_names(1, 2),
                    relation={"type": "string", "enum": ["birth", "adopted", "step", "unknown"]}),
                _op("siblings", ["people", "kind"], people=_names(2),
                    kind={"type": "string", "enum": ["full", "half", "step", "unspecified"]},
                    shared_parent={"type": "string", "enum": ["mother", "father", "unknown"]}),
                _op("event", ["person", "type"], person=_STR,
                    type={"type": "string", "enum": ["birth", "death", "residence", "occupation", "other"]}, **EVENT_FIELDS),
                _op("event", ["partners", "type"], partners=_names(2, 2),
                    type={"type": "string", "enum": ["marriage", "divorce"]}, **EVENT_FIELDS),
                _op("relation_hint", ["a", "b", "kind"], a=_STR, b=_STR,
                    kind={"type": "string", "enum": ["grandparent", "grandchild", "aunt_uncle", "niece_nephew", "cousin", "in_law", "other"]}),
            ]},
        }
    },
    "required": ["ops"],
}


def _messages(sentence: str) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM}]
    for example, answer in EXAMPLES:
        messages.append({"role": "user", "content": example})
        messages.append({"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)})
    messages.append({"role": "user", "content": sentence})
    return messages


def parse_sentence(sentence: str, model: str = MODEL) -> dict:
    """Returns {"ops", "problems", "raw", "seconds"}. Problems are ops we couldn't use."""
    start = time.perf_counter()
    response = ollama.chat(
        model=model,
        messages=_messages(sentence),
        format=SCHEMA,
        think=False,
        options={"temperature": 0, "num_predict": 600},   # hard stop: no endless answers
    )
    raw = response["message"]["content"]
    seconds = round(time.perf_counter() - start, 1)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"ops": [], "problems": [f"invalid JSON (length {len(raw)})"], "raw": raw, "seconds": seconds}
    ops, problems = normalize_ops(data.get("ops", []))
    return {"ops": ops, "problems": problems, "raw": raw, "seconds": seconds}
