"""The interface in Italian, and a photo for each person."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import api, llm
from backend.messages import MESSAGES, TERMS
from backend.seed import seed

ROOT = Path(__file__).resolve().parent.parent
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d4944415478da63f8ffff3f0005fe02fea7d5a1000000"
    "0049454e44ae426082"
)


def test_every_message_has_the_same_blanks_in_every_language():
    for key, (en, it) in MESSAGES.items():
        assert set(re.findall(r"{(\w+)}", en)) == set(re.findall(r"{(\w+)}", it)), key
    assert set(TERMS["en"]) == set(TERMS["it"])


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "TREES", tmp_path)
    seed(ROOT / "data" / "villa-diodati.yaml", tmp_path / "villa-diodati.db")
    return TestClient(api.app)


def plan_for(client, model_ops, lang, choices=None):
    body = {"model_ops": model_ops, "lang": lang, "choices": choices or {}}
    return client.post("/api/trees/villa-diodati/plan", json=body).json()["plan"]


def test_the_plan_speaks_the_interface_language(client):
    ops = [{"op": "relation", "person": "Jane St John", "word": "wife", "of": ["Percy Florence Shelley"]},
           {"op": "event", "partners": ["Percy Florence Shelley", "Jane St John"], "type": "marriage", "date": "1848"}]
    assert "New person: Jane St John" in plan_for(client, ops, "en")["summary"]
    it = plan_for(client, ops, "it")["summary"]
    assert "Nuova persona: Jane St John" in it
    assert "Percy Florence Shelley e Jane St John: matrimonio (1848)" in it


def test_errors_and_questions_in_italian(client):
    wrong = [{"op": "relation", "person": "Ada Lovelace", "word": "mother", "of": ["Lord Byron"]}]
    assert "è già un antenato" in plan_for(client, wrong, "it")["errors"][0]
    nipote = [{"op": "relation", "person": "Giulia", "word": "nipote", "of": ["Lucia"]}]
    question = plan_for(client, nipote, "it")["questions"][0]
    assert {o["id"] for o in question["options"]} == {"grandchild", "niece_nephew"}
    assert any(o["label"].startswith("nipote di nonno") for o in question["options"])
    # the answer is the meaning's id, whatever the language
    assert plan_for(client, nipote, "it", {"meaning:nipote": "grandchild"})["status"] == "save"


def test_unknown_word_warning_in_italian(client):
    ops = [{"op": "relation", "person": "Rita", "word": "madrina", "of": ["Ugo"]}]
    assert any(w.startswith('Non conosco la parentela "madrina"') for w in plan_for(client, ops, "it")["warnings"])


def test_a_photo_for_a_person(client):
    tree = client.get("/api/trees/villa-diodati").json()
    mary = next(p for p in tree["people"] if p["name"] == "Mary Shelley")
    assert mary["photo"] is None
    url = f"/api/trees/villa-diodati/people/{mary['id']}/photo"

    r = client.put(url, content=TINY_PNG, headers={"Content-Type": "image/png"})
    assert r.status_code == 200 and r.json()["photo"]
    got = client.get(url)
    assert got.content == TINY_PNG and got.headers["content-type"] == "image/png"
    mary = next(p for p in client.get("/api/trees/villa-diodati").json()["people"] if p["id"] == mary["id"])
    assert mary["photo"]

    assert client.delete(url).status_code == 200
    assert client.get(url).status_code == 404


def test_only_real_pictures_are_accepted(client):
    url = "/api/trees/villa-diodati/people/1/photo"
    # a text file that says it's a picture
    assert client.put(url, content=b"not a picture", headers={"Content-Type": "image/jpeg"}).status_code == 415
    assert client.put("/api/trees/villa-diodati/people/9999/photo", content=TINY_PNG).status_code == 404
    too_big = b"\xff\xd8\xff" + b"0" * api.PHOTO_MAX_BYTES
    assert client.put(url, content=too_big).status_code == 413
