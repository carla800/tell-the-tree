import { useState } from "react";
import { api } from "./api";
import { joinNames, useI18n } from "./i18n";
import type { Family, Person, TreeData } from "./types";

/**
 * Fixing a wrong link: take a person out of a couple, or a child out of a family.
 * Nobody is deleted here. New links are added with a sentence or with "Add a relative",
 * so they go through the engine's checks.
 */
export function RelationEditor({ person, tree, treeName, onSaved }: {
  person: Person; tree: TreeData; treeName: string; onSaved: (data: TreeData) => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const nameOf = (id: number) => tree.people.find((p) => p.id === id)?.name ?? "?";
  const families = tree.families.filter((f) => f.partners.includes(person.id) || f.children.some((c) => c.id === person.id));
  const title = (f: Family) => {
    const partners = f.partners.filter((x): x is number => x != null).map(nameOf);
    return partners.length ? t.familyOf(joinNames(t, partners)) : t.familyNoParents;
  };

  const remove = async (action: "remove_partner" | "remove_child", family: Family, id: number) => {
    if (!window.confirm(t.confirmRemoveLink(nameOf(id), title(family)))) return;
    setBusy(true);
    setError("");
    try {
      onSaved(await api.removeLink(treeName, action, family.id, id));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return <button type="button" className="link" onClick={() => setOpen(true)}>{t.fixLinks}</button>;
  }

  return (
    <section className="relation-editor" aria-label={t.fixLinks}>
      <div className="relation-head">
        <h3>{t.fixLinks}</h3>
        <button type="button" className="link" onClick={() => setOpen(false)}>{t.close}</button>
      </div>
      {families.length === 0 && <p className="tip">{t.noLinks}</p>}
      {families.map((f) => (
        <div key={f.id} className="relation-family">
          <strong>{title(f)}</strong>
          {f.partners.filter((x): x is number => x != null).map((id) => (
            <div key={`p${id}`} className="relation-line">
              <span>{nameOf(id)} <span className="relation-kind">{t.linkPartner}</span></span>
              <button type="button" className="link" disabled={busy} onClick={() => remove("remove_partner", f, id)}>{t.removeLink}</button>
            </div>
          ))}
          {f.children.map((c) => (
            <div key={`c${c.id}`} className="relation-line">
              <span>{nameOf(c.id)} <span className="relation-kind">{t.linkChild[c.relation] ?? c.relation}</span></span>
              <button type="button" className="link" disabled={busy} onClick={() => remove("remove_child", f, c.id)}>{t.removeLink}</button>
            </div>
          ))}
        </div>
      ))}
      <p className="tip">{t.linksHint}</p>
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  );
}
