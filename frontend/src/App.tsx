import { useCallback, useEffect, useMemo, useState, type FormEvent, type KeyboardEvent } from "react";
import { ReactFlowProvider } from "@xyflow/react";
import { api } from "./api";
import { Bats } from "./Bats";
import { PersonDetail } from "./PersonDetail";
import { PlanView, questionKey } from "./PlanView";
import { withPreview } from "./preview";
import { TreeView } from "./TreeView";
import type { Choices, Plan, Question, TreeData } from "./types";

// The project's name: change it here (and in index.html)
const APP_NAME = "Family tree";
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

const remembered = {
  get: () => { try { return localStorage.getItem("tree"); } catch { return null; } },
  set: (name: string) => { try { localStorage.setItem("tree", name); } catch { /* private window: fine */ } },
};

export default function App() {
  const [trees, setTrees] = useState<string[]>([]);
  const [current, setCurrent] = useState("");
  const [tree, setTree] = useState<TreeData | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const [sentence, setSentence] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [choices, setChoices] = useState<Choices>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [newName, setNewName] = useState<string | null>(null);

  const theme = current === DEMO_TREE ? "diodati" : "register";
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);

  useEffect(() => {
    api.health().then((h) => setModel(h.model)).catch(() => setModel(null));
    api.listTrees()
      .then((names) => {
        setTrees(names);
        const last = remembered.get();
        setCurrent(last && names.includes(last) ? last : names.includes(DEMO_TREE) ? DEMO_TREE : names[0] ?? "");
      })
      .catch(() => setError("Can't reach the app's server. Start it with: uvicorn backend.api:app --reload"));
  }, []);

  useEffect(() => {
    if (!current) return;
    remembered.set(current);
    setTree(null);
    setPending(null);
    setSelected(null);
    setNotice(null);
    setError(null);
    setSentence("");
    api.getTree(current).then(setTree).catch((e: Error) => setError(e.message));
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
      const result = await api.parse(current, sentence.trim());
      setChoices({});
      setPending({ sentence: sentence.trim(), modelOps: result.model_ops, plan: result.plan,
                   asked: addQuestions([], result.plan), seconds: result.seconds });
    } catch (e) {
      setError(`Gemma couldn't read the sentence (${(e as Error).message}). Is Ollama running?`);
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
      const { plan } = await api.plan(current, pending.modelOps, next);
      setPending({ ...pending, plan, asked: addQuestions(pending.asked, plan) });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [choices, current, pending]);

  const confirm = async () => {
    if (!pending) return;
    setBusy(true);
    try {
      const result = await api.apply(current, pending.sentence, pending.modelOps, choices);
      setTree(result.tree);
      setPending(null);
      setSentence("");
      setNotice("Added to the tree.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const createTree = async (event: FormEvent) => {
    event.preventDefault();
    if (!newName) return;
    try {
      const { name } = await api.createTree(newName.trim());
      setTrees((t) => [...t, name].sort());
      setCurrent(name);
      setNewName(null);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const example = current === DEMO_TREE
    ? "Percy Florence Shelley was the son of Mary Shelley."
    : "Maria Rossi è la moglie di Marco Rossi.";

  return (
    <div className="app">
      <header className="bar">
        <span className="brand">{APP_NAME}</span>
        <h1 className="tree-title">{current ? titleOf(current) : APP_NAME}</h1>
        <div className="picker">
          {newName === null ? (
            <>
              <label htmlFor="tree">Tree</label>
              <select id="tree" value={current} onChange={(e) => setCurrent(e.target.value)}>
                {trees.map((t) => <option key={t} value={t}>{titleOf(t)}</option>)}
              </select>
              <button type="button" className="link" onClick={() => setNewName("")}>New tree</button>
            </>
          ) : (
            <form className="new-tree" onSubmit={createTree}>
              <label htmlFor="new-tree">Name</label>
              <input id="new-tree" value={newName} placeholder="rossi-family" autoFocus
                     onChange={(e) => setNewName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))} />
              <button type="submit" className="primary small" disabled={!newName}>Create</button>
              <button type="button" className="link" onClick={() => setNewName(null)}>Cancel</button>
            </form>
          )}
        </div>
      </header>

      <main className="main">
        <div className="canvas">
          {shown && (
            <ReactFlowProvider>
              <TreeView tree={shown} selectedId={selected} onSelect={setSelected}
                        fitKey={`${current}:${tree?.people.length ?? 0}:${pending ? "preview" : "saved"}`} />
            </ReactFlowProvider>
          )}
          {tree && tree.people.length === 0 && !pending && (
            <div className="empty">
              <p>This tree is empty.</p>
              <p>Start with one sentence, for example “{example}”</p>
            </div>
          )}
          {theme === "diodati" && <Bats key={current} />}
        </div>

        <aside className="panel">
          <form className="tell" onSubmit={read}>
            <label htmlFor="sentence">Tell the tree something</label>
            <textarea id="sentence" rows={3} value={sentence} placeholder={example}
                      disabled={!!pending} onChange={(e) => setSentence(e.target.value)} onKeyDown={onKeyDown} />
            <p className="tip">One fact per sentence works best. Names, dates and places are kept exactly as you write them.</p>
            {!pending && (
              <button type="submit" className="primary" disabled={busy || !sentence.trim() || !current}>
                {busy ? "Reading…" : "Read sentence"}
              </button>
            )}
          </form>

          {error && <p className="error" role="alert">{error}</p>}
          {notice && <p className="notice" role="status">{notice}</p>}

          {pending && (
            <>
              <p className="read-time">Read in {pending.seconds} s on this computer.</p>
              <PlanView plan={pending.plan} asked={pending.asked} choices={choices} busy={busy} onChoose={choose}
                        onConfirm={confirm} onDiscard={() => setPending(null)} />
            </>
          )}

          {!pending && !selectedPerson && tree && tree.people.length > 0 && (
            <p className="panel-hint">Click a person to see their dates, places and the sentence each fact came from.</p>
          )}

          {selectedPerson && shown && (
            <PersonDetail person={selectedPerson} tree={shown} onClose={() => setSelected(null)} />
          )}

          <footer className="panel-foot">
            {model ? <>Sentences are read by {model} with Ollama, on this computer. The tree is a file in the app’s trees folder.</>
                   : <>Gemma isn’t reachable yet.</>}
          </footer>
        </aside>
      </main>
    </div>
  );
}
