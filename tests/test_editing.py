"""Editing and deleting by hand: the same checks as a sentence, and people are never lost by accident."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import api
from backend.seed import seed

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "TREES", tmp_path)
    seed(ROOT / "data" / "villa-diodati.yaml", tmp_path / "villa-diodati.db")
    return TestClient(api.app)


def people(client):
    return {p["name"]: p for p in client.get("/api/trees/villa-diodati").json()["people"]}


def edit(client, person, lang="en", **changes):
    first = lambda kind: next((e for e in person["events"] if e["type"] == kind), {})  # noqa: E731
    body = {"name": person["name"], "sex": person["sex"], "lang": lang,
            "birth_date": first("birth").get("date_text"), "birth_place": first("birth").get("place"),
            "death_date": first("death").get("date_text"), "death_place": first("death").get("place"), **changes}
    return client.put(f"/api/trees/villa-diodati/people/{person['id']}", json=body)


def test_edit_checks_the_dates_like_a_sentence(client):
    allegra = people(client)["Allegra Byron"]
    r = edit(client, allegra, death_date="1700")
    assert r.status_code == 409
    assert "Allegra Byron was born in 1817, so can't die in 1700." in r.json()["detail"]["errors"]
    # in Italian too
    r = edit(client, allegra, lang="it", birth_date="1780")      # her father Byron was born in 1788
    assert "Lord Byron (nascita: 1788) non può essere genitore di Allegra Byron (nascita: 1780)." in r.json()["detail"]["errors"]
    # a parent who died long before the child was born
    r = edit(client, people(client)["Lord Byron"], death_date="1810")   # Ada was born in 1815
    assert any("Ada Lovelace" in e for e in r.json()["detail"]["errors"])


def test_an_edit_is_marked_as_made_by_hand(client):
    mary = people(client)["Mary Shelley"]
    assert edit(client, mary, birth_place="Somers Town, London, England").status_code == 200
    birth = next(e for e in people(client)["Mary Shelley"]["events"] if e["type"] == "birth")
    assert birth["place"] == "Somers Town, London, England" and birth["source"] == "By hand"
    # an unchanged event keeps its source
    death = next(e for e in people(client)["Mary Shelley"]["events"] if e["type"] == "death")
    assert death["source"].startswith("http")


def test_clearing_a_date_and_place_removes_the_event(client):
    fanny = people(client)["Fanny Imlay"]
    assert edit(client, fanny, death_date="", death_place="").status_code == 200
    assert not any(e["type"] == "death" for e in people(client)["Fanny Imlay"]["events"])


def test_removing_a_link_keeps_the_people(client):
    tree = client.get("/api/trees/villa-diodati").json()
    ids = {p["name"]: p["id"] for p in tree["people"]}
    byron_couple = next(f for f in tree["families"] if set(f["partners"]) == {ids["Lord Byron"], ids["Anne Isabella Milbanke"]})
    r = client.post("/api/trees/villa-diodati/relations/remove",
                    json={"action": "remove_child", "family_id": byron_couple["id"], "person_id": ids["Ada Lovelace"]})
    tree = r.json()
    assert "Ada Lovelace" in {p["name"] for p in tree["people"]}
    assert not any(ids["Ada Lovelace"] in [c["id"] for c in f["children"]] for f in tree["families"])
    # the couple still has its wedding, so the family stays
    assert any(f["id"] == byron_couple["id"] for f in tree["families"])
    # links can only be removed here: new links go through a sentence or "Add a relative"
    assert client.post("/api/trees/villa-diodati/relations/remove",
                       json={"action": "add_child", "family_id": byron_couple["id"], "person_id": ids["Ada Lovelace"]}).status_code == 400


def test_deleting_a_person_keeps_their_relatives(client):
    ids = {p: v["id"] for p, v in people(client).items()}
    tree = client.delete(f"/api/trees/villa-diodati/people/{ids['Allegra Byron']}").json()
    names = {p["name"] for p in tree["people"]}
    assert "Allegra Byron" not in names and {"Lord Byron", "Claire Clairmont"} <= names
    # Byron and Claire are still a couple ("together, not married"), even without Allegra
    couple = next(f for f in tree["families"] if set(f["partners"]) == {ids["Lord Byron"], ids["Claire Clairmont"]})
    assert couple["union_type"] == "partnership" and couple["children"] == []


def test_trees_can_be_deleted_but_not_the_demo(client):
    assert client.post("/api/trees", json={"name": "prova"}).status_code == 200
    assert client.delete("/api/trees/prova").status_code == 200
    assert "prova" not in client.get("/api/trees").json()
    assert client.delete("/api/trees/villa-diodati").status_code == 403
    assert client.delete("/api/trees/..%2Fsecret").status_code in (400, 404)
