"""The relation-word dictionary: the part of the app that decides what a word means."""

import pytest

from backend.words import read_word, to_tree_ops


def meaning(word):
    r = read_word(word)
    assert len(r.meanings) == 1, (word, r.meanings)
    m = r.meanings[0]
    return m.category, (m.kind if m.category in ("sibling", "hint") else m.relation if m.category in ("parent", "child") else m.union_type)


@pytest.mark.parametrize("word, expected", [
    # parents and children
    ("mother", ("parent", "birth")), ("madre", ("parent", "birth")), ("papà", ("parent", "birth")),
    ("daughter", ("child", "birth")), ("figlio", ("child", "birth")), ("their only child", ("child", "birth")),
    ("figlio adottivo", ("child", "adopted")), ("adoptive mother", ("parent", "adopted")),
    # words that contain other words
    ("grandson", ("hint", "grandchild")), ("granddaughter", ("hint", "grandchild")),
    ("grandmother", ("hint", "grandparent")), ("nonna", ("hint", "grandparent")),
    ("stepmother", ("parent", "step")), ("step-son", ("child", "step")), ("matrigna", ("parent", "step")),
    ("mother-in-law", ("hint", "in_law")), ("suocera", ("hint", "in_law")), ("cognato", ("hint", "in_law")),
    ("great-grandfather", ("hint", "other")), ("bisnonno", ("hint", "other")),
    # siblings
    ("sister", ("sibling", "unspecified")), ("fratelli", ("sibling", "unspecified")),
    ("half-sister", ("sibling", "half")), ("stepsister", ("sibling", "step")),
    ("half-sister on her mother's side", ("sibling", "half")), ("sorella da parte di madre", ("sibling", "half")),
    ("fratellastro da parte di padre", ("sibling", "half")), ("twin", ("sibling", "full")), ("gemella", ("sibling", "full")),
    # couples
    ("wife", ("couple", "marriage")), ("moglie", ("couple", "marriage")), ("sposò", ("couple", "marriage")),
    ("married", ("couple", "marriage")), ("never married", ("couple", "partnership")),
    ("non erano sposati", ("couple", "partnership")), ("compagna", ("couple", "partnership")),
    # wider family
    ("uncle", ("hint", "aunt_uncle")), ("zia", ("hint", "aunt_uncle")), ("niece", ("hint", "niece_nephew")),
    ("cugina", ("hint", "cousin")),
])
def test_word_meanings(word, expected):
    assert meaning(word) == expected


@pytest.mark.parametrize("word, labels", [
    ("nipote", {"grandchild", "niece_nephew"}),
    ("nipoti", {"grandchild", "niece_nephew"}),
    ("sorellastra", {"half", "step"}),
    ("fratellastro", {"half", "step"}),
])
def test_ambiguous_italian_words(word, labels):
    r = read_word(word)
    assert r.ambiguous
    assert {m.kind for m in r.meanings} == labels


@pytest.mark.parametrize("word, sex", [
    ("mother", "F"), ("daughter", "F"), ("half-sister on her mother's side", "F"), ("moglie", "F"),
    ("son", "M"), ("grandson", "M"), ("half-brother on the mother's side", "M"), ("marito", "M"),
    ("fratelli", None), ("nipote", None), ("sposò", None), ("married", None),
])
def test_sex_from_word(word, sex):
    assert read_word(word).sex == sex


def test_unknown_words():
    assert read_word("godmother").meanings == []
    assert read_word("best friend").meanings == []


def test_two_parents_in_one_relation():
    ops, problems = to_tree_ops([{"op": "relation", "person": "Ada", "word": "daughter", "of": ["Byron", "Annabella"]}])
    assert not problems
    assert {"op": "child", "child": "Ada", "parents": ["Byron", "Annabella"], "relation": "birth"} in ops
    assert {"op": "person", "name": "Ada", "sex": "F"} in ops


def test_two_relations_for_the_same_child_are_merged():
    ops, _ = to_tree_ops([
        {"op": "relation", "person": "Ada", "word": "daughter", "of": ["Byron"]},
        {"op": "relation", "person": "Ada", "word": "daughter", "of": ["Annabella"]},
    ])
    children = [o for o in ops if o["op"] == "child"]
    assert children == [{"op": "child", "child": "Ada", "parents": ["Byron", "Annabella"], "relation": "birth"}]


def test_parent_of_two_children():
    ops, _ = to_tree_ops([{"op": "relation", "person": "Elena", "word": "madre", "of": ["Paolo", "Giulia"]}])
    assert [o["child"] for o in ops if o["op"] == "child"] == ["Paolo", "Giulia"]


def test_unknown_word_is_reported_not_dropped():
    ops, problems = to_tree_ops([{"op": "relation", "person": "Rita", "word": "madrina", "of": ["Ugo"]}])
    assert ops == [] and "madrina" in problems[0]
