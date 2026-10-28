"""Tests for the code side: derived relationships and the planner.

These run without Gemma: the planner gets the *expected* operations from
tests/sentences.yaml, so a failure here is always a bug in our code.

    python -m pytest
"""

from pathlib import Path

import pytest
import yaml

from backend.db import connect
from backend.ops import normalize_ops
from backend.planner import apply_plan, make_plan
from backend.seed import seed
from backend.tree import Tree, load_tree
from evals.scoring import expected_statuses

ROOT = Path(__file__).resolve().parent.parent
CASES = yaml.safe_load((ROOT / "tests" / "sentences.yaml").read_text(encoding="utf-8"))["dev"]


@pytest.fixture(scope="module")
def villa(tmp_path_factory):
    conn, ids = seed(ROOT / "data" / "villa-diodati.yaml", tmp_path_factory.mktemp("trees") / "villa.db")
    return load_tree(conn), ids


def test_demo_data_relationships(villa):
    tree, ids = villa
    data = yaml.safe_load((ROOT / "data" / "villa-diodati.yaml").read_text(encoding="utf-8"))
    expected = {
        ("mary-shelley", "fanny-imlay"): ("sibling", "half"),
        ("mary-shelley", "claire-clairmont"): ("sibling", "step"),
        ("mary-shelley", "william-godwin-jr"): ("sibling", "half"),
        ("claire-clairmont", "william-godwin-jr"): ("sibling", "half"),
        ("ada-lovelace", "allegra-byron"): ("sibling", "half"),
        ("percy-florence-shelley", "william-godwin"): ("grandchild", None),
        ("percy-florence-shelley", "ianthe-shelley"): ("sibling", "half"),
        ("allegra-byron", "mary-shelley"): ("niece_nephew", "step"),
    }
    # every derived_check in the YAML has a machine-readable expectation here
    assert {(c["a"], c["b"]) for c in data["derived_checks"]} == set(expected)
    for (a, b), rel in expected.items():
        assert tree.relation(ids[a], ids[b]) == rel, (a, b)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_planner_on_expected_ops(case, villa):
    tree = villa[0] if case["tree"] == "villa-diodati" else Tree()
    ops, problems = normalize_ops(case["expected_ops"])
    assert not problems
    plan = make_plan(tree, ops)
    assert plan.status in expected_statuses(case["expect_code"]), (plan.errors, plan.questions, plan.summary)


def test_ambiguous_names_are_asked_not_guessed(villa):
    tree, ids = villa
    ops, _ = normalize_ops([{"op": "union", "partners": ["Percy", "Mary"], "type": "marriage"}])
    plan = make_plan(tree, ops)
    asked = {q["name"]: {c["name"] for c in q["candidates"]} for q in plan.questions}
    assert asked["Percy"] == {"Percy Bysshe Shelley", "Percy Florence Shelley"}
    assert "Mary Shelley" in asked["Mary"] and "Mary Wollstonecraft" in asked["Mary"]
    # once the user picks, the same sentence goes through
    plan = make_plan(tree, ops, choices={"Percy": ids["percy-shelley"], "Mary": ids["mary-shelley"]})
    assert plan.status == "save"
    assert any("already a couple" in k for k in plan.known)


def test_impossible_parent_is_rejected_with_a_reason(villa):
    tree, _ = villa
    ops, _ = normalize_ops([{"op": "child", "child": "Lord Byron", "parents": ["Ada Lovelace"]}])
    plan = make_plan(tree, ops)
    assert plan.status == "reject"
    assert "ancestor" in plan.errors[0]


def test_siblings_get_parents_later(tmp_path):
    """'Marco e Roberta sono fratelli', then their parents: the same family is filled in."""
    conn = connect(tmp_path / "rossi.db")
    steps = [
        [{"op": "siblings", "people": ["Marco", "Roberta"], "kind": "unspecified"}],
        [{"op": "child", "child": "Marco", "parents": ["Maria Rossi", "Giovanni Rossi"]}],
    ]
    for raw in steps:
        ops, _ = normalize_ops(raw)
        plan = make_plan(load_tree(conn), ops)
        assert plan.status == "save", plan.errors
        apply_plan(conn, plan, "test")
    tree = load_tree(conn)
    by_name = {p.name: p.id for p in tree.people.values()}
    assert tree.relation(by_name["Roberta"], by_name["Maria Rossi"]) == ("child", None)
    assert tree.sibling_kind(by_name["Marco"], by_name["Roberta"]) == "full"


def test_apply_keeps_the_source_sentence(tmp_path):
    conn = connect(tmp_path / "t.db")
    sentence = "Roberta è nata a Padova nel 1960, poi si è trasferita a Parigi."
    ops, _ = normalize_ops([
        {"op": "event", "person": "Roberta", "type": "birth", "date": "1960", "place": "Padova"},
        {"op": "event", "person": "Roberta", "type": "residence", "place": "Parigi"},
    ])
    apply_plan(conn, make_plan(load_tree(conn), ops), sentence)
    rows = conn.execute("SELECT type, place, source FROM event ORDER BY id").fetchall()
    assert [(r["type"], r["place"]) for r in rows] == [("birth", "Padova"), ("residence", "Parigi")]
    assert sentence in rows[0]["source"]


def test_birth_after_death_is_rejected(villa):
    tree, _ = villa
    ops, _ = normalize_ops([{"op": "event", "person": "Ada Lovelace", "type": "death", "date": "1801"}])
    assert make_plan(tree, ops).status == "reject"


def test_date_parts_read_the_same_day_written_differently():
    from backend.tree import date_parts
    assert date_parts("1816-12-30") == date_parts("30 December 1816") == date_parts("30 dicembre 1816") == (1816, 12, 30)
    assert date_parts("December 1816") == (1816, 12, None)
    assert date_parts("about 1815") == (1815, None, None)
    assert date_parts(None) == (None, None, None)


def test_an_event_already_in_the_tree_is_not_added_twice(villa):
    """The demo data stores the wedding as 1816-12-30; the sentence says 30 December 1816."""
    tree, ids = villa
    choices = {"Percy": ids["percy-shelley"], "Mary": ids["mary-shelley"]}
    same = [{"op": "event", "partners": ["Percy", "Mary"], "type": "marriage", "date": "30 December 1816"}]
    plan = make_plan(tree, normalize_ops(same)[0], choices=choices)
    assert plan.status == "save" and plan.changes == []
    assert any("already in the tree" in k for k in plan.known)
    # a new detail is still added
    other = [{"op": "event", "person": "Mary Shelley", "type": "residence", "place": "Villa Diodati"}]
    assert make_plan(tree, normalize_ops(other)[0]).changes
