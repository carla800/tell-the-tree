import type { Lang } from "./i18n";
import type { Choices, Plan, TreeData } from "./types";

/** An error from the server, with its HTTP status so the interface can explain it in its own words. */
export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function call<T>(path: string, init?: { method?: string; body?: unknown; raw?: Blob }): Promise<T> {
  const method = init?.method ?? (init?.body === undefined && !init?.raw ? "GET" : "POST");
  const response = await fetch(`/api${path}`, {
    method,
    headers: init?.raw ? { "Content-Type": init.raw.type } : init?.body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: init?.raw ?? (init?.body !== undefined ? JSON.stringify(init.body) : undefined),
  });
  if (!response.ok) {
    let message = `The server answered ${response.status}.`;
    try {
      const detail = (await response.json()).detail;
      message = typeof detail === "string" ? detail : detail?.message ?? message;
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(message, response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => call<{ model: string; prompt: string }>("/health"),
  listTrees: () => call<string[]>("/trees"),
  createTree: (name: string) => call<{ name: string }>("/trees", { body: { name } }),
  getTree: (name: string) => call<TreeData>(`/trees/${name}`),
  parse: (name: string, sentence: string, lang: Lang) =>
    call<{ model_ops: unknown[]; seconds: number; plan: Plan }>(`/trees/${name}/parse`, { body: { sentence, lang } }),
  plan: (name: string, model_ops: unknown[], choices: Choices, lang: Lang) =>
    call<{ plan: Plan }>(`/trees/${name}/plan`, { body: { model_ops, choices, lang } }),
  apply: (name: string, sentence: string, model_ops: unknown[], choices: Choices, lang: Lang, by_hand = false) =>
    call<{ saved: string[]; tree: TreeData }>(`/trees/${name}/apply`, { body: { sentence, model_ops, choices, lang, by_hand } }),
  setPhoto: (name: string, personId: number, picture: Blob) =>
    call<{ photo: string }>(`/trees/${name}/people/${personId}/photo`, { method: "PUT", raw: picture }),
  removePhoto: (name: string, personId: number) =>
    call<{ photo: null }>(`/trees/${name}/people/${personId}/photo`, { method: "DELETE" }),
};

export const photoUrl = (tree: string, personId: number, version: string) =>
  `/api/trees/${tree}/people/${personId}/photo?v=${encodeURIComponent(version)}`;

/**
 * Makes a picture small enough for a family tree (at most 640 px on the long side, JPEG),
 * here in the browser, before it is sent: a phone photo of 5 MB becomes about 100 KB.
 */
export async function shrinkPicture(file: File): Promise<Blob> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 640 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("toBlob"))), "image/jpeg", 0.86));
}
