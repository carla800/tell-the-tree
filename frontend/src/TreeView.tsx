import {
  Background,
  Controls,
  ReactFlow,
  useReactFlow,
  type Edge,
  type Node,
  type NodeChange,
  type NodeMouseHandler,
} from "@xyflow/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { photoUrl } from "./api";
import { useI18n } from "./i18n";
import { layoutTree, type TreeDirection } from "./layout";
import { KnotNode, PersonNode } from "./nodes";
import type { TreeData } from "./types";

const nodeTypes = { person: PersonNode, knot: KnotNode };

// Collegamenti sobri e meno marcati, senza alterare i tipi di parentela.
const defaultEdgeOptions = { style: { strokeWidth: 1.15 } };

/** What a preview changes: the pending nodes, and the parents above any knot they hang from. */
function previewArea(nodes: Node[], edges: Edge[]): string[] {
  const area = new Set(
    nodes
      .filter((n) => {
        const d = n.data as {
          person?: { pending?: boolean };
          pending?: boolean;
        };
        return d.person?.pending || d.pending;
      })
      .map((n) => n.id),
  );
  for (const e of edges)
    if (String(e.className).includes("pending")) {
      area.add(e.source);
      area.add(e.target);
    }
  for (const e of edges)
    if (e.target.startsWith("f") && area.has(e.target)) area.add(e.source);
  return [...area];
}

const reduceMotion = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

interface Props {
  tree: TreeData;
  treeName: string;
  direction: TreeDirection;
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  fitKey: string; // changes when the view should re-centre (new tree, new preview)
  focus: { id: number; at: number } | null; // a person found with the search
  printing: boolean;
  onReadyToPrint: () => void;
}

const wide = () => window.matchMedia("(min-width: 821px)").matches;

function Legend() {
  const { t } = useI18n();
  return (
    <details className="legend" open={wide()}>
      <summary>{t.legendTitle}</summary>
      <div className="legend-keys">
        <span>
          <i className="key-line" /> {t.keyChild}
        </span>
        <span>
          <i className="key-line key-step" /> {t.keyStepchild}
        </span>
        <span>
          <i className="key-line key-adopted" /> {t.keyAdopted}
        </span>
        <span>
          <i className="key-knot" /> {t.keyMarried}
        </span>
        <span>
          <i className="key-knot key-partners" /> {t.keyNotMarried}
        </span>
        <span>
          <i className="key-knot key-unknown" /> {t.keyParents}
        </span>
      </div>
    </details>
  );
}

export function TreeView({
  tree,
  treeName,
  direction,
  selectedId,
  onSelect,
  fitKey,
  focus,
  printing,
  onReadyToPrint,
}: Props) {
  const { t } = useI18n();
  // Cards grow with long names, so the layout uses each card's real height once it has been drawn
  const [heights, setHeights] = useState<Record<string, number>>({});
  const { nodes, edges } = useMemo(
    () =>
      layoutTree(tree, {
        direction,
        selectedId,
        heights,
        claimLabels: t.claims,
        photoUrl: (p) =>
          p.photo && p.id > 0 ? photoUrl(treeName, p.id, p.photo) : null,
      }),
    [tree, treeName, direction, selectedId, heights, t],
  );
  const flow = useReactFlow();

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    const measured: Record<string, number> = {};
    for (const c of changes) {
      if (c.type === "dimensions" && c.dimensions && c.id.startsWith("p"))
        measured[c.id] = Math.ceil(c.dimensions.height);
    }
    setHeights((h) =>
      Object.entries(measured).some(([id, v]) => h[id] !== v)
        ? { ...h, ...measured }
        : h,
    );
  }, []);
  const measuredCount = Object.keys(heights).length;

  const latest = useRef({ nodes, edges });
  latest.current = { nodes, edges };

  // A new tree: show all of it. A preview: move to where the change would land.
  useEffect(() => {
    const timer = setTimeout(() => {
      const focus = previewArea(latest.current.nodes, latest.current.edges);
      const duration = reduceMotion() ? 0 : 450;
      if (focus.length)
        flow.fitView({
          nodes: focus.map((id) => ({ id })),
          padding: { top: "48px", right: "48px", bottom: "84px", left: "48px" },
          maxZoom: 1,
          duration,
        });
      else
        flow.fitView({
          padding: { top: "20px", right: "24px", bottom: "64px", left: "24px" },
          maxZoom: 1,
          duration,
        });
    }, 60);
    return () => clearTimeout(timer);
  }, [fitKey, direction, measuredCount, flow]);

  // A person found with the search: move to them (a click on a card doesn't move the view)
  useEffect(() => {
    if (!focus) return;
    const node = latest.current.nodes.find((n) => n.id === `p${focus.id}`);
    if (!node) return;
    const width = node.measured?.width ?? 196;
    const height = node.measured?.height ?? 74;
    void flow.setCenter(node.position.x + width / 2, node.position.y + height / 2, {
      zoom: Math.max(flow.getZoom(), 0.9), duration: reduceMotion() ? 0 : 400,
    });
  }, [focus, flow]);

  // Printing: the canvas has taken the page's shape; fit the whole tree in it, then print
  const ready = useRef(onReadyToPrint);
  ready.current = onReadyToPrint;
  useEffect(() => {
    if (!printing) return;
    const timer = setTimeout(() => {
      // room for the title above and the key below
      void flow.fitView({ padding: { top: "48px", right: "12px", bottom: "56px", left: "12px" }, duration: 0 })
        .then(() => requestAnimationFrame(() => ready.current()));
    }, 150);
    return () => clearTimeout(timer);
  }, [printing, flow]);

  const onNodeClick: NodeMouseHandler = (_, node) => {
    if (node.type === "person") onSelect(Number(node.id.slice(1)));
  };

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      defaultEdgeOptions={defaultEdgeOptions}
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
