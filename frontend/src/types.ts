export type Sex = "F" | "M" | "U";

export interface TreeEvent {
  id: number;
  type: string;
  person_id: number | null;
  family_id: number | null;
  date_text: string | null;
  place: string | null;
  description: string | null;
  source: string | null;
}

export interface Person {
  id: number;
  name: string;
  birth_name: string | null;
  also_known_as: string | null;
  sex: Sex;
  notes: string | null;
  born: number | null;
  died: number | null;
  events: TreeEvent[];
  pending?: boolean;
}

export interface ChildLink {
  id: number;
  relation: string;
  pending?: boolean;
}

export interface Family {
  id: number;
  partners: (number | null)[];
  union_type: string;
  children: ChildLink[];
  events: TreeEvent[];
  pending?: boolean;
}

export interface Claim {
  id: number;
  a_id: number;
  b_id: number;
  kind: string;
  sentence: string | null;
  pending?: boolean;
}

export interface TreeData {
  people: Person[];
  families: Family[];
  claims: Claim[];
}

export interface PersonQuestion {
  kind: "person";
  name: string;
  candidates: { id: number; name: string; born: number | null }[];
}

export interface MeaningQuestion {
  kind: "meaning";
  word: string;
  person: string;
  of: string[];
  options: string[];
}

export type Question = PersonQuestion | MeaningQuestion;

// One change the sentence would make. New people and families have negative ids.
export type Change = { action: string } & Record<string, unknown>;

export interface Plan {
  status: "save" | "ask" | "reject";
  changes: Change[];
  summary: string[];
  known: string[];
  questions: Question[];
  errors: string[];
  warnings: string[];
}

export type Choices = Record<string, number | string>;
