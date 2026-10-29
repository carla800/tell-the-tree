"""Everything the engine says to a person, in English and Italian.

The planner builds `Message`s: they are plain English strings (so the tests, the evals and the
logs read them as before) that also remember their key and values, so the API can say them
again in the language of the interface. Adding a language means adding one column here.
"""

LANGUAGES = ("en", "it")


class Term:
    """A code that is a word in each language: Term("birth") -> "birth" / "nascita"."""

    def __init__(self, code: str):
        self.code = code


TERMS = {
    "en": {
        # events
        "birth": "birth", "death": "death", "marriage": "marriage", "divorce": "divorce",
        "residence": "residence", "occupation": "work", "other": "event",
        # relatives
        "parent": "parent", "child": "child", "partner": "partner", "sibling": "sibling",
        "full_sibling": "sibling", "unspecified_sibling": "sibling",
        "half_sibling": "half-sibling", "step_sibling": "step-sibling",
        "grandchild": "grandchild", "grandparent": "grandparent", "niece_nephew": "niece or nephew",
        "aunt_uncle": "aunt or uncle", "cousin": "cousin", "in_law": "in-law", "relative": "relative",
        "full": "full siblings", "half": "half-siblings", "step": "step-siblings", "unspecified": "siblings",
        # meanings to choose from
        "meaning_half": "half-sibling (one parent in common)",
        "meaning_step": "step-sibling (their parents married each other)",
        "meaning_grandchild": "grandchild (a child's child)",
        "meaning_niece_nephew": "niece or nephew (a sibling's child)",
        "and": "and", "other_parents": "other parents",
    },
    "it": {
        "birth": "nascita", "death": "morte", "marriage": "matrimonio", "divorce": "divorzio",
        "residence": "residenza", "occupation": "lavoro", "other": "evento",
        "parent": "genitore", "child": "figlio o figlia", "partner": "compagno o compagna",
        "sibling": "fratello o sorella",
        "full_sibling": "fratello o sorella", "unspecified_sibling": "fratello o sorella",
        "half_sibling": "fratello o sorella per parte di un solo genitore",
        "step_sibling": "fratello o sorella acquisiti",
        "grandchild": "nipote (di nonno o nonna)", "grandparent": "nonno o nonna",
        "niece_nephew": "nipote (di zio o zia)", "aunt_uncle": "zio o zia", "cousin": "cugino o cugina",
        "in_law": "parente acquisito", "relative": "parente", "full": "fratelli", "half": "fratelli per parte di un solo genitore",
        "step": "fratelli acquisiti", "unspecified": "fratelli",
        "meaning_half": "fratello o sorella per parte di un solo genitore",
        "meaning_step": "fratello o sorella acquisiti (i loro genitori si sono sposati tra loro)",
        "meaning_grandchild": "nipote di nonno o nonna (il figlio di un figlio)",
        "meaning_niece_nephew": "nipote di zio o zia (il figlio di un fratello o di una sorella)",
        "and": "e", "other_parents": "altri genitori",
    },
}

MESSAGES = {
    # what will be added
    "new_person": ("New person: {name}", "Nuova persona: {name}"),
    "union_marriage": ("{a} and {b}: married", "{a} e {b}: sposati"),
    "union_partnership": ("{a} and {b}: partners", "{a} e {b}: coppia non sposata"),
    "union_unknown": ("{a} and {b}: a couple", "{a} e {b}: una coppia"),
    "child_of": ("{child}: child of {parents}", "{child}: figlio o figlia di {parents}"),
    "adopted_child_of": ("{child}: adopted child of {parents}", "{child}: figlio o figlia adottivi di {parents}"),
    "stepchild_of": ("{child}: stepchild of {parents}", "{child}: figlio o figlia del coniuge di {parents}"),
    "parent_added": ("{child}: {parents} added as parent", "{child}: aggiunto come genitore {parents}"),
    "siblings_new": ("{a} and {b}: siblings", "{a} e {b}: fratelli"),
    "claim_note": ("{a}: {kind} of {b} (kept as a note until their parents are in the tree)",
                   "{a}: {kind} di {b} (tenuto come nota finché i genitori non sono nell'albero)"),
    "event": ("{who}: {etype}{details}", "{who}: {etype}{details}"),
    # already known
    "already_couple": ("{a} and {b} are already a couple", "{a} e {b} sono già una coppia"),
    "parents_known": ("{child}'s parents are already in the tree", "I genitori di {child} sono già nell'albero"),
    "siblings_known": ("{a} and {b} are already {kind} in the tree", "{a} e {b} sono già {kind} nell'albero"),
    "hint_known": ("{a} is already {b}'s {kind} in the tree", "Nell'albero {a} è già {kind} di {b}"),
    "event_known": ("{who}: {etype}{details} is already in the tree", "{who}: {etype}{details} è già nell'albero"),
    "meaning_known": ('"{word}" read as {label}, as the tree already shows',
                      '"{word}" letto come {label}, come mostra già l\'albero'),
    # impossible
    "err_self_couple": ("{a} can't be in a couple with themselves.", "{a} non può fare coppia con sé."),
    "err_own_parent": ("{a} can't be their own parent.", "{a} non può essere genitore di sé."),
    "err_ancestor": ("{child} is already an ancestor of {parent}: {parent} can't also be {child}'s parent.",
                     "{child} è già un antenato di {parent}: {parent} non può essere anche genitore di {child}."),
    "err_has_parents": ("{child} already has {names} as parents in the tree.",
                        "Nell'albero {child} ha già come genitori {names}."),
    "err_parent_younger": ("{parent} (born {pb}) can't be the parent of {child} (born {cb}).",
                           "{parent} (nascita: {pb}) non può essere genitore di {child} (nascita: {cb})."),
    "err_parent_dead": ("{parent} died in {pd}, before {child} was born ({cb}).",
                        "La morte di {parent} è nel {pd}, prima della nascita di {child} ({cb})."),
    "err_sibling_kind": ("The tree says {a} and {b} are {current}, not {kind}.",
                         "Nell'albero {a} e {b} sono {current}, non {kind}."),
    "err_shared_mother": ("{a} and {b} don't share a mother in the tree.", "Nell'albero {a} e {b} non hanno la stessa madre."),
    "err_shared_father": ("{a} and {b} don't share a father in the tree.", "Nell'albero {a} e {b} non hanno lo stesso padre."),
    "err_hint": ("The tree says {a} is {b}'s {current}, not {kind}.", "Nell'albero {a} è {current} di {b}, non {kind}."),
    "err_born_conflict": ("{name} is already recorded as born in {born}, not {year}.",
                          "Nell'albero la nascita di {name} è nel {born}, non nel {year}."),
    "err_born_after_death": ("{name} died in {died}, so can't be born in {year}.",
                             "La morte di {name} è nel {died}: la nascita non può essere nel {year}."),
    "err_born_after_child": ("{name} can't be born in {year}: their child {child} was born in {cb}.",
                             "La nascita di {name} non può essere nel {year}: la nascita di {child}, che è suo figlio o figlia, è nel {cb}."),
    "err_death_conflict": ("{name} is already recorded as dead in {died}, not {year}.",
                           "Nell'albero la morte di {name} è nel {died}, non nel {year}."),
    "err_death_before_birth": ("{name} was born in {born}, so can't die in {year}.",
                               "La nascita di {name} è nel {born}: la morte non può essere nel {year}."),
    "err_died_before_child": ("{name} can't have died in {died}: their child {child} was born in {cb}.",
                              "La morte di {name} non può essere nel {died}: la nascita di {child}, che è suo figlio o figlia, è nel {cb}."),
    "err_event_before_birth": ("{name} was born in {born}: nothing can happen to them in {year}.",
                               "La nascita di {name} è nel {born}: nel {year} non può essere successo niente."),
    # the sentence itself
    "warn_young_parent": ("{parent} would have been {age} at {child}'s birth.",
                          "{parent} avrebbe avuto {age} anni alla nascita di {child}."),
    "unknown_word": ('I don\'t know the relation "{word}" ({who}).', 'Non conosco la parentela "{word}" ({who}).'),
    "couple_needs_one": ('"{word}" needs exactly one partner ({who}).', '"{word}" vuole una sola persona come coppia ({who}).'),
    "gedcom_too_big": ("The GEDCOM file is too big (15 MB at most).", "Il file GEDCOM è troppo grande (al massimo 15 MB)."),
    "gedcom_encoding": ("This file's text encoding isn't one a GEDCOM uses.", "La codifica del testo di questo file non è quella di un GEDCOM."),
    "gedcom_bad_line": ("Line {line} is not a GEDCOM line.", "La riga {line} non è una riga GEDCOM."),
    "gedcom_bad_level": ("Line {line} has a level that doesn't follow the line before.",
                         "La riga {line} ha un livello che non segue la riga precedente."),
    "gedcom_no_people": ("This GEDCOM has no people in it.", "Questo GEDCOM non contiene persone."),
    "tree_exists": ("A tree called \"{name}\" already exists.", "Esiste già un albero chiamato \"{name}\"."),
    "part_not_read": ("Part of this sentence couldn't be turned into tree facts.",
                      "Una parte della frase non è diventata un fatto dell'albero."),
}


def _render(lang: str, value) -> str:
    if isinstance(value, Term):
        return TERMS[lang].get(value.code, value.code.replace("_", " "))
    if isinstance(value, (list, tuple)):
        names = [_render(lang, v) for v in value]
        return f" {TERMS[lang]['and']} ".join(names)
    return str(value)


def say(lang: str, key: str, **params) -> str:
    lang = lang if lang in LANGUAGES else "en"
    template = MESSAGES[key][LANGUAGES.index(lang)]
    return template.format(**{k: _render(lang, v) for k, v in params.items()})


class Message(str):
    """An English string that can be said again in another language."""

    def __new__(cls, key: str, **params):
        text = super().__new__(cls, say("en", key, **params))
        text.key, text.params = key, params
        return text

    def __deepcopy__(self, memo):
        return self


def term(code: str) -> str:
    """A single word, as a Message-like string (used for the meaning labels)."""
    return TermText(code)


class TermText(str):
    def __new__(cls, code: str):
        text = super().__new__(cls, TERMS["en"].get(code, code))
        text.code = code
        return text

    def __deepcopy__(self, memo):
        return self


def translate(text, lang: str) -> str:
    """Any string the engine produced, in `lang`. Plain strings stay as they are."""
    if isinstance(text, Message):
        return say(lang, text.key, **text.params)
    if isinstance(text, TermText):
        return TERMS.get(lang, TERMS["en"]).get(text.code, str(text))
    return str(text)
