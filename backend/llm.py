"""Gemma reads one sentence and copies out its facts. It never touches the database.

Gemma doesn't decide what a relation word means: it copies it ("half-sister", "nipote"),
and backend/words.py decides. A small model copies well and classifies badly.
"""

import json
import os
import time

import ollama

from .ops import normalize_model_ops
from .words import to_tree_ops

MODEL = os.getenv("FAMILY_TREE_MODEL", "gemma4:e2b-it-qat")
PROMPT_VERSION = "p3"

SYSTEM = """You read one sentence about a family and copy its facts into JSON for a family-tree app: {"ops": [...]}.
Use an empty list if the sentence says nothing about people's families or lives.

Three operations:

1. relation: {"op": "relation", "person": name, "word": relation word, "of": [one or two names]}
   For every family relation. Read it as: <person> is the <word> of <of>.
   Copy the relation word exactly as it is written, in the sentence's language, together with the words that
   qualify it: "half-sister on her mother's side", "figlio adottivo", "fratellastro da parte di padre", "never married".
   Do not translate the word and do not replace it with another word.
   Someone who is the child of two people: one relation with both parents in "of".
   A couple: one relation with the word that describes them ("wife", "married", "never married", "sposò").

2. event: something that happened to one person:
   {"op": "event", "person": name, "type": "birth"|"death"|"residence"|"occupation"|"other", "date", "place", "description"}
   or a wedding with a date or a place:
   {"op": "event", "partners": [name, name], "type": "marriage"|"divorce", "date", "place"}
   "gave birth" or "giving birth" is the birth of the child, never the mother's own birth.

3. person: {"op": "person", "name", "sex", "birth_name"}, only when the sentence states the person's sex or birth name.

Rules:
- Copy every name exactly as written. Never complete, guess or translate a name: "Mary" stays "Mary".
- Words that describe someone's relation to the speaker are not part of their name: "nonna Lucia" -> "Lucia", "my uncle Tom" -> "Tom". Titles stay: "Lord Byron".
- Copy dates and places as written, including words like "about", "probably", "verso", "forse".
- Places, houses and companies are never people.
- Only write what the sentence says. Do not add facts you know from elsewhere.
- Copy a sentence faithfully even if it seems wrong: another part of the app checks it."""

EXAMPLES = [
    (
        "Elena Bianchi, nata a Torino nel 1931, era la madre di Paolo e di sua sorella Giulia.",
        {"ops": [
            {"op": "event", "person": "Elena Bianchi", "type": "birth", "date": "1931", "place": "Torino"},
            {"op": "relation", "person": "Elena Bianchi", "word": "madre", "of": ["Paolo", "Giulia"]},
            {"op": "relation", "person": "Giulia", "word": "sorella", "of": ["Paolo"]},
        ]},
    ),
    (
        "Anna Ford and James Hill lived together for years but never married; their son Sam moved to Boston.",
        {"ops": [
            {"op": "relation", "person": "Anna Ford", "word": "never married", "of": ["James Hill"]},
            {"op": "relation", "person": "Sam", "word": "son", "of": ["Anna Ford", "James Hill"]},
            {"op": "event", "person": "Sam", "type": "residence", "place": "Boston", "description": "moved to Boston"},
        ]},
    ),
    (
        "Luca era il fratellastro di Sara da parte di padre, e sposò Irene a Napoli nel 1950.",
        {"ops": [
            {"op": "relation", "person": "Luca", "word": "fratellastro da parte di padre", "of": ["Sara"]},
            {"op": "relation", "person": "Luca", "word": "sposò", "of": ["Irene"]},
            {"op": "event", "partners": ["Luca", "Irene"], "type": "marriage", "date": "1950", "place": "Napoli"},
        ]},
    ),
    (
        "Rose Carter was the grandmother of Lily, and Max was Lily's cousin.",
        {"ops": [
            {"op": "relation", "person": "Rose Carter", "word": "grandmother", "of": ["Lily"]},
            {"op": "relation", "person": "Max", "word": "cousin", "of": ["Lily"]},
        ]},
    ),
    (
        "My great-uncle Thomas Hale probably died in Genoa around 1890.",
        {"ops": [
            {"op": "event", "person": "Thomas Hale", "type": "death", "date": "around 1890", "place": "probably Genoa"},
        ]},
    ),
    (
        "They spent every summer at the old mill near Bath, a house with a big garden.",
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
                _op("relation", ["person", "word", "of"], person=_STR, word=_STR, of=_names(1, 2)),
                _op("event", ["person", "type"], person=_STR,
                    type={"type": "string", "enum": ["birth", "death", "residence", "occupation", "other"]}, **EVENT_FIELDS),
                _op("event", ["partners", "type"], partners=_names(2, 2),
                    type={"type": "string", "enum": ["marriage", "divorce"]}, **EVENT_FIELDS),
                _op("person", ["name"], name=_STR, sex={"type": "string", "enum": ["F", "M", "U"]}, birth_name=_STR),
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


def interpret(model_ops: list) -> dict:
    """Gemma's raw operations -> cleaned model ops + tree ops + problems."""
    model_ops, problems = normalize_model_ops(model_ops)
    ops, word_problems = to_tree_ops(model_ops)
    return {"model_ops": model_ops, "ops": ops, "problems": problems + word_problems}


def parse_sentence(sentence: str, model: str = MODEL) -> dict:
    """Returns {"model_ops", "ops", "problems", "raw", "seconds"}."""
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
        return {"model_ops": [], "ops": [], "problems": [f"invalid JSON (length {len(raw)})"], "raw": raw, "seconds": seconds}
    return {**interpret(data.get("ops", [])), "raw": raw, "seconds": seconds}
