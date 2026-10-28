import { createContext, useContext } from "react";

/**
 * Every word of the interface, in English and Italian.
 * To add a language: copy the `en` block, translate it, add it to STRINGS and LANGS,
 * and add the same language to backend/messages.py (the sentences the engine writes).
 */

const MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July",
  "August", "September", "October", "November", "December"];

const en = {
  appName: "Family tree",
  language: "Language",
  tree: "Tree",
  newTree: "New tree",
  name: "Name",
  newTreePlaceholder: "rossi-family",
  create: "Create",
  cancel: "Cancel",
  treeExists: "A tree with this name already exists.",
  badTreeName: "Tree names use lowercase letters, digits and hyphens.",
  serverDown: "Can't reach the app's server. Start it with: uvicorn backend.api:app --reload",
  gemmaFailed: (why: string) => `Gemma couldn't read the sentence (${why}). Is Ollama running?`,

  tell: "Tell the tree something",
  tip: "One fact per sentence works best. Names, dates and places are kept exactly as you write them.",
  read: "Read sentence",
  reading: "Reading…",
  readIn: (seconds: string) => `Read in ${seconds} s on this computer.`,
  added: "Added to the tree.",
  clickHint: "Click a person to see their dates, places and the sentence each fact came from.",
  footer: (model: string) => `Sentences are read by ${model} with Ollama, on this computer. The tree is a file in the app’s trees folder.`,
  noGemma: "Gemma isn’t reachable yet.",
  emptyTree: "This tree is empty.",
  startWith: (example: string) => `Start with one sentence, for example “${example}”`,
  exampleDemo: "Percy Florence Shelley was the son of Mary Shelley.",
  exampleOther: "Maria Rossi is Marco Rossi's wife.",

  doesntFit: "This doesn’t fit the tree",
  nothingSaved: "Nothing will be saved. Check the sentence, or the facts already in the tree.",
  whichPerson: (name: string) => `Which ${name} do you mean?`,
  bornYear: (year: number) => `born ${year}`,
  someoneElse: (name: string) => `Someone else called ${name}`,
  meaningQuestion: (word: string, person: string, of: string) => `“${word}” can mean two things here. ${person} is ${of}’s…`,
  willAdd: "This will be added",
  onceAnswered: "Once you answer, this will be added",
  alreadyKnows: "The tree already knows this. Nothing to add.",
  showKnown: (n: number) => `Show what the tree already knows (${n})`,
  hideKnown: (n: number) => `Hide what the tree already knows (${n})`,
  addToTree: "Add to tree",
  discard: "Discard",
  clear: "Clear",
  and: "and",

  close: "Close",
  bornAs: (name: string) => `Born ${name}`,
  alsoKnownAs: (name: string) => `Also known as ${name}`,
  dateUnknown: "date unknown",
  noEvents: (name: string) => `No dates or places yet. Tell the tree, for example: “${name} was born in…”.`,
  sourceWeb: (host: string) => `Source: ${host}`,
  fromSentence: (sentence: string) => `From: “${sentence}”`,
  events: { birth: "Born", death: "Died", marriage: "Married", divorce: "Divorced",
            residence: "Lived", occupation: "Work", other: "Event" } as Record<string, string>,
  months: MONTHS_EN,
  dayMonthYear: (d: string | null, m: string, y: string) => [d, m, y].filter(Boolean).join(" "),

  addRelativeOf: (name: string) => `Add a relative of ${name}`,
  addPersonByHand: "Or add a person by hand",
  whoIsIt: "Who are you adding?",
  relativeOf: (relative: string, name: string) => ({
    mother: `Mother of ${name}`, father: `Father of ${name}`, daughter: `Daughter of ${name}`, son: `Son of ${name}`,
    sister: `Sister of ${name}`, brother: `Brother of ${name}`, wife: `Wife of ${name}`, husband: `Husband of ${name}`,
    partner: `Partner of ${name}, not married`,
  } as Record<string, string>)[relative],
  fullName: "Name and surname",
  otherParent: "The other parent",
  otherParentUnknown: "No one, or I don't know",
  birthDate: "Born (year or date, optional)",
  birthDatePlaceholder: "12 March 1990",
  birthPlace: "Place of birth (optional)",
  showInTree: "Show in the tree",
  byHand: "Added by hand",

  addPhoto: "Add a photo",
  changePhoto: "Change photo",
  removePhoto: "Remove photo",
  photoOf: (name: string) => `Photo of ${name}`,
  photoSaving: "Saving the photo…",
  photoUnreadable: "This picture can't be opened here. Use a JPEG, PNG or WebP file.",
  photoNote: "The photo is kept inside this tree’s file, on this computer.",

  legendTitle: "How to read the tree",
  keyChild: "child",
  keyStepchild: "stepchild",
  keyAdopted: "adopted",
  keyMarried: "married",
  keyNotMarried: "together, not married",
  keyParents: "parents",
  knotTitles: { marriage: "Married", partnership: "Together, not married", unknown: "Parents" } as Record<string, string>,
  newTag: "new",
  cardYears: (born: number | null, died: number | null) =>
    born && died ? `${born}–${died}` : born ? `born ${born}` : died ? `died ${died}` : "",
  cardBirthName: (name: string, _sex: string) => `born ${name}`,
  claims: {
    step_sibling: "step-sibling", half_sibling: "half-sibling", full_sibling: "sibling",
    unspecified_sibling: "sibling", grandchild: "grandchild", grandparent: "grandparent",
    niece_nephew: "niece or nephew", aunt_uncle: "aunt or uncle", cousin: "cousin",
    in_law: "in-law", other: "relative",
  } as Record<string, string>,
};

export type Strings = typeof en;

const MONTHS_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
  "agosto", "settembre", "ottobre", "novembre", "dicembre"];

const it: Strings = {
  appName: "Albero di famiglia",
  language: "Lingua",
  tree: "Albero",
  newTree: "Nuovo albero",
  name: "Nome",
  newTreePlaceholder: "famiglia-rossi",
  create: "Crea",
  cancel: "Annulla",
  treeExists: "Esiste già un albero con questo nome.",
  badTreeName: "Il nome dell'albero può avere solo lettere minuscole, numeri e trattini.",
  serverDown: "Il server dell'app non risponde. Avvialo con: uvicorn backend.api:app --reload",
  gemmaFailed: (why) => `Gemma non è riuscito a leggere la frase (${why}). Ollama è acceso?`,

  tell: "Racconta qualcosa all’albero",
  tip: "Funziona meglio un fatto per frase. Nomi, date e luoghi restano esattamente come li scrivi.",
  read: "Leggi la frase",
  reading: "Sto leggendo…",
  readIn: (seconds) => `Letta in ${seconds} s su questo computer.`,
  added: "Aggiunto all’albero.",
  clickHint: "Clicca una persona per vedere date, luoghi e la frase da cui viene ogni fatto.",
  footer: (model) => `Le frasi le legge ${model} con Ollama, su questo computer. L’albero è un file nella cartella trees dell’app.`,
  noGemma: "Gemma non è ancora raggiungibile.",
  emptyTree: "Questo albero è vuoto.",
  startWith: (example) => `Comincia con una frase, per esempio “${example}”`,
  exampleDemo: "Percy Florence Shelley era il figlio di Mary Shelley.",
  exampleOther: "Maria Rossi è la moglie di Marco Rossi.",

  doesntFit: "Questo non torna con l’albero",
  nothingSaved: "Non verrà salvato niente. Controlla la frase, o i fatti che sono già nell’albero.",
  whichPerson: (name) => `Quale ${name} intendi?`,
  bornYear: (year) => `n. ${year}`,
  someoneElse: (name) => `Un’altra persona di nome ${name}`,
  meaningQuestion: (word, person, of) => `Qui “${word}” può voler dire due cose. Rispetto a ${of}, ${person} è…`,
  willAdd: "Verrà aggiunto",
  onceAnswered: "Quando rispondi, verrà aggiunto",
  alreadyKnows: "L’albero lo sa già. Non c’è niente da aggiungere.",
  showKnown: (n) => `Mostra cosa sa già l’albero (${n})`,
  hideKnown: (n) => `Nascondi cosa sa già l’albero (${n})`,
  addToTree: "Aggiungi all’albero",
  discard: "Scarta",
  clear: "Chiudi",
  and: "e",

  close: "Chiudi",
  bornAs: (name) => `Nome alla nascita: ${name}`,
  alsoKnownAs: (name) => `Detto anche ${name}`,
  dateUnknown: "data sconosciuta",
  noEvents: (name) => `Ancora nessuna data o luogo. Raccontalo all’albero, per esempio: “${name} è nato a…”.`,
  sourceWeb: (host) => `Fonte: ${host}`,
  fromSentence: (sentence) => `Dalla frase: “${sentence}”`,
  events: { birth: "Nascita", death: "Morte", marriage: "Matrimonio", divorce: "Divorzio",
            residence: "Residenza", occupation: "Lavoro", other: "Evento" },
  months: MONTHS_IT,
  dayMonthYear: (d, m, y) => [d, m, y].filter(Boolean).join(" "),

  addRelativeOf: (name) => `Aggiungi un parente di ${name}`,
  addPersonByHand: "Oppure aggiungi una persona a mano",
  whoIsIt: "Chi stai aggiungendo?",
  relativeOf: (relative, name) => ({
    mother: `La madre di ${name}`, father: `Il padre di ${name}`, daughter: `Una figlia di ${name}`,
    son: `Un figlio di ${name}`, sister: `Una sorella di ${name}`, brother: `Un fratello di ${name}`,
    wife: `La moglie di ${name}`, husband: `Il marito di ${name}`,
    partner: `Il compagno o la compagna di ${name}, non sposati`,
  } as Record<string, string>)[relative],
  fullName: "Nome e cognome",
  otherParent: "L’altro genitore",
  otherParentUnknown: "Nessuno, o non lo so",
  birthDate: "Nascita (anno o data, facoltativo)",
  birthDatePlaceholder: "12 marzo 1990",
  birthPlace: "Luogo di nascita (facoltativo)",
  showInTree: "Mostra nell’albero",
  byHand: "Aggiunto a mano",

  addPhoto: "Aggiungi una foto",
  changePhoto: "Cambia foto",
  removePhoto: "Togli la foto",
  photoOf: (name) => `Foto di ${name}`,
  photoSaving: "Sto salvando la foto…",
  photoUnreadable: "Questa immagine non si apre. Usa un file JPEG, PNG o WebP.",
  photoNote: "La foto resta dentro il file di questo albero, su questo computer.",

  legendTitle: "Come leggere l’albero",
  keyChild: "figlio",
  keyStepchild: "figlio del coniuge",
  keyAdopted: "adottato",
  keyMarried: "sposati",
  keyNotMarried: "insieme, non sposati",
  keyParents: "genitori",
  knotTitles: { marriage: "Sposati", partnership: "Insieme, non sposati", unknown: "Genitori" },
  newTag: "nuovo",
  cardYears: (born, died) => (born && died ? `${born}–${died}` : born ? `n. ${born}` : died ? `m. ${died}` : ""),
  cardBirthName: (name, sex) => `${sex === "F" ? "nata" : sex === "M" ? "nato" : "alla nascita"} ${name}`,
  claims: {
    step_sibling: "fratello o sorella acquisiti", half_sibling: "fratello o sorella per un genitore",
    full_sibling: "fratello o sorella", unspecified_sibling: "fratello o sorella",
    grandchild: "nipote (di nonno)", grandparent: "nonno o nonna", niece_nephew: "nipote (di zio)",
    aunt_uncle: "zio o zia", cousin: "cugino o cugina", in_law: "parente acquisito", other: "parente",
  },
};

export type Lang = "en" | "it";
export const STRINGS: Record<Lang, Strings> = { en, it };
export const LANGS: { code: Lang; name: string }[] = [
  { code: "en", name: "English" },
  { code: "it", name: "Italiano" },
];

export function startingLang(): Lang {
  try {
    const saved = localStorage.getItem("lang");
    if (saved === "en" || saved === "it") return saved;
  } catch { /* private window: fall back to the browser's language */ }
  return navigator.language?.toLowerCase().startsWith("it") ? "it" : "en";
}

export function rememberLang(lang: Lang) {
  try { localStorage.setItem("lang", lang); } catch { /* fine */ }
}

export const I18n = createContext<{ lang: Lang; t: Strings }>({ lang: "en", t: en });
export const useI18n = () => useContext(I18n);

/** "Byron", "Annabella" -> "Byron and Annabella" / "Byron e Annabella". */
export const joinNames = (t: Strings, names: string[]) => names.join(` ${t.and} `);
