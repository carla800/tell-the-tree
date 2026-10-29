import { useState, type FormEvent } from "react";
import { api, ApiError } from "./api";
import { useI18n } from "./i18n";
import type { Person, TreeData } from "./types";

type Field = "name" | "birth_name" | "also_known_as" | "birth_date" | "birth_place" | "death_date" | "death_place" | "notes";

/** Edit or delete a person. The server checks the dates exactly as it checks a sentence. */
export function PersonEditor({ person, treeName, onSaved, onDeleted }: {
  person: Person; treeName: string;
  onSaved: (data: TreeData) => void; onDeleted: (data: TreeData) => void;
}) {
  const { t, lang } = useI18n();
  const first = (kind: string) => person.events.find((e) => e.type === kind);
  const [form, setForm] = useState({
    name: person.name, birth_name: person.birth_name ?? "", also_known_as: person.also_known_as ?? "",
    sex: person.sex, notes: person.notes ?? "",
    birth_date: first("birth")?.date_text ?? "", birth_place: first("birth")?.place ?? "",
    death_date: first("death")?.date_text ?? "", death_place: first("death")?.place ?? "",
  });
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  const field = (key: Field, label: string) => (
    <label className="edit-field">
      <span>{label}</span>
      {key === "notes"
        ? <textarea rows={3} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
        : <input value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />}
    </label>
  );

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErrors([]);
    try {
      onSaved(await api.editPerson(treeName, person.id, form, lang));
      setEditing(false);
    } catch (err) {
      setErrors(err instanceof ApiError && err.errors.length ? err.errors : [(err as Error).message]);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!window.confirm(t.confirmDeletePerson(person.name))) return;
    setBusy(true);
    setErrors([]);
    try {
      onDeleted(await api.deletePerson(treeName, person.id));
    } catch (err) {
      setErrors([(err as Error).message]);
    } finally {
      setBusy(false);
    }
  };

  if (!editing) {
    return (
      <section className="person-editor">
        <button type="button" className="secondary" disabled={busy} onClick={() => setEditing(true)}>{t.editInfo}</button>
        <button type="button" className="link danger" disabled={busy} onClick={remove}>{t.deletePerson}</button>
        {errors.length > 0 && <p className="error" role="alert">{errors[0]}</p>}
      </section>
    );
  }

  return (
    <form className="edit-form" onSubmit={save}>
      <h3>{t.editInfo}</h3>
      {field("name", t.fieldName)}
      {field("birth_name", t.fieldBirthName)}
      {field("also_known_as", t.fieldOtherNames)}
      <label className="edit-field">
        <span>{t.fieldSex}</span>
        <select value={form.sex} onChange={(e) => setForm({ ...form, sex: e.target.value as Person["sex"] })}>
          {(["U", "F", "M"] as const).map((s) => <option key={s} value={s}>{t.sexes[s]}</option>)}
        </select>
      </label>
      {field("birth_date", t.fieldBirthDate)}
      {field("birth_place", t.fieldBirthPlace)}
      {field("death_date", t.fieldDeathDate)}
      {field("death_place", t.fieldDeathPlace)}
      {field("notes", t.fieldNotes)}
      {errors.length > 0 && (
        <div className="plan-errors" role="alert">
          <h3>{t.doesntFit}</h3>
          <ul>{errors.map((e) => <li key={e}>{e}</li>)}</ul>
        </div>
      )}
      <div className="edit-actions">
        <button type="submit" className="primary" disabled={busy || !form.name.trim()}>{t.save}</button>
        <button type="button" className="secondary" onClick={() => { setEditing(false); setErrors([]); }} disabled={busy}>{t.cancel}</button>
      </div>
    </form>
  );
}
