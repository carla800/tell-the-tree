# DEVLOG

Build journal for the Week 4 project ("Ghost in the Machine"). Newest entries at the bottom.
Deadline: 31 October 2026, 23:59 PDT (1 November, 07:59 in Italy).

## Day 0 - Wednesday 28 October

**The idea.** A family tree that lives on my own computer and grows from plain sentences ("Maria Rossi è la moglie di Marco Rossi").

**Why.** Years ago I built my family tree on a website, asking my parents for every name and date. I didn't open it for a while, and when I came back the site was gone: a 404 and years of work lost. I want a tree that can't disappear, and that my parents can update by just saying what they know.

**How the theme fits.** Día de los Muertos is about remembering the people who came before us; this keeps their memory safe on your own machine. For the demo I use a real and very gothic family: the people around the 1816 ghost-story contest at Villa Diodati, where Frankenstein was born. Byron's daughter was Ada Lovelace, often called the first programmer.

**Decisions**
- Gemma turns a sentence into a short list of operations; **the code** resolves names, checks the tree and saves only after the user confirms. Gemma never writes to the database. (`docs/operations.md`)
- Data model on GEDCOM's idea of families: siblings, half-siblings and step-siblings are derived, never stored, so the tree can't contradict itself. (`docs/data-model.md`)
- One SQLite file per tree; export to GEDCOM so the data is never locked into this app.
- Stack: Python + FastAPI + Ollama (Gemma 4) for the backend, React + TypeScript for the interface.
- Left for after the deadline: voice input (the browser's speech recognition sends audio to a cloud service, which would break the whole point), photos.

**Test set written before any model run:** 15 dev sentences in English and Italian, including traps: an ambiguous "Percy married Mary" (two of each in the tree), a sentence with no family facts, and an impossible one ("Ada Lovelace was Lord Byron's mother") that Gemma must translate faithfully and the code must reject. The holdout set is written by me without looking at any output, and will be run once after freezing the code. (`tests/sentences.yaml`)

**Demo data:** 22 people and 9 families from Villa Diodati, each with a source (mostly Wikipedia). Sources already disagree in places: Allegra Byron died on 19 or 20 April 1822 depending on the source. (`data/villa-diodati.yaml`)

**First bug, before any code.** In the first version of the demo data, places with a comma inside `{ }` (like `place: Gulf of La Spezia, Italy`) were silently split in two: in YAML's inline style a comma separates fields, so "Italy" became a field of its own. My editor reformatted the file on save and the stray "Italy" showed up on its own line. Fixed by switching to block style, quoting all dates, and checking every field name when the file is loaded.

**New requirement: "probably".** Wikipedia says Gilbert Imlay was *probably* born in Upper Freehold and that the death record on Jersey *may* be his. Genealogy is full of uncertain facts, and the old site had no way to say so. The app must keep "probably", "about" and "maybe" instead of turning them into certainties.

**Plan**
- Wed evening: verify the demo data, write the holdout sentences, set up the repo.
- Thu evening: backend (database, Gemma, checks), first run on the dev set.
- Fri evening: interface with the tree.
- Sat: gothic theme for the Diodati tree, GEDCOM export, README, demo GIF, post.
