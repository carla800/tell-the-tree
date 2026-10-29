import { useRef, useState, type ChangeEvent } from "react";
import { api, photoUrl, shrinkPicture } from "./api";
import { useI18n, type Strings } from "./i18n";
import type { Person, TreeData } from "./types";

/** "1797-08-30" becomes "30 August 1797" / "30 agosto 1797", "about 1890" becomes "circa 1890".
 *  Anything else is shown as written. */
function readableDate(t: Strings, text: string | null): string | null {
  const qualified = text?.match(/^(about|before|after)\s+(.+)$/);
  if (qualified) return `${t.dateQualifiers[qualified[1]]} ${readableDate(t, qualified[2])}`;
  const m = text?.match(/^(\d{4})-(\d{2})(?:-(\d{2}))?$/);
  if (!m) return text;
  return t.dayMonthYear(m[3] ? String(Number(m[3])) : null, t.months[Number(m[2]) - 1], m[1]);
}

function Source({ text }: { text: string | null }) {
  const { t } = useI18n();
  if (!text) return null;
  if (/^https?:\/\//.test(text)) {
    return <a className="source" href={text} target="_blank" rel="noreferrer">{t.sourceWeb(new URL(text).hostname)}</a>;
  }
  if (text === "By hand") return <span className="source">{t.byHand}</span>;
  if (text === "GEDCOM import") return <span className="source">{t.gedcomSource}</span>;
  const sentence = text.match(/^From: "(.*)"$/s);
  return <span className="source">{sentence ? t.fromSentence(sentence[1]) : text}</span>;
}

interface Props {
  person: Person;
  tree: TreeData;
  treeName: string;
  onClose: () => void;
  onPhotoChanged: () => void;
}

function Photo({ person, treeName, onPhotoChanged }: Omit<Props, "tree" | "onClose">) {
  const { t } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (person.id < 0) return null;   // still in the preview: no photo until it's saved

  const pick = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await api.setPhoto(treeName, person.id, await shrinkPicture(file));
      onPhotoChanged();
    } catch {
      setError(t.photoUnreadable);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    try {
      await api.removePhoto(treeName, person.id);
      onPhotoChanged();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="detail-photo">
      {person.photo && (
        <img src={photoUrl(treeName, person.id, person.photo)} alt={t.photoOf(person.name)} />
      )}
      <div className="detail-photo-actions">
        <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={pick} />
        <button type="button" className="link" disabled={busy} onClick={() => input.current?.click()}>
          {busy ? t.photoSaving : person.photo ? t.changePhoto : t.addPhoto}
        </button>
        {person.photo && !busy && <button type="button" className="link" onClick={remove}>{t.removePhoto}</button>}
        {error ? <p className="detail-photo-note" role="alert">{error}</p>
               : !person.photo && <p className="detail-photo-note">{t.photoNote}</p>}
      </div>
    </div>
  );
}

export function PersonDetail({ person, tree, treeName, onClose, onPhotoChanged }: Props) {
  const { t } = useI18n();
  const familyEvents = tree.families
    .filter((f) => f.partners.includes(person.id))
    .flatMap((f) => {
      const partner = tree.people.find((p) => p.id !== person.id && f.partners.includes(p.id));
      return f.events.map((e) => ({ ...e, with: partner?.name }));
    });
  const events = [...person.events.map((e) => ({ ...e, with: undefined as string | undefined })), ...familyEvents];

  return (
    <section className="detail" aria-label={person.name}>
      <div className="detail-head">
        <h2>{person.name}</h2>
        <button type="button" className="link" onClick={onClose}>{t.close}</button>
      </div>
      {person.birth_name && person.birth_name !== person.name && <p className="detail-sub">{t.bornAs(person.birth_name)}</p>}
      {person.also_known_as && <p className="detail-sub">{t.alsoKnownAs(person.also_known_as)}</p>}
      <Photo person={person} treeName={treeName} onPhotoChanged={onPhotoChanged} />
      {person.notes && <p className="detail-notes">{person.notes}</p>}
      {events.length > 0 ? (
        <ul className="events">
          {events.map((e) => (
            <li key={`${e.type}-${e.id}`}>
              <span className="event-label">{t.events[e.type] ?? e.type}</span>
              <span className="event-what">
                {e.with && <span className="event-with">{e.with}</span>}
                {[readableDate(t, e.date_text), e.place, e.description].filter(Boolean).join(", ") || t.dateUnknown}
              </span>
              <Source text={e.source} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="detail-empty">{t.noEvents(person.name)}</p>
      )}
    </section>
  );
}
