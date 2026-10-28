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

from . import llm
from .db import connect
from .messages import Message, translate
from .planner import apply_plan, make_plan
from .tree import load_tree

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


@app.get("/api/health")
def health():
    return {"model": llm.MODEL, "prompt": llm.PROMPT_VERSION}
