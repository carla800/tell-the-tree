"""Pipeline tests with a fake Gemma: they check our plumbing, not the model."""

import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from backend import api, llm
from backend.seed import seed
from evals.scoring import score_ops

ROOT = Path(__file__).resolve().parent.parent
CASES = {c["sentence"]: c for c in yaml.safe_load((ROOT / "tests" / "sentences.yaml").read_text(encoding="utf-8"))["dev"]}


def perfect_gemma(model, messages, format, think, options):
    """Answers every dev sentence with exactly the expected ops."""
    case = CASES[messages[-1]["content"]]
    return {"message": {"content": json.dumps({"ops": case["expected_ops"]})}}


def test_scoring():
    expected = [{"op": "union", "partners": ["Maria Rossi", "Marco Rossi"], "type": "marriage"}]
    same = [{"op": "union", "partners": ["marco rossi", "Maria Rossi"], "type": "marriage"},
            {"op": "person", "name": "Maria Rossi", "sex": "F"}]
    assert score_ops(expected, same)["ok"]
    assert not score_ops(expected, [])["ok"]
    assert not score_ops([], [{"op": "event", "person": "Byron", "type": "residence"}])["ok"]


def test_parse_sentence_survives_broken_json(monkeypatch):
    monkeypatch.setattr(llm.ollama, "chat", lambda **kw: {"message": {"content": '{"ops": [{"op": "chi'}})
    result = llm.parse_sentence("Marco e Roberta sono fratelli.")
    assert result["ops"] == [] and "invalid JSON" in result["problems"][0]


def test_prompt_examples_are_not_test_sentences():
    examples = {e for e, _ in llm.EXAMPLES}
    assert not examples & set(CASES)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "TREES", tmp_path)
    monkeypatch.setattr(llm.ollama, "chat", perfect_gemma)
    seed(ROOT / "data" / "villa-diodati.yaml", tmp_path / "villa-diodati.db")
    return TestClient(api.app)


def test_api_full_flow(client):
    assert client.get("/api/trees").json() == ["villa-diodati"]
    assert client.post("/api/trees", json={"name": "rossi"}).status_code == 200

    # a sentence that saves straight away
    r = client.post("/api/trees/rossi/parse", json={"sentence": "Maria Rossi è la moglie di Marco Rossi."}).json()
    assert r["plan"]["status"] == "save"
    saved = client.post("/api/trees/rossi/apply", json={"sentence": "Maria Rossi è la moglie di Marco Rossi.", "ops": r["ops"]})
    assert saved.status_code == 200
    assert {p["name"] for p in saved.json()["tree"]["people"]} == {"Maria Rossi", "Marco Rossi"}


def test_api_asks_then_saves(client):
    sentence = "Percy married Mary on 30 December 1816."
    r = client.post("/api/trees/villa-diodati/parse", json={"sentence": sentence}).json()
    assert r["plan"]["status"] == "ask"
    # can't save before answering
    assert client.post("/api/trees/villa-diodati/apply", json={"sentence": sentence, "ops": r["ops"]}).status_code == 409
    pick = {q["name"]: next(c["id"] for c in q["candidates"] if c["name"] in ("Percy Bysshe Shelley", "Mary Shelley"))
            for q in r["plan"]["questions"]}
    plan = client.post("/api/trees/villa-diodati/plan", json={"ops": r["ops"], "choices": pick}).json()["plan"]
    assert plan["status"] == "save"
    assert client.post("/api/trees/villa-diodati/apply", json={"sentence": sentence, "ops": r["ops"], "choices": pick}).status_code == 200


def test_api_rejects_impossible(client):
    r = client.post("/api/trees/villa-diodati/parse", json={"sentence": "Ada Lovelace was Lord Byron's mother."}).json()
    assert r["plan"]["status"] == "reject" and r["plan"]["errors"]


def test_bad_tree_name(client):
    assert client.get("/api/trees/../secret").status_code in (400, 404)
    assert client.post("/api/trees", json={"name": "Bad Name!"}).status_code == 400
