"""HTTP API used by the React interface.

    uvicorn backend.api:app --reload

Flow: /parse (Gemma reads the sentence) -> the user answers any questions -> /plan (re-check with the answers)
-> the user confirms -> /apply (saved). Gemma is called only once per sentence: the client sends Gemma's
operations (`model_ops`) back to /plan and /apply, and the server interprets them again each time.
"""

import re
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import llm
from .db import connect
from .planner import apply_plan, make_plan
from .tree import load_tree

TREES = Path(__file__).resolve().parent.parent / "trees"
TREES.mkdir(exist_ok=True)

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


class PlanRequest(BaseModel):
    model_ops: list[dict]
    choices: dict[str, int | str] = {}   # "Mary" -> person id or "new"; "meaning:nipote" -> chosen label


class ApplyRequest(PlanRequest):
    sentence: str


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
    people = []
    for p in tree.people.values():
        events = [e for e in tree.events if e.person_id == p.id]
        people.append({
            **asdict(p),
            "born": tree.year(p.id, "birth"),
            "died": tree.year(p.id, "death"),
            "events": [asdict(e) for e in events],
        })
    families = [{
        "id": f.id, "partners": f.partners, "union_type": f.union_type,
        "children": [{"id": c, "relation": r} for c, r in f.children.items()],
        "events": [asdict(e) for e in tree.events if e.family_id == f.id],
    } for f in tree.families.values()]
    return {"people": people, "families": families, "claims": [asdict(c) for c in tree.claims]}


def _plan_json(plan) -> dict:
    data = asdict(plan)
    data.pop("changes")   # internal detail; the summary says the same in plain words
    return data


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
            "plan": _plan_json(_make(tree, result))}


@app.post("/api/trees/{name}/plan")
def replan(name: str, req: PlanRequest):
    with closing(_open(name)) as conn:
        tree = load_tree(conn)
    return {"plan": _plan_json(_make(tree, llm.interpret(req.model_ops), req.choices))}


@app.post("/api/trees/{name}/apply")
def apply(name: str, req: ApplyRequest):
    with closing(_open(name)) as conn:
        plan = _make(load_tree(conn), llm.interpret(req.model_ops), req.choices)
        if plan.status != "save":
            raise HTTPException(409, {"message": "The sentence needs answers or has errors.", "plan": _plan_json(plan)})
        apply_plan(conn, plan, req.sentence)
        return {"saved": plan.summary, "tree": _tree_json(conn)}


def _make(tree, interpreted: dict, choices: dict | None = None):
    plan = make_plan(tree, interpreted["ops"], choices)
    for problem in interpreted["problems"]:
        # never stay silent: say which part of the sentence did not become tree facts
        plan.warnings.append(problem if problem.startswith("I don't know") else "Part of this sentence couldn't be turned into tree facts.")
    return plan


@app.get("/api/health")
def health():
    return {"model": llm.MODEL, "prompt": llm.PROMPT_VERSION}

