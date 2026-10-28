import { useState } from "react";
import { joinNames, useI18n } from "./i18n";
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

export const questionKey = (q: Question) => (q.kind === "person" ? q.name : `meaning:${q.word}`);

function QuestionBlock({ q, value, onChoose }: { q: Question; value: number | string | undefined; onChoose: Props["onChoose"] }) {
  const { t } = useI18n();
  const key = questionKey(q);
  if (q.kind === "person") {
    return (
      <fieldset className="question">
        <legend>{t.whichPerson(q.name)}</legend>
        {q.candidates.map((c) => (
          <label key={c.id} className="choice">
            <input type="radio" name={`q-${key}`} checked={value === c.id} onChange={() => onChoose(key, c.id)} />
            <span>{c.name}{c.born ? <span className="choice-note"> {t.bornYear(c.born)}</span> : null}</span>
          </label>
        ))}
        <label className="choice">
          <input type="radio" name={`q-${key}`} checked={value === "new"} onChange={() => onChoose(key, "new")} />
          <span>{t.someoneElse(q.name)}</span>
        </label>
      </fieldset>
    );
  }
  return (
    <fieldset className="question">
      <legend>{t.meaningQuestion(q.word, q.person, joinNames(t, q.of))}</legend>
      {q.options.map((option) => (
        <label key={option.id} className="choice">
          <input type="radio" name={`q-${key}`} checked={value === option.id} onChange={() => onChoose(key, option.id)} />
          <span>{option.label}</span>
        </label>
      ))}
    </fieldset>
  );
}

export function PlanView({ plan, asked, choices, busy, onChoose, onConfirm, onDiscard }: Props) {
  const { t } = useI18n();
  const [showKnown, setShowKnown] = useState(false);
  const nothingNew = plan.status === "save" && plan.summary.length === 0;

  return (
    <section className="plan" aria-live="polite">
      {plan.errors.length > 0 && (
        <div className="plan-errors">
          <h3>{t.doesntFit}</h3>
          <ul>{plan.errors.map((e) => <li key={e}>{e}</li>)}</ul>
          <p className="plan-hint">{t.nothingSaved}</p>
        </div>
      )}

      {asked.map((q) => (
        <QuestionBlock key={questionKey(q)} q={q} value={choices[questionKey(q)]} onChoose={onChoose} />
      ))}

      {plan.summary.length > 0 && plan.errors.length === 0 && (
        <div className="plan-summary">
          <h3>{plan.status === "ask" ? t.onceAnswered : t.willAdd}</h3>
          <ul>{plan.summary.map((s) => <li key={s}>{s}</li>)}</ul>
        </div>
      )}

      {nothingNew && <p className="plan-nothing">{t.alreadyKnows}</p>}

      {plan.warnings.length > 0 && (
        <ul className="plan-warnings">{plan.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
      )}

      {plan.known.length > 0 && (
        <div className="plan-known">
          <button type="button" className="link" onClick={() => setShowKnown(!showKnown)} aria-expanded={showKnown}>
            {showKnown ? t.hideKnown(plan.known.length) : t.showKnown(plan.known.length)}
          </button>
          {showKnown && <ul>{plan.known.map((k) => <li key={k}>{k}</li>)}</ul>}
        </div>
      )}

      <div className="plan-actions">
        {plan.status !== "reject" && !nothingNew && (
          <button type="button" className="primary" disabled={busy || plan.status !== "save"} onClick={onConfirm}>
            {t.addToTree}
          </button>
        )}
        <button type="button" className="secondary" disabled={busy} onClick={onDiscard}>
          {plan.status === "reject" || nothingNew ? t.clear : t.discard}
        </button>
      </div>
    </section>
  );
}
