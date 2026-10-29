import dagre from "@dagrejs/dagre";
import type { Edge, Node } from "@xyflow/react";
import type { Person, TreeData } from "./types";

export type TreeDirection = "LR" | "TB";

export const PERSON_W = 196;
export const PERSON_H = 74;
const KNOT = 14;

export type PersonNodeData = {
  person: Person;
  selected: boolean;
  photoUrl: string | null;
  direction: TreeDirection;
};
export type KnotNodeData = {
  unionType: string;
  pending: boolean;
  direction: TreeDirection;
};

export interface LayoutOptions {
  direction: TreeDirection;
  selectedId: number | null;
  heights: Record<string, number>; // measured card heights
  claimLabels: Record<string, string>; // "half_sibling" -> "half-sibling", in the interface's language
  photoUrl: (p: Person) => string | null;
}

/** A first guess, used until the card has been drawn and measured. */
function guessHeight(p: Person): number {
  const nameLines = p.name.length > (p.photo ? 14 : 21) ? 2 : 1;
  const birth =
    p.birth_name && p.birth_name !== p.name
      ? p.birth_name.length > 21
        ? 2
        : 1
      : 0;
  return PERSON_H + (nameLines - 1) * 22 + birth * 16 - (birth ? 4 : 0);
}

/**
 * People are linked through small "knots": one knot per family.
 * Generations are columns, read left to right: partners point to their knot, the knot points to the children.
 */
export function layoutTree(
  tree: TreeData,
  options: LayoutOptions,
): { nodes: Node[]; edges: Edge[] } {
  const { direction, selectedId, heights, claimLabels, photoUrl } = options;
  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: direction,
    nodesep: 26,
    ranksep: 58,
    marginx: 24,
    marginy: 24,
  });
  g.setDefaultEdgeLabel(() => ({}));

  const known = new Set(tree.people.map((p) => p.id));
  const heightOf = (p: Person) => heights[`p${p.id}`] ?? guessHeight(p);
  for (const p of tree.people)
    g.setNode(`p${p.id}`, { width: PERSON_W, height: heightOf(p) });

  const edges: Edge[] = [];
  for (const f of tree.families) {
    const partners = f.partners.filter(
      (x): x is number => x != null && known.has(x),
    );
    const children = f.children.filter((c) => known.has(c.id));
    if (partners.length + children.length < 2) continue; // nothing to connect
    const knot = `f${f.id}`;
    g.setNode(knot, { width: KNOT, height: KNOT });
    for (const p of partners) {
      g.setEdge(`p${p}`, knot);
      edges.push({
        id: `${knot}-up-${p}`,
        source: `p${p}`,
        target: knot,
        type: "smoothstep",
        sourceHandle: "out",
        targetHandle: "in",
        className: f.pending ? "edge pending" : "edge",
      });
    }
    for (const c of children) {
      g.setEdge(knot, `p${c.id}`);
      edges.push({
        id: `${knot}-down-${c.id}`,
        source: knot,
        target: `p${c.id}`,
        type: "smoothstep",
        sourceHandle: "out",
        targetHandle: "in",
        className: `edge rel-${c.relation}${c.pending ? " pending" : ""}`,
      });
    }
  }

  dagre.layout(g);

  const nodes: Node[] = [];
  for (const p of tree.people) {
    const { x, y } = g.node(`p${p.id}`);
    nodes.push({
      id: `p${p.id}`,
      type: "person",
      position: { x: x - PERSON_W / 2, y: y - heightOf(p) / 2 },
      data: {
        person: p,
        selected: p.id === selectedId,
        photoUrl: photoUrl(p),
        direction,
      } satisfies PersonNodeData,
      draggable: false,
    });
  }
  for (const f of tree.families) {
    if (!g.hasNode(`f${f.id}`)) continue;
    const { x, y } = g.node(`f${f.id}`);
    nodes.push({
      id: `f${f.id}`,
      type: "knot",
      position: { x: x - KNOT / 2, y: y - KNOT / 2 },
      data: {
        unionType: f.union_type,
        pending: !!f.pending,
        direction,
      } satisfies KnotNodeData,
      draggable: false,
      selectable: false,
    });
  }

  // Relationships we know about but can't place yet: drawn, but they don't move anyone
  for (const c of tree.claims) {
    if (!known.has(c.a_id) || !known.has(c.b_id)) continue;
    edges.push({
      id: `claim-${c.id}`,
      source: `p${c.a_id}`,
      target: `p${c.b_id}`,
      type: "straight",
      sourceHandle: "side",
      targetHandle: "side-in",
      label: claimLabels[c.kind] ?? c.kind.replace(/_/g, " "),
      className: `edge claim${c.pending ? " pending" : ""}`,
    });
  }
  return { nodes, edges };
}
