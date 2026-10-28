import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ReactFlow, Background, Controls, useReactFlow, type Edge, type Node, type NodeChange, type NodeMouseHandler } from "@xyflow/react";
import { photoUrl } from "./api";
import { useI18n } from "./i18n";
import { layoutTree } from "./layout";
import { KnotNode, PersonNode } from "./nodes";
import type { TreeData } from "./types";

const nodeTypes = { person: PersonNode, knot: KnotNode };

/** What a preview changes: the pending nodes, and the parents above any knot they hang from. */
function previewArea(nodes: Node[], edges: Edge[]): string[] {
  const area = new Set(nodes.filter((n) => {
    const d = n.data as { person?: { pending?: boolean }; pending?: boolean };
    return d.person?.pending || d.pending;
  }).map((n) => n.id));
  for (const e of edges) if (String(e.className).includes("pending")) { area.add(e.source); area.add(e.target); }
  for (const e of edges) if (e.target.startsWith("f") && area.has(e.target)) area.add(e.source);
  return [...area];
}

const reduceMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

interface Props {
  tree: TreeData;
  treeName: string;
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  fitKey: string;          // changes when the view should re-centre (new tree, new preview)
}

const wide = () => window.matchMedia("(min-width: 821px)").matches;

function Legend() {
  const { t } = useI18n();
  return (
    <details className="legend" open={wide()}>
      <summary>{t.legendTitle}</summary>
      <div className="legend-keys">
        <span><i className="key-line" /> {t.keyChild}</span>
        <span><i className="key-line key-step" /> {t.keyStepchild}</span>
        <span><i className="key-line key-adopted" /> {t.keyAdopted}</span>
        <span><i className="key-knot" /> {t.keyMarried}</span>
        <span><i className="key-knot key-partners" /> {t.keyNotMarried}</span>
        <span><i className="key-knot key-unknown" /> {t.keyParents}</span>
      </div>
    </details>
  );
}

export function TreeView({ tree, treeName, selectedId, onSelect, fitKey }: Props) {
  const { t } = useI18n();
  // Cards grow with long names, so the layout uses each card's real height once it has been drawn
  const [heights, setHeights] = useState<Record<string, number>>({});
  const { nodes, edges } = useMemo(() => layoutTree(tree, {
    selectedId, heights, claimLabels: t.claims,
    photoUrl: (p) => (p.photo && p.id > 0 ? photoUrl(treeName, p.id, p.photo) : null),
  }), [tree, treeName, selectedId, heights, t]);
  const flow = useReactFlow();

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    const measured: Record<string, number> = {};
    for (const c of changes) {
      if (c.type === "dimensions" && c.dimensions && c.id.startsWith("p")) measured[c.id] = Math.ceil(c.dimensions.height);
    }
    setHeights((h) => (Object.entries(measured).some(([id, v]) => h[id] !== v) ? { ...h, ...measured } : h));
  }, []);
  const measuredCount = Object.keys(heights).length;

  const latest = useRef({ nodes, edges });
  latest.current = { nodes, edges };

  // A new tree: show all of it. A preview: move to where the change would land.
  useEffect(() => {
    const timer = setTimeout(() => {
      const focus = previewArea(latest.current.nodes, latest.current.edges);
      const duration = reduceMotion() ? 0 : 450;
      if (focus.length) flow.fitView({ nodes: focus.map((id) => ({ id })), padding: { top: "48px", right: "48px", bottom: "84px", left: "48px" }, maxZoom: 1, duration });
      else flow.fitView({ padding: { top: "20px", right: "24px", bottom: "64px", left: "24px" }, maxZoom: 1, duration });
    }, 60);
    return () => clearTimeout(timer);
  }, [fitKey, measuredCount, flow]);

  const onNodeClick: NodeMouseHandler = (_, node) => {
    if (node.type === "person") onSelect(Number(node.id.slice(1)));
  };

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodesChange={onNodesChange}
      onNodeClick={onNodeClick}
      onPaneClick={() => onSelect(null)}
      nodesConnectable={false}
      nodesDraggable={false}
      fitView
      minZoom={0.2}
      maxZoom={1.6}
      proOptions={{ hideAttribution: false }}
    >
      <Background gap={28} size={1} className="tree-paper" />
      <Controls showInteractive={false} />
      {tree.people.length > 1 && <Legend />}
    </ReactFlow>
  );
}
