/** Response shapes of the FastAPI backend (backend/app/schemas.py). camelCase on the wire. */

export type SourceStatus = "queued" | "crawling" | "indexing" | "ready" | "failed";
export type SourceKind = "website" | "pdf" | "docx" | "text";

export interface SourceOut {
  id: string;
  kind: SourceKind;
  label: string;
  location: string;
  status: SourceStatus;
  pageCount: number;
  chunkCount: number;
  lastIndexedAt: string | null;
  error: string | null;
  createdAt: string;
}

export interface Citation {
  chunkId: string;
  sourceLabel: string;
  headingPath: string;
  similarity: number;
  excerpt: string;
}

export interface ChatResponse {
  id: string;
  role: "assistant";
  text: string;
  createdAt: string;
  confidence: number;
  lowConfidence: boolean;
  citations: Citation[];
}

/** What every server action returns: never throws to the browser. */
export type ActionResult<T> = { success: true; data: T } | { success: false; error: string };
