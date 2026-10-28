# Operations: what Gemma is allowed to say (draft v0)

Gemma never writes to the database. It turns one sentence into a short list of **operations**, and the code decides what to do with them.

## Two rules for Gemma

1. **Copy names exactly as written.** "Mary" stays "Mary", even if the tree has two Marys. Gemma never guesses who someone is: the code resolves names and asks the user when a name is ambiguous.
2. **Copy dates and places as written.** "about 1815", "nel 1960", "30 December 1816". The code normalises them for sorting and checks.

## The operations

| Operation | Fields | Example sentence |
| --- | --- | --- |
| `person` | `name`, `sex` (F/M/U), `birth_name` (optional) | "Mary Shelley, born Mary Wollstonecraft Godwin..." |
| `union` | `partners` (2 names), `type` (marriage / partnership / unknown) | "Maria è la moglie di Marco" |
| `child` | `child`, `parents` (1 or 2 names), `relation` (birth / adopted / step / unknown) | "Ada was the daughter of Byron and Annabella" |
| `siblings` | `people` (2+ names), `kind` (full / half / step / unspecified), `shared_parent` (optional, for half) | "Claire was Mary's stepsister" |
| `event` | `person` or `partners`, `type` (birth / death / marriage / divorce / residence / occupation / other), `date`, `place`, `description` | "Roberta si è trasferita a Parigi" |
| `relation_hint` | `a`, `b`, `kind` (grandparent / grandchild / aunt_uncle / niece_nephew / cousin / in_law / other) | "Percy Florence was Godwin's grandson" |

`relation_hint` is for relationships that skip a generation. The code checks whether the tree already explains them; if not, it asks the user for the missing link instead of inventing a person.

## What the code does with them

1. **Resolve names.** One match: use it. No match: new person (shown in the preview). More than one: ask.
2. **Check.** No one is their own ancestor; dates are possible; no third birth parent; and so on (see `data-model.md`).
3. **Preview.** "I'm about to add 2 people, 1 marriage and 1 birth. Confirm?"
4. **Save** only after the user confirms.

## Output format

Gemma returns JSON constrained by a schema, with the `ops` list. An empty list is a valid answer: a sentence with no family facts produces no operations.

```json
{"ops": [
  {"op": "union", "partners": ["Maria Rossi", "Marco Rossi"], "type": "marriage"}
]}
```
