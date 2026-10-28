"""Pipeline tests with a fake Gemma: they check our plumbing, not the model."""

import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from backend import api, llm
from backend.planner import make_plan
from backend.seed import seed
from backend.tree import Tree, load_tree
from evals.scoring import score_ops

ROOT = Path(__file__).resolve().parent.parent
DEV = yaml.safe_load((ROOT / "tests" / "sentences.yaml").read_text(encoding="utf-8"))["dev"]
CASES = {c["sentence"]: c for c in DEV}
IDEAL = yaml.safe_load((ROOT / "tests" / "model_answers.yaml").read_text(encoding="utf-8"))


def perfect_gemma(model, messages, format, think, options):
    """Answers every dev sentence with the ideal answer."""
    case = CASES[messages[-1]["content"]]
    return {"message": {"content": json.dumps({"ops": IDEAL[case["id"]]})}}


@pytest.mark.parametrize("case", DEV, ids=[c["id"] for c in DEV])
def test_ideal_answer_becomes_the_expected_tree_ops(case):
    """A perfect Gemma + our dictionary = the expected operations. Failures here are dictionary bugs."""
    result = llm.interpret(IDEAL[case["id"]])
    assert not result["problems"]
    score = score_ops(case["expected_ops"], result["ops"])
    assert score["ok"], score


@pytest.fixture(scope="module")
def villa_tree(tmp_path_factory):
    conn, _ = seed(ROOT / "data" / "villa-diodati.yaml", tmp_path_factory.mktemp("t") / "v.db")
    return load_tree(conn)


@pytest.mark.parametrize("case", DEV, ids=[c["id"] for c in DEV])
def test_ideal_answer_gets_the_expected_save_ask_reject(case, villa_tree):
    tree = villa_tree if case["tree"] == "villa-diodati" else Tree()
    plan = make_plan(tree, llm.interpret(IDEAL[case["id"]])["ops"])
    assert plan.status == {"save": "save", "ask_which": "ask", "reject": "reject"}[case["expect_code"]]


def test_nipote_is_read_from_the_tree_when_possible(villa_tree):
    # Percy Florence is William Godwin's grandson in the tree: no need to ask
    ops = llm.interpret([{"op": "relation", "person": "Percy Florence Shelley", "word": "nipote", "of": ["William Godwin"]}])["ops"]
    plan = make_plan(villa_tree, ops)
    assert plan.status == "save" and not plan.changes
    assert any("grandchild" in k for k in plan.known)


def test_nipote_is_asked_when_the_tree_cant_tell():
    ops = llm.interpret([{"op": "relation", "person": "Giulia", "word": "nipote", "of": ["Lucia"]}])["ops"]
    plan = make_plan(Tree(), ops)
    assert plan.status == "ask"
    question = plan.questions[0]
    assert question["kind"] == "meaning" and question["word"] == "nipote" and len(question["options"]) == 2
    # once the user picks a meaning, it saves
    plan = make_plan(Tree(), ops, choices={"meaning:nipote": question["options"][0]})
    assert plan.status == "save"


def test_scoring():
    expected = [{"op": "union", "partners": ["Maria Rossi", "Marco Rossi"], "type": "marriage"}]
    same = [{"op": "union", "partners": ["marco rossi", "Maria Rossi"], "type": "marriage"},
            {"op": "person", "name": "Maria Rossi", "sex": "F"}]
    assert score_ops(expected, same)["ok"]
    assert not score_ops(expected, [])["ok"]
    assert not score_ops([], [{"op": "event", "person": "Byron", "type": "residence"}])["ok"]


def test_parse_sentence_survives_broken_json(monkeypatch):
    monkeypatch.setattr(llm.ollama, "chat", lambda **kw: {"message": {"content": '{"ops": [{"op": "rel'}})
    result = llm.parse_sentence("Marco e Roberta sono fratelli.")
    assert result["ops"] == [] and "invalid JSON" in result["problems"][0]


def test_prompt_examples_are_not_test_sentences():
    examples = {e for e, _ in llm.EXAMPLES}
    assert not examples & set(CASES)


def test_prompt_examples_use_known_words():
    for _, answer in llm.EXAMPLES:
        assert not llm.interpret(answer["ops"])["problems"]


def test_schema_allows_every_correct_answer():
    """The schema forces Gemma's shape. It must never forbid a right answer."""
    jsonschema = pytest.importorskip("jsonschema")
    answers = [answer for _, answer in llm.EXAMPLES] + [{"ops": ops} for ops in IDEAL.values()]
    for answer in answers:
        jsonschema.validate(answer, llm.SCHEMA)


def test_schema_refuses_incomplete_operations():
    jsonschema = pytest.importorskip("jsonschema")
    mistakes = [
        {"op": "event", "person": "Roberta", "date": "1960", "place": "Padova"},          # no type
        {"op": "relation", "person": "Ada", "of": ["Byron"]},                              # no word
        {"op": "relation", "person": "Ada", "word": "daughter", "of": ["A", "B", "C"]},    # three parents
        {"op": "union", "partners": ["Marco", "Maria"], "type": "marriage"},               # not Gemma's format any more
    ]
    for op in mistakes:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({"ops": [op]}, llm.SCHEMA)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "TREES", tmp_path)
    monkeypatch.setattr(llm.ollama, "chat", perfect_gemma)
    seed(ROOT / "data" / "villa-diodati.yaml", tmp_path / "villa-diodati.db")
    return TestClient(api.app)


def test_api_full_flow(client):
    assert client.get("/api/trees").json() == ["villa-diodati"]
    assert client.post("/api/trees", json={"name": "rossi"}).status_code == 200

    sentence = "Maria Rossi è la moglie di Marco Rossi."
    r = client.post("/api/trees/rossi/parse", json={"sentence": sentence}).json()
    assert r["plan"]["status"] == "save"
    saved = client.post("/api/trees/rossi/apply", json={"sentence": sentence, "model_ops": r["model_ops"]})
    assert saved.status_code == 200
    people = {p["name"]: p for p in saved.json()["tree"]["people"]}
    assert set(people) == {"Maria Rossi", "Marco Rossi"}
    assert people["Maria Rossi"]["sex"] == "F"   # from the word "moglie"


def test_api_asks_then_saves(client):
    sentence = "Percy married Mary on 30 December 1816."
    r = client.post("/api/trees/villa-diodati/parse", json={"sentence": sentence}).json()
    assert r["plan"]["status"] == "ask"
    # can't save before answering
    assert client.post("/api/trees/villa-diodati/apply", json={"sentence": sentence, "model_ops": r["model_ops"]}).status_code == 409
    pick = {q["name"]: next(c["id"] for c in q["candidates"] if c["name"] in ("Percy Bysshe Shelley", "Mary Shelley"))
            for q in r["plan"]["questions"]}
    plan = client.post("/api/trees/villa-diodati/plan", json={"model_ops": r["model_ops"], "choices": pick}).json()["plan"]
    assert plan["status"] == "save"
    body = {"sentence": sentence, "model_ops": r["model_ops"], "choices": pick}
    assert client.post("/api/trees/villa-diodati/apply", json=body).status_code == 200


def test_api_rejects_impossible(client):
    r = client.post("/api/trees/villa-diodati/parse", json={"sentence": "Ada Lovelace was Lord Byron's mother."}).json()
    assert r["plan"]["status"] == "reject" and r["plan"]["errors"]


def test_api_warns_about_unknown_words(client):
    model_ops = [{"op": "relation", "person": "Rita", "word": "madrina", "of": ["Ugo"]}]
    plan = client.post("/api/trees/villa-diodati/plan", json={"model_ops": model_ops}).json()["plan"]
    assert any("madrina" in w for w in plan["warnings"])


def test_bad_tree_name(client):
    assert client.get("/api/trees/../secret").status_code in (400, 404)
    assert client.post("/api/trees", json={"name": "Bad Name!"}).status_code == 400
