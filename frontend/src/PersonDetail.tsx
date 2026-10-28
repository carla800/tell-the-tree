import type { Person, TreeData } from "./types";

const EVENT_LABEL: Record<string, string> = {
  birth: "Born",
  death: "Died",
  marriage: "Married",
  divorce: "Divorced",
  residence: "Lived",
  occupation: "Work",
  other: "Event",
};

const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
  "August", "September", "October", "November", "December"];

/** "1797-08-30" becomes "30 August 1797". Anything else is shown as written. */
function readableDate(text: string | null): string | null {
  const m = text?.match(/^(\d{4})-(\d{2})(?:-(\d{2}))?$/);
  if (!m) return text;
  const month = MONTHS[Number(m[2]) - 1];
  return [m[3] ? String(Number(m[3])) : null, month, m[1]].filter(Boolean).join(" ");
}

function Source({ text }: { text: string | null }) {
  if (!text) return null;
  if (/^https?:\/\//.test(text)) {
    return <a className="source" href={text} target="_blank" rel="noreferrer">Source: {new URL(text).hostname}</a>;
  }
  return <span className="source">{text}</span>;
}

export function PersonDetail({ person, tree, onClose }: { person: Person; tree: TreeData; onClose: () => void }) {
  const familyEvents = tree.families
    .filter((f) => f.partners.includes(person.id))
    .flatMap((f) => {
      const partner = tree.people.find((p) => p.id !== person.id && f.partners.includes(p.id));
      return f.events.map((e) => ({ ...e, with: partner?.name }));
    });
  const events = [...person.events.map((e) => ({ ...e, with: undefined as string | undefined })), ...familyEvents];

  return (
    <section className="detail" aria-label={`About ${person.name}`}>
      <div className="detail-head">
        <h2>{person.name}</h2>
        <button type="button" className="link" onClick={onClose}>Close</button>
      </div>
      {person.birth_name && person.birth_name !== person.name && <p className="detail-sub">Born {person.birth_name}</p>}
      {person.also_known_as && <p className="detail-sub">Also known as {person.also_known_as}</p>}
      {person.notes && <p className="detail-notes">{person.notes}</p>}
      {events.length > 0 ? (
        <ul className="events">
          {events.map((e) => (
            <li key={`${e.type}-${e.id}`}>
              <span className="event-label">{EVENT_LABEL[e.type] ?? e.type}</span>
              <span className="event-what">
                {e.with && <span className="event-with">{e.with}</span>}
                {[readableDate(e.date_text), e.place, e.description].filter(Boolean).join(", ") || "date unknown"}
              </span>
              <Source text={e.source} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="detail-empty">No dates or places yet. Tell the tree, for example: “{person.name} was born in…”.</p>
      )}
    </section>
  );
}
