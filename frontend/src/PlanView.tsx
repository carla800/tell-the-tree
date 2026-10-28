import { useState } from "react";
import type { Choices, Plan, Question } from "./types";

interface Props {
  plan: Plan;
  asked: Question[];        // every question asked for this sentence, so answered ones stay visible
  choices: Choices;
  busy: boolean;
  onChoose: (key: string, value: number | string) => void;
  onConfirm: () => void;
  onDiscard: () => void;
}

function QuestionBlock({ q, value, onChoose }: { q: Question; value: number | string | undefined; onChoose: Props["onChoose"] }) {
  if (q.kind === "person") {
    const key = q.name;
    return (
      <fieldset className="question">
        <legend>Which {q.name} do you mean?</legend>
        {q.candidates.map((c) => (
          <label key={c.id} className="choice">
            <input type="radio" name={`q-${key}`} checked={value === c.id} onChange={() => onChoose(key, c.id)} />
            <span>{c.name}{c.born ? <span className="choice-note"> born {c.born}</span> : null}</span>
          </label>
        ))}
        <label className="choice">
          <input type="radio" name={`q-${key}`} checked={value === "new"} onChange={() => onChoose(key, "new")} />
          <span>Someone else called {q.name}</span>
        </label>
      </fieldset>
    );
  }
  const key = `meaning:${q.word}`;
  return (
    <fieldset className="question">
      <legend>
        “{q.word}” can mean two things here. {q.person} is {q.of.join(" and ")}’s…
      </legend>
      {q.options.map((label) => (
        <label key={label} className="choice">
          <input type="radio" name={`q-${key}`} checked={value === label} onChange={() => onChoose(key, label)} />
          <span>{label}</span>
        </label>
      ))}
    </fieldset>
  );
}

export const questionKey = (q: Question) => (q.kind === "person" ? q.name : `meaning:${q.word}`);

export function PlanView({ plan, asked, choices, busy, onChoose, onConfirm, onDiscard }: Props) {
  const [showKnown, setShowKnown] = useState(false);
  const valueFor = (q: Question) => choices[questionKey(q)];
  const nothingNew = plan.status === "save" && plan.summary.length === 0;

  return (
    <section className="plan" aria-live="polite">
      {plan.errors.length > 0 && (
        <div className="plan-errors">
          <h3>This doesn’t fit the tree</h3>
          <ul>{plan.errors.map((e) => <li key={e}>{e}</li>)}</ul>
          <p className="plan-hint">Nothing will be saved. Check the sentence, or the facts already in the tree.</p>
        </div>
      )}

      {asked.map((q) => (
        <QuestionBlock key={questionKey(q)} q={q} value={valueFor(q)} onChoose={onChoose} />
      ))}

      {plan.summary.length > 0 && plan.errors.length === 0 && (
        <div className="plan-summary">
          <h3>{plan.status === "ask" ? "Once you answer, this will be added" : "This will be added"}</h3>
          <ul>{plan.summary.map((s) => <li key={s}>{s}</li>)}</ul>
        </div>
      )}

      {nothingNew && <p className="plan-nothing">The tree already knows this. Nothing to add.</p>}

      {plan.warnings.length > 0 && (
        <ul className="plan-warnings">{plan.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
      )}

      {plan.known.length > 0 && (
        <div className="plan-known">
          <button type="button" className="link" onClick={() => setShowKnown(!showKnown)} aria-expanded={showKnown}>
            {showKnown ? "Hide" : "Show"} what the tree already knows ({plan.known.length})
          </button>
          {showKnown && <ul>{plan.known.map((k) => <li key={k}>{k}</li>)}</ul>}
        </div>
      )}

      <div className="plan-actions">
        {plan.status !== "reject" && !nothingNew && (
          <button type="button" className="primary" disabled={busy || plan.status !== "save"} onClick={onConfirm}>
            Add to tree
          </button>
        )}
        <button type="button" className="secondary" disabled={busy} onClick={onDiscard}>
          {plan.status === "reject" || nothingNew ? "Clear" : "Discard"}
        </button>
      </div>
    </section>
  );
}
