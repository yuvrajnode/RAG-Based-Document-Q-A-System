import type { DocumentSummary, SourceChunk, Stats, UploadOutcome } from "./types";

const BASE = "/api";

class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, init);
  if (!response.ok) {
    throw new ApiError(await readError(response), response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** FastAPI returns {detail: string} for HTTPException and a list for validation errors. */
async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  } catch {
    /* fall through to the status text */
  }
  return response.statusText || `request failed with ${response.status}`;
}

export const api = {
  stats: () => request<Stats>("/stats"),

  listDocuments: () =>
    request<{ documents: DocumentSummary[]; total_chunks: number }>("/documents"),

  deleteDocument: (id: string) => request<void>(`/documents/${id}`, { method: "DELETE" }),

  clearDocuments: () => request<void>("/documents", { method: "DELETE" }),

  search: (query: string, documentIds?: string[]) =>
    request<{ results: SourceChunk[]; strategy: string; took_ms: number }>("/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, document_ids: documentIds ?? null }),
    }),

  async upload(file: File): Promise<UploadOutcome> {
    const form = new FormData();
    form.append("file", file);
    try {
      const body = await request<{ document: DocumentSummary; replaced: boolean }>("/documents", {
        method: "POST",
        body: form,
      });
      return { filename: file.name, ok: true, document: body.document, replaced: body.replaced };
    } catch (error) {
      return {
        filename: file.name,
        ok: false,
        detail: error instanceof Error ? error.message : "upload failed",
      };
    }
  },
};

export interface StreamHandlers {
  onSources: (sources: SourceChunk[]) => void;
  onDelta: (text: string) => void;
  onDone: (payload: unknown) => void;
  onError: (message: string) => void;
}

export interface AskPayload {
  question: string;
  documentIds?: string[];
  history?: { role: "user" | "assistant"; content: string }[];
  signal?: AbortSignal;
}

/**
 * Reads the SSE response by hand rather than using EventSource, which only
 * speaks GET and cannot send the question body. Events are separated by a
 * blank line; a partial event at the end of a chunk stays in the buffer until
 * the rest of it arrives.
 */
export async function askStream(payload: AskPayload, handlers: StreamHandlers): Promise<void> {
  const response = await fetch(`${BASE}/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal: payload.signal,
    body: JSON.stringify({
      question: payload.question,
      document_ids: payload.documentIds?.length ? payload.documentIds : null,
      history: payload.history?.length ? payload.history : null,
    }),
  });

  if (!response.ok || !response.body) {
    handlers.onError(await readError(response));
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      dispatch(buffer.slice(0, boundary), handlers);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
  }
  if (buffer.trim()) dispatch(buffer, handlers);
}

function dispatch(raw: string, handlers: StreamHandlers): void {
  let event = "message";
  const dataLines: string[] = [];

  for (const line of raw.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice(7).trim();
    else if (line.startsWith("data: ")) dataLines.push(line.slice(6));
  }
  if (!dataLines.length) return;

  let data: unknown;
  try {
    data = JSON.parse(dataLines.join("\n"));
  } catch {
    return;
  }

  switch (event) {
    case "sources":
      handlers.onSources(data as SourceChunk[]);
      break;
    case "delta":
      handlers.onDelta(String(data));
      break;
    case "done":
      handlers.onDone(data);
      break;
    case "error":
      handlers.onError(String(data));
      break;
  }
}
