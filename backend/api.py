"""HTTP API used by the React interface.

    uvicorn backend.api:app --reload

Flow: /parse (Gemma reads the sentence) -> the user answers any questions -> /plan (re-check with the answers)
-> the user confirms -> /apply (saved). Gemma is called only once per sentence: the client sends Gemma's
operations (`model_ops`) back to /plan and /apply, and the server interprets them again each time.

`lang` ("en" or "it") is the language of the interface: the plan is written in it (backend/messages.py).
"""

import re
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import gedcom_io, llm, pdf_export
from .db import connect
from .messages import Message, translate
from .planner import BY_HAND, apply_plan, check_person_dates, make_plan
from .tree import load_tree, year_of

TREES = Path(__file__).resolve().parent.parent / "trees"
TREES.mkdir(exist_ok=True)

PHOTO_MAX_BYTES = 3 * 1024 * 1024
PHOTO_TYPES = {  # checked on the file's first bytes, not on what the browser says
    "image/jpeg": lambda b: b[:3] == b"\xff\xd8\xff",
    "image/png": lambda b: b[:8] == b"\x89PNG\r\n\x1a\n",
    "image/webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
}

app = FastAPI(title="Family tree")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class NewTree(BaseModel):
    name: str


class ParseRequest(BaseModel):
    sentence: str
    lang: str = "en"


class PlanRequest(BaseModel):
    model_ops: list[dict]
    choices: dict[str, int | str] = {}   # "Mary" -> person id or "new"; "meaning:nipote" -> chosen meaning id
    lang: str = "en"


class ApplyRequest(PlanRequest):
    sentence: str = ""
    by_hand: bool = False                # added with the form in the interface, not with a sentence


class PersonEdit(BaseModel):
    name: str
    birth_name: str | None = None
    also_known_as: str | None = None
    sex: str = "U"
    notes: str | None = None
    birth_date: str | None = None
    birth_place: str | None = None
    death_date: str | None = None
    death_place: str | None = None
    lang: str = "en"


class LinkRemoval(BaseModel):
    """Removing one link: a partner from a couple, or a child from a family. People are never deleted here."""
    action: str          # remove_partner | remove_child
    family_id: int
    person_id: int


def _path(name: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", name):
        raise HTTPException(400, "Tree names use lowercase letters, digits and hyphens.")
    return TREES / f"{name}.db"


def _open(name: str):
    path = _path(name)
    if not path.exists():
        raise HTTPException(404, f"No tree called '{name}'.")
    return connect(path)


def _tree_json(conn) -> dict:
    tree = load_tree(conn)
    photos = {r["person_id"]: r["updated"] for r in conn.execute("SELECT person_id, updated FROM photo")}
    people = []
    for p in tree.people.values():
        events = [e for e in tree.events if e.person_id == p.id]
        people.append({
            **asdict(p),
            "born": tree.year(p.id, "birth"),
            "died": tree.year(p.id, "death"),
            "events": [asdict(e) for e in events],
            "photo": photos.get(p.id),        # when it last changed, or None
        })
    families = [{
        "id": f.id, "partners": f.partners, "union_type": f.union_type,
        "children": [{"id": c, "relation": r} for c, r in f.children.items()],
        "events": [asdict(e) for e in tree.events if e.family_id == f.id],
    } for f in tree.families.values()]
    return {"people": people, "families": families, "claims": [asdict(c) for c in tree.claims]}


def _plan_json(plan, lang: str = "en") -> dict:
    """The plan in the interface's language. `changes` lets the interface draw the preview
    in the tree (new people have negative ids)."""
    say = lambda items: [translate(x, lang) for x in items]  # noqa: E731
    questions = []
    for q in plan.questions:
        if q["kind"] == "meaning":
            q = {**q, "options": [{"id": o["id"], "label": translate(o["label"], lang)} for o in q["options"]]}
        questions.append(q)
    return {
        "status": plan.status, "changes": plan.changes, "questions": questions,
        "summary": say(plan.summary), "known": say(plan.known),
        "errors": say(plan.errors), "warnings": say(plan.warnings),
    }


@app.get("/api/trees")
def list_trees():
    return sorted(p.stem for p in TREES.glob("*.db") if not p.stem.startswith("_"))


@app.post("/api/trees")
def create_tree(req: NewTree):
    path = _path(req.name)
    if path.exists():
        raise HTTPException(409, f"'{req.name}' already exists.")
    connect(path).close()
    return {"name": req.name}


@app.delete("/api/trees/{name}")
def delete_tree(name: str):
    if name == "villa-diodati":
        raise HTTPException(403, "The demonstration tree cannot be deleted.")
    path = _path(name)
    if not path.is_file():
        raise HTTPException(404, f"No tree called '{name}'.")
    try:
        path.unlink()
    except OSError as exc:
        raise HTTPException(500, f"Could not delete tree: {exc}") from exc
    return {"deleted": name}


@app.get("/api/trees/{name}")
def get_tree(name: str):
    with closing(_open(name)) as conn:
        return _tree_json(conn)


@app.post("/api/trees/{name}/parse")
def parse(name: str, req: ParseRequest):
    with closing(_open(name)) as conn:
        tree = load_tree(conn)
    result = llm.parse_sentence(req.sentence)
    return {"model_ops": result["model_ops"], "seconds": result["seconds"],
            "plan": _plan_json(_make(tree, result), req.lang)}


@app.post("/api/trees/{name}/plan")
def replan(name: str, req: PlanRequest):
    with closing(_open(name)) as conn:
        tree = load_tree(conn)
    return {"plan": _plan_json(_make(tree, llm.interpret(req.model_ops), req.choices), req.lang)}


@app.post("/api/trees/{name}/apply")
def apply(name: str, req: ApplyRequest):
    with closing(_open(name)) as conn:
        plan = _make(load_tree(conn), llm.interpret(req.model_ops), req.choices)
        if plan.status != "save":
            raise HTTPException(409, {"message": "The sentence needs answers or has errors.",
                                      "plan": _plan_json(plan, req.lang)})
        apply_plan(conn, plan, req.sentence, by_hand=req.by_hand)
        return {"saved": [translate(s, req.lang) for s in plan.summary], "tree": _tree_json(conn)}


def _make(tree, interpreted: dict, choices: dict | None = None):
    plan = make_plan(tree, interpreted["ops"], choices)
    for problem in interpreted["problems"]:
        # never stay silent: say which part of the sentence did not become tree facts
        plan.warnings.append(problem if isinstance(problem, Message) else Message("part_not_read"))
    return plan


# ---------- photos ----------

def _person_exists(conn, pid: int):
    if not conn.execute("SELECT 1 FROM person WHERE id = ?", (pid,)).fetchone():
        raise HTTPException(404, "No such person in this tree.")


@app.get("/api/trees/{name}/people/{pid}/photo")
def get_photo(name: str, pid: int):
    with closing(_open(name)) as conn:
        row = conn.execute("SELECT mime, data FROM photo WHERE person_id = ?", (pid,)).fetchone()
    if not row:
        raise HTTPException(404, "No photo.")
    return Response(row["data"], media_type=row["mime"], headers={"Cache-Control": "private, max-age=31536000"})


@app.put("/api/trees/{name}/people/{pid}/photo")
async def put_photo(name: str, pid: int, request: Request):
    data = await request.body()
    if len(data) > PHOTO_MAX_BYTES:
        raise HTTPException(413, "The photo is too big (3 MB at most).")
    mime = next((m for m, looks_like in PHOTO_TYPES.items() if looks_like(data)), None)
    if mime is None:
        raise HTTPException(415, "Use a JPEG, PNG or WebP picture.")
    updated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(_open(name)) as conn, conn:
        _person_exists(conn, pid)
        conn.execute("INSERT OR REPLACE INTO photo (person_id, mime, data, updated) VALUES (?, ?, ?, ?)",
                     (pid, mime, data, updated))
    return {"photo": updated}


@app.delete("/api/trees/{name}/people/{pid}/photo")
def delete_photo(name: str, pid: int):
    with closing(_open(name)) as conn, conn:
        conn.execute("DELETE FROM photo WHERE person_id = ?", (pid,))
    return {"photo": None}


def _drop_empty_families(conn):
    """A family with no children and fewer than two partners links nobody: remove it
    (unless one partner is left with the family's events, e.g. a wedding date)."""
    conn.execute("""
        DELETE FROM family WHERE NOT EXISTS (SELECT 1 FROM family_child fc WHERE fc.family_id = family.id)
          AND (partner1_id IS NULL OR partner2_id IS NULL)
          AND (partner1_id IS NULL AND partner2_id IS NULL
               OR NOT EXISTS (SELECT 1 FROM event e WHERE e.family_id = family.id))""")


@app.put("/api/trees/{name}/people/{pid}")
def edit_person(name: str, pid: int, req: PersonEdit):
    """Edits a person with the form. The dates go through the same checks as a sentence."""
    if not req.name.strip() or len(req.name.strip()) > 200:
        raise HTTPException(400, "A name is required (max 200 characters).")
    if req.sex not in ("F", "M", "U"):
        raise HTTPException(400, "Invalid sex.")
    clean = lambda v: (v or "").strip() or None  # noqa: E731
    wanted = {"birth": (clean(req.birth_date), clean(req.birth_place)),
              "death": (clean(req.death_date), clean(req.death_place))}
    with closing(_open(name)) as conn, conn:
        _person_exists(conn, pid)
        errors = check_person_dates(load_tree(conn), pid, year_of(wanted["birth"][0]), year_of(wanted["death"][0]))
        if errors:
            raise HTTPException(409, {"message": translate(errors[0], req.lang),
                                      "errors": [translate(e, req.lang) for e in errors]})
        conn.execute("UPDATE person SET name=?, birth_name=?, also_known_as=?, sex=?, notes=? WHERE id=?",
                     (req.name.strip(), clean(req.birth_name), clean(req.also_known_as), req.sex, clean(req.notes), pid))
        for kind, (date, place) in wanted.items():
            row = conn.execute("SELECT id, date_text, place FROM event WHERE person_id=? AND type=? ORDER BY id",
                               (pid, kind)).fetchone()
            if row and not date and not place:
                conn.execute("DELETE FROM event WHERE id=?", (row["id"],))
            elif row and (row["date_text"], row["place"]) != (date, place):
                # changed by hand: the old source no longer says this
                conn.execute("UPDATE event SET date_text=?, place=?, source=? WHERE id=?", (date, place, BY_HAND, row["id"]))
            elif not row and (date or place):
                conn.execute("INSERT INTO event (person_id, type, date_text, place, source) VALUES (?, ?, ?, ?, ?)",
                             (pid, kind, date, place, BY_HAND))
        return _tree_json(conn)


@app.delete("/api/trees/{name}/people/{pid}")
def delete_person(name: str, pid: int):
    """Deletes a person with their events, photo and links. Their relatives stay in the tree."""
    with closing(_open(name)) as conn, conn:
        _person_exists(conn, pid)
        conn.execute("UPDATE family SET partner1_id=NULL WHERE partner1_id=?", (pid,))
        conn.execute("UPDATE family SET partner2_id=NULL WHERE partner2_id=?", (pid,))
        conn.execute("DELETE FROM person WHERE id=?", (pid,))   # events, photo, child links and notes go with it
        _drop_empty_families(conn)
        return _tree_json(conn)


@app.post("/api/trees/{name}/relations/remove")
def remove_link(name: str, req: LinkRemoval):
    """Fixes a wrong link. New links are added with a sentence or with "Add a relative",
    which go through the planner's checks."""
    with closing(_open(name)) as conn, conn:
        family = conn.execute("SELECT * FROM family WHERE id=?", (req.family_id,)).fetchone()
        if family is None:
            raise HTTPException(404, "Family not found.")
        if req.action == "remove_partner":
            slot = next((s for s in ("partner1_id", "partner2_id") if family[s] == req.person_id), None)
            if slot is None:
                raise HTTPException(404, "This person is not a partner in this family.")
            conn.execute(f"UPDATE family SET {slot}=NULL WHERE id=?", (req.family_id,))
        elif req.action == "remove_child":
            if conn.execute("DELETE FROM family_child WHERE family_id=? AND child_id=?",
                            (req.family_id, req.person_id)).rowcount == 0:
                raise HTTPException(404, "This person is not a child in this family.")
        else:
            raise HTTPException(400, "Unknown action.")
        _drop_empty_families(conn)
        return _tree_json(conn)


@app.get("/api/health")
def health():
    return {"model": llm.MODEL, "prompt": llm.PROMPT_VERSION}


# ---------- GEDCOM and PDF ----------

def _gedcom_error(exc: gedcom_io.GedcomError, lang: str):
    return HTTPException(400, translate(exc.message, lang))


@app.post("/api/gedcom/preview")
async def preview_gedcom(request: Request, lang: str = "en"):
    """What a GEDCOM file contains, before importing it."""
    try:
        return gedcom_io.preview(await request.body())
    except gedcom_io.GedcomError as exc:
        raise _gedcom_error(exc, lang) from exc


@app.post("/api/gedcom/import/{name}")
async def import_gedcom(name: str, request: Request, lang: str = "en"):
    """A GEDCOM file becomes a new tree. Nothing is created if the file can't be read."""
    path = _path(name)
    if path.exists():
        raise HTTPException(409, translate(Message("tree_exists", name=name), lang))
    raw = await request.body()
    try:
        gedcom_io.parse(raw)
    except gedcom_io.GedcomError as exc:
        raise _gedcom_error(exc, lang) from exc
    try:
        with closing(connect(path)) as conn, conn:
            result = gedcom_io.import_into(conn, raw)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {"name": name, **result}


@app.get("/api/trees/{name}/export.ged")
def export_gedcom(name: str):
    with closing(_open(name)) as conn:
        data = gedcom_io.export(conn)
    return Response(data, media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}.ged"'})


@app.get("/api/trees/{name}/export.pdf")
def export_pdf(name: str, lang: str = "en", title: str | None = None):
    """The family register: every family and every person, ready to print or send."""
    with closing(_open(name)) as conn:
        data = pdf_export.create_pdf(conn, title or name.replace("-", " ").title(), lang=lang, demo=name == "villa-diodati")
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})
