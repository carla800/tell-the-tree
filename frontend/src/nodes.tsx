import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { KnotNodeData, PersonNodeData } from "./layout";

function years(born: number | null, died: number | null): string {
  if (born && died) return `${born}–${died}`;
  if (born) return `born ${born}`;
  if (died) return `died ${died}`;
  return "";
}

export function PersonNode({ data }: NodeProps) {
  const { person, selected } = data as PersonNodeData;
  const className = ["person", person.pending ? "is-pending" : "", selected ? "is-selected" : ""].join(" ");
  return (
    <div className={className}>
      <Handle type="target" position={Position.Left} id="in" />
      <Handle type="source" position={Position.Bottom} id="side" />
      <Handle type="target" position={Position.Top} id="side-in" />
      {person.pending && <span className="person-new">new</span>}
      <div className="person-name">{person.name}</div>
      <div className="person-years">{years(person.born, person.died)}</div>
      {person.birth_name && person.birth_name !== person.name && (
        <div className="person-birthname">born {person.birth_name}</div>
      )}
      <Handle type="source" position={Position.Right} id="out" />
    </div>
  );
}

const KNOT_TITLE: Record<string, string> = {
  marriage: "Married",
  partnership: "Partners, not married",
  unknown: "Parents",
};

export function KnotNode({ data }: NodeProps) {
  const { unionType, pending } = data as KnotNodeData;
  return (
    <div className={`knot knot-${unionType}${pending ? " is-pending" : ""}`} title={KNOT_TITLE[unionType]}>
      <Handle type="target" position={Position.Left} id="in" />
      <Handle type="source" position={Position.Right} id="out" />
    </div>
  );
}
