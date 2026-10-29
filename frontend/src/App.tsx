import { useCallback, useEffect, useMemo, useState, type ChangeEvent, type FormEvent, type KeyboardEvent } from "react";
import { ReactFlowProvider } from "@xyflow/react";
import { api, ApiError, gedcomUrl, registerUrl } from "./api";
import { Bats } from "./Bats";
import { ByHand } from "./ByHand";
import { PersonEditor } from "./PersonEditor";
import { RelationEditor } from "./RelationEditor";
import { PersonDetail } from "./PersonDetail";
import { PlanView, questionKey } from "./PlanView";
import { withPreview } from "./preview";
import { I18n, LANGS, rememberLang, startingLang, STRINGS, type Lang, type Strings } from "./i18n";
import { TreeTools } from "./TreeTools";
import { TreeView } from "./TreeView";
import type { TreeDirection } from "./layout";
import type { Choices, Plan, Question, TreeData } from "./types";

// The project's name is in i18n.ts (appName) and index.html
const DEMO_TREE = "villa-diodati";

// The photo in the Villa Diodati story: by Robertgrassi (2008), released into the public domain
// on Wikimedia Commons. No credit is required; we give it anyway.
const VILLA_PHOTO = {
  page: "https://commons.wikimedia.org/wiki/File:Villa_diodati_2008.07.27_rg_5.JPG",
  author: "Robertgrassi",
};

interface Pending {
  sentence: string;
  modelOps: unknown[];
  plan: Plan;
  asked: Question[];
  seconds: number | null;     // null when added by hand: Gemma didn't read anything
  byHand: boolean;
}

const addQuestions = (asked: Question[], plan: Plan) =>
  [...asked, ...plan.questions.filter((q) => !asked.some((a) => questionKey(a) === questionKey(q)))];

const titleOf = (slug: string) => slug.split("-").map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(" ");
const displayTreeName = (name: string, t: Strings) => (name === DEMO_TREE ? t.demoTitle : titleOf(name));
const treeSlug = (text: string) => text.toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 41);

/** Messages are kept as "how to say it", so they follow the language when it changes. */
type Say = (t: Strings) => string;

const remembered = {
  get: () => { try { return localStorage.getItem("tree"); } catch { return null; } },
  set: (name: string) => { try { localStorage.setItem("tree", name); } catch { /* private window: fine */ } },
};

export default function App() {
  const [trees, setTrees] = useState<string[]>([]);
  const [current, setCurrent] = useState("");
  // the tree's data travels with its name, so a tree is never drawn under another tree's name
  const [loaded, setLoaded] = useState<{ name: string; data: TreeData } | null>(null);
  const tree = loaded && loaded.name === current ? loaded.data : null;
  const [model, setModel] = useState<string | null>(null);
  const [sentence, setSentence] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [choices, setChoices] = useState<Choices>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Say | null>(null);
  const [notice, setNotice] = useState<Say | null>(null);
  const [lang, setLang] = useState<Lang>(startingLang);
  const t = STRINGS[lang];
  const i18n = useMemo(() => ({ lang, t }), [lang, t]);
  const [selected, setSelected] = useState<number | null>(null);
  const [directions, setDirections] = useState<Record<string, TreeDirection>>(() => {
    try { return JSON.parse(localStorage.getItem("tree-directions") || "{}"); }
    catch { return {}; }
  });
  const direction = directions[current] === "TB" ? "TB" : "LR";
  const changeDirection = (next: TreeDirection) => {
    setDirections((old) => {
      const updated = { ...old, [current]: next };
      try { localStorage.setItem("tree-directions", JSON.stringify(updated)); } catch { /* optional preference */ }
      return updated;
    });
  };
  const [focus, setFocus] = useState<{ id: number; at: number } | null>(null);   // a person found with the search
  const [printing, setPrinting] = useState(false);
  const [gedFile, setGedFile] = useState<File | null>(null);
  const [gedPreview, setGedPreview] = useState<{people:number;families:number;sample:string[]} | null>(null);
  const [gedName, setGedName] = useState("");
  const [gedBusy, setGedBusy] = useState(false);
  const [newName, setNewName] = useState<string | null>(null);

  const theme = current === DEMO_TREE ? "diodati" : "register";
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = t.appName;
    rememberLang(lang);
  }, [lang, t]);

  useEffect(() => {
    api.health().then((h) => setModel(h.model)).catch(() => setModel(null));
    api.listTrees()
      .then((names) => {
        setTrees(names);
        const last = remembered.get();
        setCurrent(last && names.includes(last) ? last : names.includes(DEMO_TREE) ? DEMO_TREE : names[0] ?? "");
      })
      .catch(() => setError(() => (t: Strings) => t.serverDown));
  }, []);

  useEffect(() => {
    if (!current) return;
    remembered.set(current);
    setPending(null);
    setSelected(null);
    setNotice(null);
    setError(null);
    setSentence("");
    setFocus(null);
    api.getTree(current).then((data) => setLoaded({ name: current, data }))
      .catch((e: Error) => setError(() => () => e.message));
  }, [current]);

  const shown = useMemo(() => (tree && pending ? withPreview(tree, pending.plan.changes) : tree), [tree, pending]);
  const selectedPerson = shown?.people.find((p) => p.id === selected) ?? null;

  const read = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!sentence.trim() || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.parse(current, sentence.trim(), lang);
      setChoices({});
      setPending({ sentence: sentence.trim(), modelOps: result.model_ops, plan: result.plan,
                   asked: addQuestions([], result.plan), seconds: result.seconds, byHand: false });
    } catch (e) {
      const why = (e as Error).message;
      setError(() => (t: Strings) => t.gemmaFailed(why));
    } finally {
      setBusy(false);
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) read();
  };

  const choose = useCallback(async (key: string, value: number | string) => {
    if (!pending) return;
    const next = { ...choices, [key]: value };
    setChoices(next);
    setBusy(true);
    try {
      const { plan } = await api.plan(current, pending.modelOps, next, lang);
      setPending({ ...pending, plan, asked: addQuestions(pending.asked, plan) });
    } catch (e) {
      const why = (e as Error).message;
      setError(() => () => why);
    } finally {
      setBusy(false);
    }
  }, [choices, current, pending, lang]);

  // A new language while a sentence is waiting: ask for the same plan again, in that language
  const changeLang = async (next: Lang) => {
    setLang(next);
    if (!pending) return;
    try {
      const { plan } = await api.plan(current, pending.modelOps, choices, next);
      const asked = pending.asked.map((q) => plan.questions.find((n) => questionKey(n) === questionKey(q)) ?? q);
      setPending({ ...pending, plan, asked: addQuestions(asked, plan) });
    } catch { /* the old plan stays: still right, just in the other language */ }
  };

  // The form writes Gemma's operations: from here on it's the same flow as a sentence
  const previewByHand = async (modelOps: unknown[], initial: Choices) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const { plan } = await api.plan(current, modelOps, initial, lang);
      setChoices(initial);
      setPending({ sentence: "", modelOps, plan, asked: addQuestions([], plan), seconds: null, byHand: true });
    } catch (e) {
      const why = (e as Error).message;
      setError(() => () => why);
    } finally {
      setBusy(false);
    }
  };

  const reloadTree = () => {
    const name = current;
    api.getTree(name).then((data) => setLoaded({ name, data })).catch(() => undefined);
  };

  const confirm = async () => {
    if (!pending) return;
    setBusy(true);
    try {
      const result = await api.apply(current, pending.sentence, pending.modelOps, choices, lang, pending.byHand);
      setLoaded({ name: current, data: result.tree });
      setPending(null);
      if (!pending.byHand) setSentence("");
      setNotice(() => (t: Strings) => t.added);
    } catch (e) {
      const why = (e as Error).message;
      setError(() => () => why);
    } finally {
      setBusy(false);
    }
  };

  const createTree = async (event: FormEvent) => {
    event.preventDefault();
    if (!newName) return;
    try {
      const { name } = await api.createTree(newName.trim());
      setTrees((names) => [...names, name].sort());
      setCurrent(name);
      setNewName(null);
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      const why = (e as Error).message;
      setError(() => (t: Strings) => (status === 409 ? t.treeExists : status === 400 ? t.badTreeName : why));
    }
  };

  const deleteCurrentTree = async () => {
    if (!current || current === DEMO_TREE || busy) return;
    if (!window.confirm(t.confirmDeleteTree(titleOf(current), tree?.people.length ?? 0))) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteTree(current);
      const remaining = trees.filter((name) => name !== current);
      setTrees(remaining);
      setLoaded(null);
      setSelected(null);
      setCurrent(remaining.includes(DEMO_TREE) ? DEMO_TREE : remaining[0] ?? "");
      setNotice(() => (t: Strings) => t.treeDeleted);
    } catch (e) {
      setError(() => () => (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const chooseGed = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    setGedFile(null); setGedPreview(null);
    if (!file) return;
    setGedBusy(true); setError(null);
    try {
      const result = await api.previewGedcom(file, lang);
      setGedFile(file);
      setGedPreview(result);
      setGedName(treeSlug(file.name.replace(/\.ged(com)?$/i, "")) || "imported");
    } catch (e) { setError(() => () => (e as Error).message); }
    finally { setGedBusy(false); }
  };
  const importGed = async () => {
    if (!gedFile || !gedName || gedBusy) return;
    setGedBusy(true); setError(null);
    try {
      const result = await api.importGedcom(gedName, gedFile, lang);
      setTrees(names => [...names, result.name].sort());
      setGedFile(null); setGedPreview(null); setCurrent(result.name);
      setNotice(() => (t: Strings) => t.imported);
    } catch (e) { setError(() => () => (e as Error).message); }
    finally { setGedBusy(false); }
  };

  // Printing draws the tree that is on screen: the canvas takes the page's shape, fits the tree, then prints
  const printTree = () => setPrinting(true);
  useEffect(() => {
    document.documentElement.toggleAttribute("data-printing", printing);
    if (!printing) return;
    const done = () => setPrinting(false);
    window.addEventListener("afterprint", done, { once: true });
    return () => window.removeEventListener("afterprint", done);
  }, [printing]);

  const example = current === DEMO_TREE ? t.exampleDemo : t.exampleOther;
  const seconds = pending?.seconds?.toLocaleString(lang, { maximumFractionDigits: 1 });

  return (
    <I18n.Provider value={i18n}>
    <div className="app">
      <header className="bar">
        <span className="brand">{t.appName}</span>
        <div className="tree-heading">
          <h1 className="tree-title">{current ? displayTreeName(current, t) : t.appName}</h1>
          {current && current !== DEMO_TREE && (
            <button type="button" className="delete-tree" title={t.deleteTree}
              aria-label={t.deleteTreeOf(titleOf(current))} disabled={busy} onClick={deleteCurrentTree}>
              <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 6h18M8 6V4h8v2M5 6l1 14h12l1-14M10 10v7M14 10v7" />
              </svg>
            </button>
          )}
        </div>
        <select className="lang" aria-label={t.language} value={lang} onChange={(e) => changeLang(e.target.value as Lang)}>
          {LANGS.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
        </select>
        <div className="picker">
          {newName === null ? (
            <>
              <label htmlFor="tree">{t.tree}</label>
              <select id="tree" value={current} onChange={(e) => setCurrent(e.target.value)}>
                {trees.map((name) => <option key={name} value={name}>{displayTreeName(name, t)}</option>)}
              </select>
              <button type="button" className="link" onClick={() => setNewName("")}>{t.newTree}</button>
            </>
          ) : (
            <form className="new-tree" onSubmit={createTree}>
              <label htmlFor="new-tree">{t.name}</label>
              <input id="new-tree" value={newName} placeholder={t.newTreePlaceholder} autoFocus
                     onChange={(e) => setNewName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))} />
              <button type="submit" className="primary small" disabled={!newName}>{t.create}</button>
              <button type="button" className="link" onClick={() => setNewName(null)}>{t.cancel}</button>
            </form>
          )}
        </div>
      </header>

      <main className="main">
        <div className="canvas">
          <h2 className="print-title">{current ? displayTreeName(current, t) : t.appName}</h2>
          {shown && (
            <ReactFlowProvider>
              <TreeView tree={shown} treeName={current} direction={direction} selectedId={selected} onSelect={setSelected}
                        focus={focus} printing={printing} onReadyToPrint={() => window.print()}
                        fitKey={`${current}:${tree?.people.length ?? 0}:${pending ? "preview" : "saved"}`} />
            </ReactFlowProvider>
          )}
          {tree && tree.people.length > 0 && (
            <TreeTools people={tree.people} direction={direction} onDirection={changeDirection}
                       onFind={(id) => { setSelected(id); setFocus({ id, at: Date.now() }); }} />
          )}
          {tree && tree.people.length === 0 && !pending && (
            <div className="empty">
              <p>{t.emptyTree}</p>
              <p>{t.startWith(example)}</p>
            </div>
          )}
          {theme === "diodati" && <Bats key={current} />}
        </div>

        <aside className="panel">
          {current === DEMO_TREE && (
            <section className="diodati-intro" aria-label={t.introLabel}>
              <figure>
                <img src="/villa-diodati.png" alt={t.introPhotoAlt} />
                <figcaption>
                  <a href={VILLA_PHOTO.page} target="_blank" rel="noreferrer">
                    {t.photoCredit}: {VILLA_PHOTO.author}, {t.publicDomain}, Wikimedia Commons
                  </a>
                </figcaption>
              </figure>
              <div className="diodati-intro-content">
                <p className="diodati-intro-place">{t.introPlace}</p>
                <h2>{t.introTitle}</h2>
                <p>{t.introText}</p>
                <details>
                  <summary>{t.introMore}</summary>
                  <p>{t.introStory}</p>
                </details>
              </div>
            </section>
          )}
          <form className="tell" onSubmit={read}>
            <label htmlFor="sentence">{t.tell}</label>
            <textarea id="sentence" rows={3} value={sentence} placeholder={example}
                      disabled={!!pending} onChange={(e) => setSentence(e.target.value)} onKeyDown={onKeyDown} />
            <p className="tip">{t.tip}</p>
            {!pending && (
              <button type="submit" className="primary" disabled={busy || !sentence.trim() || !current}>
                {busy ? t.reading : t.read}
              </button>
            )}
          </form>

          {!pending && tree && <ByHand person={null} tree={tree} disabled={busy} onPreview={previewByHand} />}

          {error && <p className="error" role="alert">{error(t)}</p>}
          {notice && <p className="notice" role="status">{notice(t)}</p>}

          {pending && (
            <>
              {seconds && <p className="read-time">{t.readIn(seconds)}</p>}
              <PlanView plan={pending.plan} asked={pending.asked} choices={choices} busy={busy} onChoose={choose}
                        onConfirm={confirm} onDiscard={() => setPending(null)} />
            </>
          )}

          {!pending && !selectedPerson && tree && tree.people.length > 0 && (
            <p className="panel-hint">{t.clickHint}</p>
          )}

          {selectedPerson && shown && (
            <PersonDetail person={selectedPerson} tree={shown} treeName={current}
                          onClose={() => setSelected(null)} onPhotoChanged={reloadTree} />
          )}
          {selectedPerson && selectedPerson.id > 0 && !pending && tree && (
            <ByHand key={selectedPerson.id} person={selectedPerson} tree={tree} disabled={busy} onPreview={previewByHand} />
          )}
          {selectedPerson && selectedPerson.id > 0 && !pending && tree && (
            <PersonEditor key={`${current}:${selectedPerson.id}`} person={selectedPerson} treeName={current}
              onSaved={(data) => { setLoaded({ name: current, data }); setNotice(() => (t: Strings) => t.infoUpdated); }}
              onDeleted={(data) => { setLoaded({ name: current, data }); setSelected(null); setNotice(() => (t: Strings) => t.personDeleted); }} />
          )}
          {selectedPerson && selectedPerson.id > 0 && !pending && tree && (
            <RelationEditor key={`links:${current}:${selectedPerson.id}`} person={selectedPerson} tree={tree} treeName={current}
              onSaved={(data) => { setLoaded({ name: current, data }); setNotice(() => (t: Strings) => t.linkRemoved); }} />
          )}

          <section className="archive-tools" aria-labelledby="archive-title">
            <h3 id="archive-title">{t.archiveTitle}</h3>
            {current && (
              <div className="archive-actions">
                <button type="button" className="secondary" disabled={!tree?.people.length || printing} onClick={printTree}>{t.printTree}</button>
                <a className="secondary" href={registerUrl(current, lang, displayTreeName(current, t))} download={`${current}.pdf`}>{t.exportRegister}</a>
                <a className="secondary" href={gedcomUrl(current)} download={`${current}.ged`}>{t.exportGedcom}</a>
              </div>
            )}
            <p className="tip">{t.archiveNote}</p>
            <div className="gedcom-upload">
              <span className="gedcom-label">{t.importGedcom}</span>
              <input id="ged-file" className="gedcom-file-input" type="file"
                accept=".ged,.gedcom,text/plain" onChange={chooseGed} disabled={gedBusy} />
              <label htmlFor="ged-file" className={`secondary gedcom-upload-button${gedBusy ? " is-disabled" : ""}`}>{t.chooseFile}</label>
              <span className="gedcom-file-name" title={gedFile?.name ?? ""}>
                {gedBusy ? t.readingFile : gedFile?.name ?? t.noFile}
              </span>
            </div>
            {gedPreview && (
              <div className="ged-preview">
                <p>{t.gedcomFound(gedPreview.people, gedPreview.families)}</p>
                <p className="tip">{gedPreview.sample.join(", ")}</p>
                <label htmlFor="ged-name">{t.newTreeName}</label>
                <input id="ged-name" value={gedName} onChange={(e) => setGedName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-").slice(0, 41))} />
                <button type="button" className="primary" disabled={gedBusy || !gedName} onClick={importGed}>{t.importAsNew}</button>
              </div>
            )}
          </section>

          <footer className="panel-foot">
            {model ? t.footer(model) : t.noGemma}
          </footer>
        </aside>
      </main>
    </div>
    </I18n.Provider>
  );
}
