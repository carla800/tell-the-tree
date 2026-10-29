"""GEDCOM, the file every genealogy program can open, and the printable register."""

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


def records(ged: str) -> dict:
    """{'@I1@': ['1 NAME ...', ...]} for every level-0 record."""
    out, current = {}, None
    for line in ged.splitlines():
        if line.startswith("0 "):
            parts = line.split()
            current = parts[1]
            out[current] = []
        elif current:
            out[current].append(line)
    return out


def family_shape(tree: dict) -> set:
    """Every link in the tree, by names: couples with their type, and children with their kind of link."""
    name = {p["id"]: p["name"] for p in tree["people"]}
    shape = set()
    for f in tree["families"]:
        partners = frozenset(name[x] for x in f["partners"] if x)
        shape.add(("couple", partners, f["union_type"] if len(partners) == 2 else None))
        for c in f["children"]:
            shape.add(("child", name[c["id"]], partners, c["relation"]))
    return shape


def test_export_is_a_gedcom_other_programs_can_read(client):
    ged = client.get("/api/trees/villa-diodati/export.ged").text
    lines = ged.splitlines()
    assert lines[0] == "0 HEAD" and lines[-1] == "0 TRLR"
    assert "1 SUBM @U1@" in lines and "0 @U1@ SUBM" in lines and "2 VERS 5.5.1" in lines
    assert all(len(line) <= 255 for line in lines)
    recs = records(ged)
    people = {k: v for k, v in recs.items() if k.startswith("@I")}
    sex = {k: next(l.split()[2] for l in v if l.startswith("1 SEX")) for k, v in people.items()}
    for key, lines_ in recs.items():
        if key.startswith("@F"):
            husbands = [l.split()[2] for l in lines_ if l.startswith("1 HUSB")]
            assert not any(sex[h] == "F" for h in husbands), key
    mary = next(v for v in people.values() if "1 NAME Mary /Shelley/" in v)
    assert "1 NAME Mary Wollstonecraft /Godwin/" in mary and "2 TYPE birth" in mary
    assert "2 DATE 30 AUG 1797" in mary                      # stored as 1797-08-30
    assert any(l.startswith("2 SOUR http") for l in mary)    # where each fact comes from travels too
    assert any(l.startswith("1 FAMC") for l in mary) and any(l.startswith("1 FAMS") for l in mary)
    assert "2 _FREL Step" in ged                             # Mary is Mary Jane Godwin's stepdaughter


def test_a_wife_is_exported_as_the_wife(client):
    """Before: the partner written first was always the husband, so Maria became Marco's husband."""
    client.post("/api/trees", json={"name": "rossi"})
    ops = [{"op": "relation", "person": "Maria Rossi", "word": "moglie", "of": ["Marco Rossi"]}]
    client.post("/api/trees/rossi/apply", json={"model_ops": ops, "by_hand": True})
    recs = records(client.get("/api/trees/rossi/export.ged").text)
    maria = next(k for k, v in recs.items() if "1 NAME Maria /Rossi/" in v)
    family = next(v for k, v in recs.items() if k.startswith("@F"))
    assert f"1 WIFE {maria}" in family and "1 MARR Y" in family


def test_export_and_import_give_back_the_same_tree(client):
    before = client.get("/api/trees/villa-diodati").json()
    ged = client.get("/api/trees/villa-diodati/export.ged").content
    assert client.post("/api/gedcom/import/copia", content=ged).status_code == 200
    after = client.get("/api/trees/copia").json()
    person = lambda p: (p["name"], p["birth_name"], p["sex"], sorted((e["type"], e["place"]) for e in p["events"]))  # noqa: E731
    assert sorted(map(person, before["people"])) == sorted(map(person, after["people"]))
    assert family_shape(before) == family_shape(after)
    mary = next(p for p in after["people"] if p["name"] == "Mary Shelley")
    birth = next(e for e in mary["events"] if e["type"] == "birth")
    assert birth["date_text"] == "1797-08-30" and birth["source"].startswith("http")   # exactly as before


FOREIGN = """\
0 HEAD
1 CHAR UTF-8
0 @N1@ NOTE A note kept in its own record
0 @S1@ SOUR
  1 TITL Parish register of Cagliari
0 @I1@ INDI
1 NAME Giovanni /Melis/
1 SEX M
1 BIRT
2 DATE ABT 1890
2 PLAC Cagliari
2 SOUR @S1@
1 NOTE First line
2 CONT second line, which is
2 CONC  long
1 NOTE @N1@
0 @I2@ INDI
1 NAME Anna /Pinna/
1 NAME Anna /Sanna/
2 TYPE maiden
1 SEX F
0 @I3@ INDI
1 NAME Luigi /Melis/
1 FAMC @F1@
2 PEDI adopted
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
1 CHIL @I3@
1 MARR Y
0 TRLR
"""


def test_import_a_gedcom_from_another_program(client):
    r = client.post("/api/gedcom/preview", content=FOREIGN.encode())
    assert r.json() == {"people": 3, "families": 1, "sample": ["Giovanni Melis", "Anna Pinna", "Luigi Melis"]}
    assert client.post("/api/gedcom/import/melis", content=FOREIGN.encode()).status_code == 200
    tree = client.get("/api/trees/melis").json()
    people = {p["name"]: p for p in tree["people"]}
    giovanni = people["Giovanni Melis"]
    assert giovanni["notes"] == "First line\nsecond line, which is long\nA note kept in its own record"
    birth = giovanni["events"][0]
    assert (birth["date_text"], birth["place"], birth["source"]) == ("about 1890", "Cagliari", "Parish register of Cagliari")
    assert people["Anna Pinna"]["birth_name"] == "Anna Sanna" and people["Anna Pinna"]["sex"] == "F"
    family = tree["families"][0]
    assert family["union_type"] == "marriage" and family["children"] == [{"id": people["Luigi Melis"]["id"], "relation": "adopted"}]


def test_gedcom_problems_are_explained_in_the_interface_language(client):
    r = client.post("/api/gedcom/preview?lang=it", content=b"0 HEAD\nthis is not gedcom\n")
    assert r.status_code == 400 and r.json()["detail"] == "La riga 2 non è una riga GEDCOM."
    r = client.post("/api/gedcom/preview", content=b"0 HEAD\n0 TRLR\n")
    assert r.json()["detail"] == "This GEDCOM has no people in it."
    r = client.post("/api/gedcom/import/villa-diodati?lang=it", content=FOREIGN.encode())
    assert r.status_code == 409 and r.json()["detail"] == 'Esiste già un albero chiamato "villa-diodati".'
    assert "broken" not in client.get("/api/trees").json()
    assert client.post("/api/gedcom/import/broken", content=b"nonsense").status_code == 400
    assert "broken" not in client.get("/api/trees").json()      # nothing is created from a bad file


def test_the_register_pdf_in_both_languages(client):
    for lang in ("en", "it"):
        r = client.get(f"/api/trees/villa-diodati/export.pdf?lang={lang}&title=Godwin%E2%80%93Shelley%E2%80%93Byron")
        assert r.status_code == 200 and r.content.startswith(b"%PDF") and len(r.content) > 20_000
    client.post("/api/trees", json={"name": "vuoto"})
    assert client.get("/api/trees/vuoto/export.pdf?lang=it").content.startswith(b"%PDF")
