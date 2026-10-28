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

Holdout sentences written and committed (`tests/holdout.txt`) before any model output existed.

## Day 0, afternoon - the engine

Moved the backend up from Thursday, in case I can't work tomorrow.

- `backend/tree.py`: the tree in memory and the derived relationships. All 8 tricky Villa Diodati relations come out right, including Allegra being Mary Shelley's step-niece.
- `backend/planner.py`: turns operations into a preview. It resolves names (and asks when "Mary" could be three people), rejects impossible facts with a reason a person can read ("Lord Byron is already an ancestor of Ada Lovelace"), and saves only after confirmation. Every saved fact keeps the sentence it came from.
- `backend/llm.py`: the prompt (version p1) and a JSON schema for Gemma's answer. Lessons from Week 3 applied from the start: temperature 0, thinking off, a hard cap on the answer length, and few-shot examples that are not test sentences (a test checks this).
- `backend/api.py`: parse -> answer questions -> plan -> apply. Gemma is called once per sentence.
- `evals/run.py`: runs Gemma on the test sentences and scores the two halves separately: did Gemma produce the right operations, and did the app then save / ask / reject correctly. Every run is logged with Gemma's raw answers in `evals/runs/`.
- 28 tests on the code side, with a fake Gemma that always answers correctly, so a failure there is always our bug.

## Run 1 - prompt p1, Gemma 4 E2B (dev set, 15 sentences)

**Model 4/15, code 14/15**, 1.1 minutes in total (2-6 seconds per sentence after the first).

The code side held up: "Percy married Mary" came back with the names as written, and the app asked which Percy and which Mary instead of guessing.

Gemma's mistakes had two causes:
1. **Events without a type.** Gemma wrote the date and the place but not whether it was a birth, a death or a move (d03, d10, d14). The code drops an event it can't classify.
2. **`relation_hint` for everything.** Half-sister, stepsister, mother and grandson all came back as relation_hint, and without saying which relation (d04, d05, d09, d11). The worst one is d11: without a proper `child` operation, the app could not reject "Ada Lovelace was Lord Byron's mother".

Both come from my schema: every field except `op` was optional, so Gemma could stop halfway through an operation.

Smaller ones: "never married" became `unknown` instead of `partnership` (d07); "fratelli" became `full` instead of `unspecified` (d13). The second one is debatable in Italian, and the planner treats both the same when the parents are unknown; I'm keeping the test as written.

A design lesson: when part of Gemma's answer was unusable, the app said nothing. Now the API adds a warning ("Part of this sentence couldn't be turned into tree facts") instead of staying silent.

**Changes for p2**
- One schema per operation, with the fields it can't work without marked as required: an event without a type, or a relation_hint without a kind, can no longer be written. Two new tests check that the schema accepts every correct answer and refuses the mistakes of run 1.
- The prompt now says which operation to use for which word (mother -> child, half-sister -> siblings, grandson -> relation_hint), and that relation_hint is never for parents, children, siblings or couples.
- Two new few-shot examples: a couple who never married, and a half-brother "on the father's side" with a marriage date. Still no test sentence among the examples.

## Run 2 - prompt p2

**Model 8/15 (from 4), code 14/15.** Events without a type disappeared completely.

What was still wrong:
- `relation_hint` was still a magnet: "stepsister" came back as niece, "mother" as aunt (d05, d11). The code still rejected d11, because the tree says Ada is Byron's daughter.
- Small inventions: "a few days after giving birth" became Mary Wollstonecraft's own *birth* (d03), and "Villa Diodati" became a person (d10).
- Lost pieces in long sentences: the date of Byron's wedding (d06), "who never married" (d07).

**The real problem: we were asking a small model to classify family relations, which is exactly what it does worst.** It's the same lesson other builders wrote about this month: let the model copy, let the code decide.

## Redesign - prompt p3: Gemma copies, the code decides

- Gemma now has three operations instead of six. For any family relation it writes `relation` and **copies the word as written**: "half-sister on her mother's side", "figlio adottivo", "sposò". (`docs/operations.md`)
- `backend/words.py`: an English and Italian dictionary decides what the word means. The order of the checks matters: "grandson" before "son", "stepmother" and "mother-in-law" before "mother", "never married" before "married", and "on her mother's side" is removed before looking for "mother". 61 tests cover it.
- **"Nipote."** In Italian it means both grandchild and niece/nephew; "fratellastro" and "sorellastra" can mean a half- or a step-sibling. The code doesn't guess: if the tree already explains one meaning ("Percy Florence è il nipote di William Godwin": the tree shows he's his grandson), it uses it; otherwise it asks. My parents would say "nipote" all the time, so this matters for the real use of the app.
- The word also gives the sex when it says it ("moglie" -> F, "grandson" -> M), but not verbs like "sposò".
- An unknown word ("madrina") becomes a warning in the preview, never a silent drop.
- New test file `tests/model_answers.yaml`: the ideal Gemma answer for each dev sentence, written from the sentences alone. With those answers the whole pipeline gets 15/15, so from now on any failure in the evals is Gemma's, not the dictionary's.
- 125 tests in total.

## Run 3 - prompt p3

**Model 11/15 (from 8), code 14/15.** Stepsister, mother, grandson, "figlio adottivo", "fratelli", "never married": all copied and read correctly.

Three of the four failures had the same cause, and it was my format, not Gemma: for d02, d06 and d08 Gemma wrote the wedding with its date (an event) but not also a relation word "married". A wedding with a date *means* they were married; the code should infer that instead of asking Gemma to say it twice. Fixed in code: a marriage event now implies the union.

**Decision on d10** ("Villa Diodati is a mansion near Lake Geneva, rented by Byron in June 1816"). Gemma read it as Byron living at Villa Diodati, which is a fair reading, and the app then asked which Byron, which is right: the tree has Lord Byron, Allegra Byron and Ada (born Byron). I had written "decide after the first run" in the test; I'm now accepting that reading as a second correct answer (`also_ok`). Changing dev sentences after seeing results is fine as long as it's written down: that's what the untouched holdout set is for.

Still wrong: d06, the longest sentence. Gemma loses "their only child, Ada" (the parent link) and copies "London" from Ada's birth onto the wedding. A small-model limit with long sentences: something to say honestly in the post.

Replaying run 3's exact answers through the new code: **model 14/15, code 15/15.**

## Run 4 - same code, run for real

**Model 14/15, code 15/15**, the same result as the replay: so the replay wasn't luck. 15 sentences in about 0.8 minutes on my laptop: the first one takes ~19 s (Gemma loading), then 2-5 s each. The only failure is still d06, the long sentence.

## First live test, from the API page

I started the server and tried a sentence that isn't in any test: **"Allegra era la nipote di Mary Shelley."** The app read "nipote", saw that the tree already explains it as niece (Allegra is the daughter of Claire, Mary's stepsister), and asked nothing. The first answer took 22.7 s, because Gemma was loading.

## The interface

React + TypeScript, React Flow for the tree, dagre for the layout. Nothing leaves the computer: even the fonts are files inside the app, not loaded from Google.

- **Two looks.** The Villa Diodati demo is June 1816, "the year without a summer": storm-blue night, a moon, parchment cards, and three bats that cross the sky once (not if the computer asks for reduced motion). Every other tree is an old family register: pale paper, ink, a red rule under each name.
- **Generations are columns, read left to right.** The first version went top to bottom like most family trees, but the demo has 11 people in one generation and the cards became unreadable. Sideways, the same tree fits the screen and the names can be read.
- **You see the change before it happens.** After Gemma reads a sentence, the new people and lines appear in the tree, dashed and marked "new", and the view moves to them. Nothing is saved until "Add to tree".
- **Questions stay visible.** "Which Percy do you mean?" stays on screen with your answer while the app asks about Mary.
- **Every fact shows where it came from**: click a person to see their dates, places, and the sentence or web page each one came from.
- A key explains the lines (child, stepchild, adopted) and the knots (married, together but not married, parents).
- The tip "One fact per sentence works best" is under the text box, because of d06.

I tested it with a fake Gemma that gives the ideal answers, so the screenshots check the interface, not the model.

**A bug the interface found.** "Percy married Mary on 30 December 1816" wanted to add the wedding again: the demo data has it as 1816-12-30, and the app compared the text. Now dates are read as day, month and year (English or Italian months), and an event the tree already has, written differently or with less detail, is listed under "already knows" instead of being added twice. New details (a place, a more precise date) are still added. 128 tests.

**First real sentence in the interface.** "Percy Florence Shelley married Jane St John in 1848" with the real Gemma (22.6 s, the first sentence loads the model): the right preview, but the wedding came with the place "not specified". The sentence has no place, and instead of leaving the field out Gemma filled it in. Now words like "not specified", "unknown", "non specificato" or "sconosciuto" in a date, place or description mean "no value" and the field is dropped. 129 tests.

## Run 5 - a bigger Gemma: E4B against E2B

Same 15 sentences, same prompt p3, but with `gemma4:e4b-it-qat` (a 6 GB download).

| | E2B (run 4) | E4B (run 5) |
|---|---|---|
| Model | 14/15 | 12/15 (13/15 with the fix below) |
| Code | 15/15 | 15/15 |
| Time for 15 sentences | 0.8 min | 2.0 min |
| First sentence (loading) | ~19 s | 36 s |

- **E4B gets d06 right**, the long sentence that E2B never managed: the wedding, Ada as the child of both, and her birth.
- **d03: E4B makes the mistake E2B made in run 2.** "A few days after giving birth" becomes Mary Wollstonecraft's own birth. The code can't know that's wrong, so it would show it in the preview: this is exactly why nothing is saved before a person has seen it.
- **d10:** E4B read it as Byron living at Villa Diodati (the reading I already accept), but copied the place as "Villa Diodati near Lake Geneva". A fair copy; the scoring compares places exactly, so it counts as wrong. I'm leaving the scoring as it is.
- **d13 was not a model mistake.** E4B said it both ways, "Marco is Roberta's brother" and "Roberta is Marco's sister": the same fact twice. Now the code counts a fact said both ways once (it also keeps the sexes: Marco M, Roberta F). Replayed with this fix, E4B's d13 is right. 130 tests.

**Decision: E2B stays the default.** It's smaller, two and a half times faster, and on these sentences it makes fewer mistakes. E4B is better only on long sentences, and the interface already says one fact per sentence works best. Anyone can switch with the `FAMILY_TREE_MODEL` setting.

## Italian and English, and a photo for each person

**Two languages.** My parents should be able to use this in Italian. Gemma already read sentences in both languages; now the interface speaks both too, and you can switch at any time (it starts in the browser's language).
- The interface's words are in `frontend/src/i18n.ts`.
- The sentences the engine writes ("New person: …", "Which Percy do you mean?", the reasons for a rejection) are in `backend/messages.py`. The planner builds each one as a `Message`: an ordinary English string, so tests, evals and logs read it as before, which also remembers its key and values, so the API can say it again in Italian.
- Italian needs care where English doesn't: "nipote" is shown as "nipote (di nonno)" or "nipote (di zio)", and a birth name on a card is "nata Westbrook" or "nato Gordon Byron", depending on the person's sex.
- The answer to "what does nipote mean here?" is now an id (`grandchild`, `niece_nephew`), not the English label, so it works in any language.
- Adding a language means one more block in each of the two files. A test checks that every message has the same blanks in every language.

**Photos.** Click a person, then "Add a photo".
- The photo is stored **inside the tree's file**, not in a folder next to it: the whole tree, pictures included, stays one file you can copy or back up. After losing my old genealogy site, that matters more to me than anything else here.
- The browser makes the picture small before sending it (at most 640 px, JPEG): a 5 MB phone photo becomes about 100 KB.
- The server checks the file's first bytes, not what the browser says, and accepts only JPEG, PNG and WebP up to 3 MB.
- On the tree, the photo is a small oval miniature at Villa Diodati and a pasted print in the register.
- The demo tree has no pictures: you can add your own.

**A bug found while testing.** Switching from a tree with photos to another one asked the server for a photo that didn't exist (404): for an instant, the old tree was drawn under the new tree's name. Now a tree's data always travels with its name.

136 tests.

**Cards a little wider.** With a photo, "Wollstonecraft" broke in the middle of the word: the name had 106 pixels and the word needs 113. The cards are now 196 px instead of 184, the miniature is smaller, and if a name still doesn't fit the browser breaks it with a hyphen instead of anywhere.

## Adding people by hand

Typing a sentence isn't always the quickest way, so now you can also click a person and choose "Add a relative": mother, father, daughter, son, sister, brother, wife, husband or partner, a name, and optionally when and where they were born. For a child, the person's partner is already filled in as the other parent. In an empty tree, "Or add a person by hand" adds the first one.

**The form writes the same operations Gemma writes** (`{"op": "relation", "person": "Mario Rossi", "word": "son", "of": ["Virginia Bianchi", "Filippo Rossi"]}`), so from there it's exactly the same path: the same dictionary, the same checks, the same preview in the tree, and nothing is saved before "Add to tree". The person you clicked is passed as an answer already given, so two people with the same name never get mixed up. The source of these facts says "Added by hand".

**Two engine bugs found by building a fake family:**
- *Two knots for the same couple.* "Mario and Lorenzo are brothers", then "Virginia married Filippo", then "Mario is their son": the app filled the brothers' family with the two parents instead of joining it to the couple that already existed, so the tree showed Virginia and Filippo twice, once as a couple and once as parents. Now the two families become one (a new `merge_family` change, also drawn in the preview).
- *A son older than his mother was accepted* when the relation and the birth arrived together, by hand or in a sentence like "Paolo, born in 1940, is Virginia's son". The check only worked if the birth was already in the tree before the relation. Now a birth is also checked against the parents.

139 tests.
