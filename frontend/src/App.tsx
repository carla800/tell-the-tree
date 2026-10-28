import { useCallback, useEffect, useMemo, useState, type FormEvent, type KeyboardEvent } from "react";
import { ReactFlowProvider } from "@xyflow/react";
import { api, ApiError } from "./api";
import { Bats } from "./Bats";
import { PersonDetail } from "./PersonDetail";
import { PlanView, questionKey } from "./PlanView";
import { withPreview } from "./preview";
import { I18n, LANGS, rememberLang, startingLang, STRINGS, type Lang, type Strings } from "./i18n";
import { TreeView } from "./TreeView";
import type { Choices, Plan, Question, TreeData } from "./types";

// The project's name is in i18n.ts (appName) and index.html
const DEMO_TREE = "villa-diodati";

interface Pending {
  sentence: string;
  modelOps: unknown[];
  plan: Plan;
  asked: Question[];
  seconds: number;
}

const addQuestions = (asked: Question[], plan: Plan) =>
  [...asked, ...plan.questions.filter((q) => !asked.some((a) => questionKey(a) === questionKey(q)))];

const titleOf = (slug: string) => slug.split("-").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");

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
                   asked: addQuestions([], result.plan), seconds: result.seconds });
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

  const reloadTree = () => {
    const name = current;
    api.getTree(name).then((data) => setLoaded({ name, data })).catch(() => undefined);
  };

  const confirm = async () => {
    if (!pending) return;
    setBusy(true);
    try {
      const result = await api.apply(current, pending.sentence, pending.modelOps, choices, lang);
      setLoaded({ name: current, data: result.tree });
      setPending(null);
      setSentence("");
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

  const example = current === DEMO_TREE ? t.exampleDemo : t.exampleOther;
  const seconds = pending?.seconds.toLocaleString(lang, { maximumFractionDigits: 1 });

  return (
    <I18n.Provider value={i18n}>
    <div className="app">
      <header className="bar">
        <span className="brand">{t.appName}</span>
        <h1 className="tree-title">{current ? titleOf(current) : t.appName}</h1>
        <select className="lang" aria-label={t.language} value={lang} onChange={(e) => changeLang(e.target.value as Lang)}>
          {LANGS.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
        </select>
        <div className="picker">
          {newName === null ? (
            <>
              <label htmlFor="tree">{t.tree}</label>
              <select id="tree" value={current} onChange={(e) => setCurrent(e.target.value)}>
                {trees.map((name) => <option key={name} value={name}>{titleOf(name)}</option>)}
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
          {shown && (
            <ReactFlowProvider>
              <TreeView tree={shown} treeName={current} selectedId={selected} onSelect={setSelected}
                        fitKey={`${current}:${tree?.people.length ?? 0}:${pending ? "preview" : "saved"}`} />
            </ReactFlowProvider>
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

          {error && <p className="error" role="alert">{error(t)}</p>}
          {notice && <p className="notice" role="status">{notice(t)}</p>}

          {pending && (
            <>
              <p className="read-time">{t.readIn(seconds ?? "")}</p>
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

          <footer className="panel-foot">
            {model ? t.footer(model) : t.noGemma}
          </footer>
        </aside>
      </main>
    </div>
    </I18n.Provider>
  );
}
