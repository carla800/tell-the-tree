"""Gemma turns one sentence into operations. It never touches the database."""

import json
import os
import time

import ollama

from .ops import normalize_ops

MODEL = os.getenv("FAMILY_TREE_MODEL", "gemma4:e2b-it-qat")
PROMPT_VERSION = "p1"

SYSTEM = """You read one sentence about a family and turn it into operations for a family-tree app.
Answer with JSON only: {"ops": [...]}. Use an empty list if the sentence contains no family facts.

Operations:
- {"op": "person", "name", "sex": "F"|"M"|"U", "birth_name"}  -> only when the sentence says something about the person themselves (sex, birth name)
- {"op": "union", "partners": [name, name], "type": "marriage"|"partnership"|"unknown"}  -> a couple; "partnership" if they never married
- {"op": "child", "child": name, "parents": [one or two names], "relation": "birth"|"adopted"|"step"|"unknown"}
- {"op": "siblings", "people": [names], "kind": "full"|"half"|"step"|"unspecified", "shared_parent": "mother"|"father"}  -> "unspecified" when the sentence just says brother/sister
- {"op": "event", "person": name, "type": "birth"|"death"|"marriage"|"divorce"|"residence"|"occupation"|"other", "date", "place", "description"}  -> for a marriage, use "partners": [name, name] instead of "person"
- {"op": "relation_hint", "a": name, "b": name, "kind": "grandparent"|"grandchild"|"aunt_uncle"|"niece_nephew"|"cousin"|"in_law"|"other"}  -> a is b's <kind>, for relations that skip a generation

Rules:
1. Copy every name exactly as written. Never complete, guess or translate a name: "Mary" stays "Mary".
2. Words that describe the person's relation to the speaker are not part of the name: "nonna Lucia" -> "Lucia", "my uncle Tom" -> "Tom". Titles stay: "Lord Byron".
3. Copy dates and places as written, including words like "about", "probably", "verso", "forse".
4. Only write what the sentence says. Do not add facts you know from elsewhere.
5. Translate a sentence faithfully even if it seems wrong: another part of the app checks it."""

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
_LIST = {"type": "array", "items": {"type": "string"}}
SCHEMA = {
    "type": "object",
    "properties": {
        "ops": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "op": {"type": "string", "enum": ["person", "union", "child", "siblings", "event", "relation_hint"]},
                    "name": _STR, "sex": {"type": "string", "enum": ["F", "M", "U"]}, "birth_name": _STR,
                    "partners": _LIST, "type": _STR,
                    "child": _STR, "parents": _LIST, "relation": _STR,
                    "people": _LIST, "kind": _STR, "shared_parent": _STR,
                    "person": _STR, "date": _STR, "place": _STR, "description": _STR,
                    "a": _STR, "b": _STR,
                },
                "required": ["op"],
            },
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
