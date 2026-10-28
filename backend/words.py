"""Relation words -> tree operations, in English and Italian.

Gemma copies the relation word exactly as it appears in the sentence ("half-sister on her
mother's side", "figlio adottivo", "nipote"). This module decides what the word means.
A small model is good at copying and bad at classifying; plain code is the opposite.

Some words have more than one meaning. In Italian, "nipote" is both a grandchild and a
niece/nephew, and "fratellastro" / "sorellastra" can be a half- or a step-sibling.
Those become an `ambiguous` operation: the planner checks whether the tree already
explains one of the meanings, and otherwise asks the user.
"""

import re
import unicodedata
from dataclasses import dataclass, field


@dataclass
class Meaning:
    category: str                 # couple | parent | child | sibling | hint
    union_type: str = "marriage"  # couple
    relation: str = "birth"       # parent / child: birth | adopted | step
    kind: str = "unspecified"     # sibling: full | half | step | unspecified; hint: grandparent ...
    shared_parent: str | None = None
    label: str = ""


@dataclass
class Reading:
    """What a word means: one meaning, several possible meanings, or nothing we know."""
    meanings: list = field(default_factory=list)
    sex: str | None = None        # sex of the person the word describes, when the word says it

    @property
    def ambiguous(self) -> bool:
        return len(self.meanings) > 1


def normalize(word: str) -> str:
    text = unicodedata.normalize("NFKD", word.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.replace("’", "'")).strip()


SIDE_MOTHER = r"mother'?s side|maternal|da parte di madre|per parte di madre|da parte materna|lato materno|stessa madre|same mother"
SIDE_FATHER = r"father'?s side|paternal|da parte di padre|per parte di padre|da parte paterna|lato paterno|stesso padre|same father"
ADOPTED = r"adopt|adottiv"

FEMALE = (r"mother|\bmom\b|\bmum\b|madre|mamma|daughter|\bfigli[ae]\b|figliastra|sister|sorell|wife|moglie|nonna|aunt|"
          r"\bzia\b|niece|matrigna|cugina|cognata|suocera|nuora|compagna|fidanzata|girlfriend|gemella")
MALE = (r"father|\bdad\b|padre|\bpapa\b|babbo|\bson\b|stepson|grandson|\bfiglio\b|figliastro|brother|\bfratello\b|"
        r"fratellastro|husband|marito|nonno|uncle|\bzio\b|nephew|patrigno|cugino|cognato|suocero|genero|"
        r"compagno|fidanzato|boyfriend|gemello")

HALF = Meaning("sibling", kind="half", label="half-sibling (one parent in common)")
STEP = Meaning("sibling", kind="step", label="step-sibling (their parents married each other)")
GRANDCHILD = Meaning("hint", kind="grandchild", label="grandchild (a child's child)")
NIECE = Meaning("hint", kind="niece_nephew", label="niece or nephew (a sibling's child)")


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text) is not None


def read_word(word: str) -> Reading:
    text = normalize(word)
    side = "mother" if _has(SIDE_MOTHER, text) else "father" if _has(SIDE_FATHER, text) else None
    adopted = _has(ADOPTED, text)
    # remove qualifiers so that "sister on her mother's side" isn't read as "mother"
    core = re.sub(f"{SIDE_MOTHER}|{SIDE_FATHER}", " ", text)
    sex = "F" if _has(FEMALE, core) else "M" if _has(MALE, core) else None
    meaning = _meaning(core, side, adopted)
    if meaning is None:
        return Reading([], sex)
    return Reading(meaning if isinstance(meaning, list) else [meaning], sex)


def _meaning(t: str, side: str | None, adopted: bool):
    # Order matters: longer and compound words before the words they contain.
    if _has(r"never married|not married|unmarried|mai sposat|non sposat|non erano sposat", t):
        return Meaning("couple", union_type="partnership")
    if _has(r"in-law|in law|cognat|suocer|\bgenero\b|\bnuora\b", t):
        return Meaning("hint", kind="in_law")
    if _has(r"godmother|godfather|godson|goddaughter|godparent|padrin|madrin|figliocc", t):
        return None   # godparents are not part of the tree
    if _has(r"great|bisnonn|trisnonn|pronipot|\bavo\b|\bava\b|antenat", t):
        return Meaning("hint", kind="other")
    if _has(r"grandmother|grandfather|grandparent|grandma|grandpa|granny|\bnonn[oaie]\b", t):
        return Meaning("hint", kind="grandparent")
    if _has(r"grand[- ]?(son|daughter|child|children|kid)", t):
        return Meaning("hint", kind="grandchild")
    if _has(r"\bnipot[ei]\b", t):
        return [GRANDCHILD, NIECE]
    if _has(r"nephew|niece", t):
        return Meaning("hint", kind="niece_nephew")
    if _has(r"uncle|aunt|\bzi[oaie]\b", t):
        return Meaning("hint", kind="aunt_uncle")
    if _has(r"cousin|cugin", t):
        return Meaning("hint", kind="cousin")
    if _has(r"step[- ]?(mother|father|parent|mom|dad|mum)|matrign|patrign", t):
        return Meaning("parent", relation="step")
    if _has(r"step[- ]?(son|daughter|child|children|kid)|figliastr", t):
        return Meaning("child", relation="step")
    if _has(r"step[- ]?(brother|sister|sibling)", t):
        return Meaning("sibling", kind="step")
    if _has(r"half[- ]?(brother|sister|sibling)", t):
        return Meaning("sibling", kind="half", shared_parent=side)
    if _has(r"fratellastr|sorellastr", t):
        if side:
            return Meaning("sibling", kind="half", shared_parent=side)
        return [HALF, STEP]
    if _has(r"twin|gemell", t):
        return Meaning("sibling", kind="full")
    if _has(r"\bmother\b|\bmom\b|\bmum\b|\bmadre\b|\bmamma\b|\bfather\b|\bdad\b|\bpadre\b|\bpapa\b|\bbabbo\b|\bparents?\b|\bgenitor[ei]\b", t):
        return Meaning("parent", relation="adopted" if adopted else "birth")
    if _has(r"\bdaughters?\b|\bsons?\b|\bchild(ren)?\b|\bkids?\b|\bfigli[oae]?\b|\bbambin[oaie]\b", t):
        return Meaning("child", relation="adopted" if adopted else "birth")
    if _has(r"\bsisters?\b|\bbrothers?\b|\bsiblings?\b|\bsorell[ae]\b|\bfratell[oi]\b", t):
        if side:   # "sister on the mother's side": only one parent in common
            return Meaning("sibling", kind="half", shared_parent=side)
        return Meaning("sibling", kind="unspecified")
    if _has(r"wife|husband|spouse|married|marry|\bwed|moglie|marito|coniug|spos", t):
        return Meaning("couple", union_type="marriage")
    if _has(r"partner|companion|compagn|conviv|fidanzat|girlfriend|boyfriend|lover|amante", t):
        return Meaning("couple", union_type="partnership")
    return None


def meaning_to_ops(m: Meaning, person: str, others: list[str]) -> list[dict]:
    """Operations for "<person> is the <word> of <others>"."""
    if m.category == "couple":
        return [{"op": "union", "partners": [person, others[0]], "type": m.union_type}]
    if m.category == "child":
        return [{"op": "child", "child": person, "parents": others[:2], "relation": m.relation}]
    if m.category == "parent":
        return [{"op": "child", "child": o, "parents": [person], "relation": m.relation} for o in others]
    if m.category == "sibling":
        op = {"op": "siblings", "people": [person, *others], "kind": m.kind}
        if m.shared_parent:
            op["shared_parent"] = m.shared_parent
        return [op]
    return [{"op": "relation_hint", "a": person, "b": o, "kind": m.kind} for o in others]


def to_tree_ops(model_ops: list[dict]) -> tuple[list[dict], list[str]]:
    """Gemma's operations (person / relation / event) -> the planner's operations."""
    ops, problems = [], []
    for op in model_ops:
        if op["op"] != "relation":
            ops.append(op)
            continue
        person, word, others = op["person"], op["word"], op["of"]
        reading = read_word(word)
        if not reading.meanings:
            problems.append(f'I don\'t know the relation "{word}" ({person} / {", ".join(others)}).')
            continue
        if reading.sex:
            ops.append({"op": "person", "name": person, "sex": reading.sex})
        if reading.ambiguous:
            ops.append({
                "op": "ambiguous", "word": word, "person": person, "of": others,
                "options": [{"label": m.label, "ops": meaning_to_ops(m, person, others)} for m in reading.meanings],
            })
            continue
        meaning = reading.meanings[0]
        if meaning.category == "couple" and len(others) != 1:
            problems.append(f'"{word}" needs exactly one partner ({person} / {", ".join(others)}).')
            continue
        ops += meaning_to_ops(meaning, person, others)
    return _merge_parents(ops), problems


def _merge_parents(ops: list[dict]) -> list[dict]:
    """'X is Ann's son' + 'X is Bob's son' in one sentence -> X is the son of Ann and Bob."""
    merged, seen = [], {}
    for op in ops:
        if op["op"] == "child" and len(op["parents"]) == 1:
            key = (op["child"].casefold(), op["relation"])
            if key in seen and len(seen[key]["parents"]) == 1 and seen[key]["parents"][0] != op["parents"][0]:
                seen[key]["parents"].append(op["parents"][0])
                continue
            op = {**op, "parents": list(op["parents"])}
            seen[key] = op
        merged.append(op)
    return merged
