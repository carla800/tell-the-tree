import { useState } from "react";
import { useI18n } from "./i18n";
import type { TreeDirection } from "./layout";
import type { Person } from "./types";

/** Over the tree: find a person (the view moves to them) and read the tree across or down. */
export function TreeTools({ people, direction, onDirection, onFind }: {
  people: Person[];
  direction: TreeDirection;
  onDirection: (d: TreeDirection) => void;
  onFind: (id: number) => void;
}) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const q = query.trim().toLocaleLowerCase();
  const found = q
    ? people.filter((p) => [p.name, p.birth_name, p.also_known_as].some((n) => n?.toLocaleLowerCase().includes(q))).slice(0, 12)
    : [];

  return (
    <div className="tree-tools">
      <div className="tree-search">
        <input type="search" aria-label={t.searchLabel} placeholder={t.searchPlaceholder} value={query}
               onChange={(e) => setQuery(e.target.value)}
               onKeyDown={(e) => { if (e.key === "Enter" && found[0]) { onFind(found[0].id); setQuery(""); } }} />
        {q && (
          <div className="search-results" role="listbox" aria-label={t.searchLabel}>
            {found.length === 0 && <p className="search-empty">{t.noMatches}</p>}
            {found.map((p) => (
              <button key={p.id} type="button" role="option" aria-selected="false"
                      onClick={() => { onFind(p.id); setQuery(""); }}>
                {p.name}{p.born ? <span className="choice-note"> {t.bornYear(p.born)}</span> : null}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="view-switch" role="group" aria-label={t.view}>
        {(["LR", "TB"] as const).map((d) => (
          <button key={d} type="button" aria-pressed={direction === d} onClick={() => onDirection(d)}>
            {d === "LR" ? t.horizontal : t.vertical}
          </button>
        ))}
      </div>
    </div>
  );
}
