import { Handle, Position, type NodeProps } from "@xyflow/react";
import { useI18n } from "./i18n";
import type { KnotNodeData, PersonNodeData } from "./layout";

export function PersonNode({ data }: NodeProps) {
  const { person, selected, photoUrl, direction } = data as PersonNodeData;
  const { t } = useI18n();
  const vertical = direction === "TB";
  const className = ["person", person.pending ? "is-pending" : "", selected ? "is-selected" : "",
    photoUrl ? "has-photo" : ""].join(" ");
  return (
    <div className={className}>
      <Handle type="target" position={vertical ? Position.Top : Position.Left} id="in" />
      <Handle type="source" position={Position.Bottom} id="side" />
      <Handle type="target" position={Position.Top} id="side-in" />
      {person.pending && <span className="person-new">{t.newTag}</span>}
      {photoUrl && <img className="person-photo" src={photoUrl} alt="" />}
      <div className="person-text">
        <div className="person-name">{person.name}</div>
        <div className="person-years">{t.cardYears(person.born, person.died)}</div>
        {person.birth_name && person.birth_name !== person.name && (
          <div className="person-birthname">{t.cardBirthName(person.birth_name, person.sex)}</div>
        )}
      </div>
      <Handle type="source" position={vertical ? Position.Bottom : Position.Right} id="out" />
    </div>
  );
}

export function KnotNode({ data }: NodeProps) {
  const { unionType, pending, direction } = data as KnotNodeData;
  const { t } = useI18n();
  const vertical = direction === "TB";
  return (
    <div className={`knot knot-${unionType}${pending ? " is-pending" : ""}`} title={t.knotTitles[unionType]}>
      <Handle type="target" position={vertical ? Position.Top : Position.Left} id="in" />
      <Handle type="source" position={vertical ? Position.Bottom : Position.Right} id="out" />
    </div>
  );
}
