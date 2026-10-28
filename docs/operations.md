# Operations (v3): Gemma copies, the code decides

Gemma never writes to the database, and since prompt p3 it doesn't decide what a relation means either. It copies the facts out of the sentence; the code decides what they mean for the tree.

## What Gemma writes

| Operation | Fields | Example |
| --- | --- | --- |
| `relation` | `person`, `word`, `of` (1 or 2 names) | "Fanny was Mary's half-sister on her mother's side" -> `{"person": "Fanny", "word": "half-sister on her mother's side", "of": ["Mary"]}` |
| `event` | `person` + `type` (birth / death / residence / occupation / other), or `partners` + `type` (marriage / divorce); `date`, `place`, `description` | "Roberta si è trasferita a Parigi" |
| `person` | `name`, `sex`, `birth_name` | only when the sentence states them |

Rules for Gemma: copy names, relation words, dates and places exactly as written, including "probably", "verso", "forse". Never complete a name ("Mary" stays "Mary"). Places are never people.

## What the code does

1. **Reads the word** (`backend/words.py`): an English and Italian dictionary turns "half-sister on her mother's side" into *siblings, half, shared mother*, and "figlio adottivo" into *adopted child*. Compound words are checked before the words they contain: "grandson" is not "son", "stepmother" is not "mother", "mother-in-law" is not "mother".
2. **Handles words with two meanings.** In Italian, **"nipote"** is both a grandchild and a niece/nephew; **"fratellastro" / "sorellastra"** can be a half- or a step-sibling. The code first checks the tree: if it already explains exactly one meaning, it uses it. Otherwise it asks.
3. **Resolves names.** One match: use it. No match: new person. More than one: ask.
4. **Checks.** No one is their own ancestor; dates are possible; no third birth parent; a new fact can't contradict the tree.
5. **Preview**, then **save** only after the user confirms. Every saved fact keeps the sentence it came from.
6. **Never stays silent.** A word it doesn't know ("madrina") or an unusable part of Gemma's answer becomes a warning in the preview.

## Tree operations (internal)

What the planner works with, and what the test sentences' `expected_ops` are written in:
`person`, `union`, `child`, `siblings`, `event`, `relation_hint`, plus `ambiguous` (a word with several meanings, carrying one list of operations per meaning).
