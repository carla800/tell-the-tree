import type { Change, Family, Person, TreeData } from "./types";

const yearOf = (text: unknown): number | null => {
  const match = String(text ?? "").match(/\b(1\d{3}|20\d{2})\b/);
  return match ? Number(match[1]) : null;
};

/** The tree as it would look after the sentence, with everything new marked `pending`. */
export function withPreview(tree: TreeData, changes: Change[]): TreeData {
  const people = new Map<number, Person>(tree.people.map((p) => [p.id, { ...p }]));
  const families = new Map<number, Family>(
    tree.families.map((f) => [f.id, { ...f, partners: [...f.partners], children: [...f.children] }]),
  );
  const claims = [...tree.claims];

  for (const c of changes) {
    switch (c.action) {
      case "add_person": {
        const id = c.tmp as number;
        people.set(id, {
          id, name: c.name as string, birth_name: (c.birth_name as string) ?? null, also_known_as: null,
          sex: (c.sex as Person["sex"]) ?? "U", notes: null, born: null, died: null, events: [], photo: null, pending: true,
        });
        break;
      }
      case "update_person": {
        const p = people.get(c.id as number);
        if (p) Object.assign(p, c.fields as object);
        break;
      }
      case "add_family": {
        const id = c.tmp as number;
        families.set(id, {
          id, partners: c.partners as (number | null)[], union_type: c.union_type as string,
          children: [], events: [], pending: true,
        });
        break;
      }
      case "update_family": {
        const f = families.get(c.id as number);
        const fields = c.fields as Partial<Family>;
        if (f && fields.partners) {
          f.partners = fields.partners;
          f.pending = true;
        }
        if (f && fields.union_type) f.union_type = fields.union_type;
        break;
      }
      case "add_child": {
        const f = families.get(c.family as number);
        if (f) f.children = [...f.children, { id: c.child as number, relation: c.relation as string, pending: true }];
        break;
      }
      case "add_event": {
        const p = c.person != null ? people.get(c.person as number) : undefined;
        if (p && c.type === "birth") p.born = yearOf(c.date_text);
        if (p && c.type === "death") p.died = yearOf(c.date_text);
        break;
      }
      case "add_claim":
        claims.push({ id: -claims.length - 1000, a_id: c.a as number, b_id: c.b as number, kind: c.kind as string, sentence: null, pending: true });
        break;
    }
  }
  return { people: [...people.values()], families: [...families.values()], claims };
}
