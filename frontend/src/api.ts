import type { Choices, Plan, TreeData } from "./types";

async function call<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let message = `The server answered ${response.status}.`;
    try {
      const data = await response.json();
      const detail = data.detail;
      message = typeof detail === "string" ? detail : detail?.message ?? message;
    } catch {
      /* keep the generic message */
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => call<{ model: string; prompt: string }>("/health"),
  listTrees: () => call<string[]>("/trees"),
  createTree: (name: string) => call<{ name: string }>("/trees", { name }),
  getTree: (name: string) => call<TreeData>(`/trees/${name}`),
  parse: (name: string, sentence: string) =>
    call<{ model_ops: unknown[]; seconds: number; plan: Plan }>(`/trees/${name}/parse`, { sentence }),
  plan: (name: string, model_ops: unknown[], choices: Choices) =>
    call<{ plan: Plan }>(`/trees/${name}/plan`, { model_ops, choices }),
  apply: (name: string, sentence: string, model_ops: unknown[], choices: Choices) =>
    call<{ saved: string[]; tree: TreeData }>(`/trees/${name}/apply`, { sentence, model_ops, choices }),
};
