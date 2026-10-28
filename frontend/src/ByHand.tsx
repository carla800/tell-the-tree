import { useState, type FormEvent } from "react";
import { useI18n } from "./i18n";
import type { Choices, Person, TreeData } from "./types";

/**
 * Adding people without a sentence. The form writes the same operations Gemma writes
 * (backend/words.py knows these words), so they go through the same checks and the same preview.
 */
const RELATIVES = ["mother", "father", "daughter", "son", "sister", "brother", "wife", "husband", "partner"];
const CHILDREN = ["daughter", "son"];

interface Props {
  person: Person | null;      // the person clicked in the tree; null adds someone on their own
  tree: TreeData;
  disabled: boolean;
  onPreview: (modelOps: unknown[], choices: Choices) => void;
}

export function ByHand({ person, tree, disabled, onPreview }: Props) {
  const { t } = useI18n();
  const partners = person
    ? tree.families
        .filter((f) => f.partners.includes(person.id))
        .map((f) => tree.people.find((p) => p.id !== person.id && f.partners.includes(p.id)))
        .filter((p): p is Person => !!p)
    : [];
  const [open, setOpen] = useState(false);
  const [relative, setRelative] = useState("daughter");
  const [name, setName] = useState("");
  const [otherParent, setOtherParent] = useState(partners.length === 1 ? String(partners[0].id) : "");
  const [born, setBorn] = useState("");
  const [place, setPlace] = useState("");

  if (!open) {
    return (
      <button type="button" className="link by-hand-open" disabled={disabled} onClick={() => setOpen(true)}>
        {person ? t.addRelativeOf(person.name) : t.addPersonByHand}
      </button>
    );
  }

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const newName = name.trim();
    if (!newName) return;
    const ops: unknown[] = [];
    const choices: Choices = {};
    if (person) {
      const other = CHILDREN.includes(relative) ? partners.find((p) => String(p.id) === otherParent) : undefined;
      ops.push({ op: "relation", person: newName, word: relative, of: other ? [person.name, other.name] : [person.name] });
      choices[person.name] = person.id;          // the person you clicked, even if another one has the same name
      if (other) choices[other.name] = other.id;
    } else {
      ops.push({ op: "person", name: newName });
    }
    if (born.trim() || place.trim()) {
      ops.push({ op: "event", person: newName, type: "birth", date: born.trim() || undefined, place: place.trim() || undefined });
    }
    onPreview(ops, choices);
    setOpen(false);
    setName("");
    setBorn("");
    setPlace("");
  };

  return (
    <form className="by-hand" onSubmit={submit}>
      {person && (
        <label>
          <span>{t.whoIsIt}</span>
          <select value={relative} onChange={(e) => setRelative(e.target.value)}>
            {RELATIVES.map((r) => <option key={r} value={r}>{t.relativeOf(r, person.name)}</option>)}
          </select>
        </label>
      )}
      <label>
        <span>{t.fullName}</span>
        <input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
      </label>
      {person && CHILDREN.includes(relative) && partners.length > 0 && (
        <label>
          <span>{t.otherParent}</span>
          <select value={otherParent} onChange={(e) => setOtherParent(e.target.value)}>
            {partners.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            <option value="">{t.otherParentUnknown}</option>
          </select>
        </label>
      )}
      <label>
        <span>{t.birthDate}</span>
        <input value={born} placeholder={t.birthDatePlaceholder} onChange={(e) => setBorn(e.target.value)} />
      </label>
      <label>
        <span>{t.birthPlace}</span>
        <input value={place} onChange={(e) => setPlace(e.target.value)} />
      </label>
      <div className="by-hand-actions">
        <button type="submit" className="primary small" disabled={disabled || !name.trim()}>{t.showInTree}</button>
        <button type="button" className="link" onClick={() => setOpen(false)}>{t.cancel}</button>
      </div>
    </form>
  );
}
