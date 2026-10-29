"""The family register as a PDF: every family and every person, with where each fact comes from.

Written with the app's own fonts (backend/fonts, SIL Open Font License), so it looks the same
on Windows, macOS and Linux. Names with letters those fonts don't have use a system font.
"""

import re
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer

FONTS = Path(__file__).resolve().parent / "fonts"
FALLBACK_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
]

WORDS = {
    "en": {
        "register": "Family register",
        "people_n": ("1 person", "{n} people"), "families_n": ("1 family", "{n} families"),
        "families": "Families", "people": "People", "and": "and", "no_parents": "Parents not recorded",
        "married": "Married", "partners": "Together, not married", "children": "Children",
        "adopted": "adopted", "step": "stepchild", "no_children": "No children recorded",
        "child_of": {"F": "Daughter of", "M": "Son of", "U": "Child of"},
        "born_as": {"F": "née", "M": "born", "U": "born"}, "aka": "also known as",
        "events": {"birth": "Born", "death": "Died", "marriage": "Married", "divorce": "Divorced",
                   "residence": "Lived", "occupation": "Work", "baptism": "Baptised", "christening": "Christened",
                   "burial": "Buried", "other": "Event"},
        "with": "with", "source": "Source", "from": "From the sentence", "by_hand": "Added by hand",
        "gedcom": "Imported from GEDCOM", "empty": "This tree has no people yet.",
        "qualifiers": {"about": "about", "before": "before", "after": "after"},
        "months": ["January", "February", "March", "April", "May", "June", "July", "August",
                   "September", "October", "November", "December"],
    },
    "it": {
        "register": "Registro di famiglia",
        "people_n": ("1 persona", "{n} persone"), "families_n": ("1 famiglia", "{n} famiglie"),
        "families": "Famiglie", "people": "Persone", "and": "e", "no_parents": "Genitori non indicati",
        "married": "Sposati", "partners": "Insieme, non sposati", "children": "Figli",
        "adopted": "adottato", "step": "figlio del coniuge", "no_children": "Nessun figlio registrato",
        "child_of": {"F": "Figlia di", "M": "Figlio di", "U": "Figlio o figlia di"},
        "born_as": {"F": "nata", "M": "nato", "U": "alla nascita"}, "aka": "detto anche",
        "events": {"birth": "Nascita", "death": "Morte", "marriage": "Matrimonio", "divorce": "Divorzio",
                   "residence": "Residenza", "occupation": "Lavoro", "baptism": "Battesimo", "christening": "Battesimo",
                   "burial": "Sepoltura", "other": "Evento"},
        "with": "con", "source": "Fonte", "from": "Dalla frase", "by_hand": "Aggiunto a mano",
        "gedcom": "Importato da GEDCOM", "empty": "Questo albero non ha ancora persone.",
        "qualifiers": {"about": "circa", "before": "prima del", "after": "dopo il"},
        "months": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                   "settembre", "ottobre", "novembre", "dicembre"],
    },
}


def _register_fonts() -> str | None:
    """The app's fonts, plus a system font for letters they don't have. Returns the fallback's name."""
    for name in ("AtkinsonHyperlegible-Regular", "AtkinsonHyperlegible-Bold",
                 "AtkinsonHyperlegible-Italic", "IMFellEnglish-Regular"):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(FONTS / f"{name}.ttf")))
    # so that <b> and <i> in a paragraph pick the bold and italic files
    pdfmetrics.registerFontFamily("AtkinsonHyperlegible-Regular", normal="AtkinsonHyperlegible-Regular",
                                  bold="AtkinsonHyperlegible-Bold", italic="AtkinsonHyperlegible-Italic",
                                  boldItalic="AtkinsonHyperlegible-Bold")
    if "Fallback" in pdfmetrics.getRegisteredFontNames():
        return "Fallback"
    for path in FALLBACK_FONTS:
        if Path(path).is_file():
            try:
                pdfmetrics.registerFont(TTFont("Fallback", path))
                return "Fallback"
            except Exception:   # a font file we can't read: try the next one
                continue
    return None


class _Text:
    def __init__(self, fallback: str | None):
        self.fallback = fallback
        self.chars = {name: set(pdfmetrics.getFont(name).face.charToGlyph)
                      for name in ("AtkinsonHyperlegible-Regular", "IMFellEnglish-Regular")}

    def __call__(self, text: str, font: str = "AtkinsonHyperlegible-Regular") -> str:
        """Escaped text; switches to the system font when the app's font lacks a letter."""
        safe = escape(text)
        missing = any(ord(c) not in self.chars[font] for c in text if not c.isspace())
        if missing and self.fallback:
            return f'<font name="{self.fallback}">{safe}</font>'
        return safe


def _count(forms: tuple, n: int) -> str:
    return forms[0] if n == 1 else forms[1].format(n=n)


def _readable_date(text: str | None, words: dict) -> str | None:
    qualified = re.fullmatch(r"(about|before|after)\s+(.+)", (text or "").strip())
    if qualified:
        return f"{words['qualifiers'][qualified.group(1)]} {_readable_date(qualified.group(2), words)}"
    match = re.fullmatch(r"(\d{4})-(\d{2})(?:-(\d{2}))?", (text or "").strip())
    if not match:
        return text
    year, month, day = match.groups()
    return " ".join(x for x in (str(int(day)) if day else None, words["months"][int(month) - 1], year) if x)


def _source(text: str | None, words: dict) -> str | None:
    if not text:
        return None
    if text == "By hand":
        return words["by_hand"]
    if text == "GEDCOM import":
        return words["gedcom"]
    sentence = re.fullmatch(r'From: "(.*)"', text, re.S)
    if sentence:
        return f"{words['from']}: “{sentence.group(1)}”"
    host = re.match(r"https?://([^/]+)", text)
    return f"{words['source']}: {host.group(1) if host else text}"


def create_pdf(conn, title: str, lang: str = "en", demo: bool = False) -> bytes:
    words = WORDS.get(lang, WORDS["en"])
    text = _Text(_register_fonts())
    ink = colors.HexColor("#23201C")
    soft = colors.HexColor("#6A645B")
    accent = colors.HexColor("#A8742A" if demo else "#B0302A")
    def style(name, **changes):
        base = {"fontName": "AtkinsonHyperlegible-Regular", "fontSize": 9.5, "leading": 13.5, "textColor": ink}
        return ParagraphStyle(name, **{**base, **changes})
    s_title = style("title", fontName="IMFellEnglish-Regular", fontSize=30, leading=36, alignment=TA_CENTER, spaceAfter=10)
    s_sub = style("sub", textColor=soft, fontSize=10.5, alignment=TA_CENTER)
    s_section = style("section", fontName="IMFellEnglish-Regular", fontSize=19, leading=24, textColor=accent,
                      spaceBefore=18, spaceAfter=8)
    s_name = style("name", fontName="IMFellEnglish-Regular", fontSize=13.5, leading=17, spaceBefore=8)
    s_line = style("line")
    s_small = style("small", fontSize=8.5, leading=11.5, textColor=soft, leftIndent=12)

    people = conn.execute("SELECT * FROM person ORDER BY name COLLATE NOCASE, id").fetchall()
    name = {p["id"]: p["name"] for p in people}
    families = conn.execute("SELECT * FROM family ORDER BY id").fetchall()
    kids = {}
    for r in conn.execute("SELECT * FROM family_child ORDER BY family_id, child_id"):
        kids.setdefault(r["family_id"], []).append((r["child_id"], r["relation"]))
    events = conn.execute("SELECT * FROM event ORDER BY id").fetchall()
    and_ = f" {words['and']} "

    def event_line(e, partner=None):
        what = ", ".join(x for x in (_readable_date(e["date_text"], words), e["place"], e["description"]) if x)
        label = words["events"].get(e["type"], e["type"])
        if partner:
            label += f" {words['with']} {text(partner)}"
        out = [Paragraph(f"<b>{label}</b>" + (f"  {text(what)}" if what else ""), s_line)]
        source = _source(e["source"], words)
        if source:
            out.append(Paragraph(text(source), s_small))
        return out

    story = [Spacer(1, 3 * cm), Paragraph(text(title, "IMFellEnglish-Regular"), s_title),
             Paragraph(words["register"], s_sub), Spacer(1, 0.3 * cm),
             Paragraph(f"{_count(words['people_n'], len(people))}, {_count(words['families_n'], len(families))}", s_sub),
             Spacer(1, 1.5 * cm)]
    if not people:
        story.append(Paragraph(words["empty"], s_sub))

    if families:
        story.append(Paragraph(words["families"], s_section))
    for f in families:
        partners = [name[x] for x in (f["partner1_id"], f["partner2_id"]) if x]
        block = [Paragraph(text(and_.join(partners) or words["no_parents"], "IMFellEnglish-Regular"), s_name)]
        if len(partners) == 2 and f["union_type"] in ("marriage", "partnership"):
            block.append(Paragraph(words["married" if f["union_type"] == "marriage" else "partners"], s_line))
        for e in events:
            if e["family_id"] == f["id"]:
                block += event_line(e)
        children = [name[c] + (f" ({words[rel]})" if rel in ("adopted", "step") else "") for c, rel in kids.get(f["id"], [])]
        block.append(Paragraph(f"<b>{words['children']}</b>  " + text(", ".join(children) if children else words["no_children"]), s_line))
        story.append(KeepTogether(block))

    if people:
        story.append(Paragraph(words["people"], s_section))
    for p in people:
        sex = p["sex"] if p["sex"] in ("F", "M") else "U"
        block = [Paragraph(text(p["name"], "IMFellEnglish-Regular"), s_name)]
        also = []
        if p["birth_name"] and p["birth_name"] != p["name"]:
            also.append(f"{words['born_as'][sex]} {p['birth_name']}")
        if p["also_known_as"]:
            also.append(f"{words['aka']} {p['also_known_as']}")
        if also:
            block.append(Paragraph(f"<i>{text('; '.join(also))}</i>", s_line))
        parents = [name[x] for f in families for c, rel in kids.get(f["id"], []) if c == p["id"] and rel != "step"
                   for x in (f["partner1_id"], f["partner2_id"]) if x]
        if parents:
            block.append(Paragraph(f"{words['child_of'][sex]} {text(and_.join(parents))}", s_line))
        for e in events:
            if e["person_id"] == p["id"]:
                block += event_line(e)
        for f in families:
            if p["id"] in (f["partner1_id"], f["partner2_id"]):
                partner = next((name[x] for x in (f["partner1_id"], f["partner2_id"]) if x and x != p["id"]), None)
                for e in events:
                    if e["family_id"] == f["id"]:
                        block += event_line(e, partner)
        if p["notes"]:
            block.append(Paragraph(text(p["notes"][:1500]), s_line))
        story.append(KeepTogether(block))

    def page(canvas, doc):
        canvas.saveState()
        width, _ = A4
        canvas.setStrokeColor(accent)
        canvas.setLineWidth(0.6)
        canvas.line(2 * cm, 1.6 * cm, width - 2 * cm, 1.6 * cm)
        canvas.setFillColor(soft)
        canvas.setFont("AtkinsonHyperlegible-Regular", 8)
        canvas.drawCentredString(width / 2, 1.1 * cm, f"{title}  ·  {doc.page}")
        canvas.restoreState()

    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=A4, leftMargin=2.3 * cm, rightMargin=2.3 * cm,
                            topMargin=2 * cm, bottomMargin=2.3 * cm, title=title, author="")
    doc.build(story, onFirstPage=page, onLaterPages=page)
    return stream.getvalue()
