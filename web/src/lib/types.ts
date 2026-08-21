export interface DocumentSummary {
  id: string;
  title: string;
  source_type: string;
  chunk_count: number;
  char_count: number;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface SourceChunk {
  chunk_id: string;
  document_id: string;
  document_title: string;
  text: string;
  score: number;
  dense_score: number;
  lexical_score: number;
  page: number | null;
  heading: string | null;
}

export interface Citation {
  marker: number;
  chunk_id: string;
  document_id: string;
  document_title: string;
  page: number | null;
  snippet: string;
}

export interface Stats {
  documents: number;
  chunks: number;
  characters: number;
  vector_store: string;
  embedding: { provider: string; model: string; dimension: number };
  llm: { model: string | null; generative: boolean };
  retrieval: {
    top_k: number;
    candidate_k: number;
    hybrid_alpha: number;
    mmr: boolean;
    strategy: string;
  };
}

export interface AskDone {
  citations: Citation[];
  latency_ms: number;
  retrieval_ms?: number;
  strategy?: string;
  grounded: boolean;
}

export type MessageRole = "user" | "assistant";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  sources?: SourceChunk[];
  citations?: Citation[];
  meta?: AskDone;
  streaming?: boolean;
  error?: string;
}

export interface UploadOutcome {
  filename: string;
  ok: boolean;
  detail?: string;
  document?: DocumentSummary;
  replaced?: boolean;
}
