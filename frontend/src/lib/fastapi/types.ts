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

// --- Analytics (backend/app/routers/insights.py) ---

export type Trend = "baseline" | "emerging" | "recurring" | "stable" | "declining";
export type RecommendationCategory = "product" | "documentation" | "faq" | "customer_issue";

export interface TopicOut {
  id: string;
  period: string;
  rank: number;
  name: string;
  keywords: string[];
  queryCount: number;
  previousQueryCount: number;
  growth: number;
  meanConfidence: number;
  severity: number;
  severityReason: string | null;
  priority: number;
  trend: Trend;
}

export interface TopicDetailOut extends TopicOut {
  history: { period: string; queryCount: number; meanConfidence: number; trend: Trend }[];
  memberQueries: { messageId: string; text: string; confidence: number | null; createdAt: string }[];
  weakestChunks: {
    chunkId: string;
    sourceLabel: string;
    headingPath: string;
    url: string | null;
    excerpt: string;
    timesRetrieved: number;
    meanSimilarity: number;
  }[];
}

export interface RecommendationOut {
  id: string;
  clusterId: string;
  clusterName: string;
  category: RecommendationCategory;
  headline: string;
  body: string;
  faqAnswer: string | null;
  supportingQueries: string[];
  volume: number;
  growth: number;
  expectedEffect: string;
}

export interface ReportSummaryOut {
  id: string;
  period: string;
  generatedAt: string;
  conversationCount: number;
  queryCount: number;
  unansweredRate: number;
}

export interface ReportOut extends ReportSummaryOut {
  summary: string;
  recommendations: RecommendationOut[];
}
