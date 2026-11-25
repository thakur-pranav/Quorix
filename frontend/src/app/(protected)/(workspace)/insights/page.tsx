import type { Metadata } from "next";
import Link from "next/link";

import { formatGrowth, TrendBadge } from "@/components/insights/trend-badge";
import { RunAnalysisButton } from "@/components/insights/run-analysis-button";
import { Alert } from "@/components/ui/card";
import { BackendError, fastapi } from "@/lib/fastapi/client";
import type { TopicOut } from "@/lib/fastapi/types";
import { formatPercent } from "@/lib/utils";

export const metadata: Metadata = { title: "Insights" };

export default async function InsightsPage() {
  let topics: TopicOut[] = [];
  let error: string | null = null;
  try {
    topics = await fastapi<TopicOut[]>("/insights");
  } catch (e) {
    if (!(e instanceof BackendError)) throw e;
    error = e.message;
  }
  const period = topics[0]?.period;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[28px] font-medium tracking-tight">Insights</h1>
          <p className="mt-1 text-ink-muted">
            {period ? `What customers asked about in ${period}, highest priority first.` : "Topics your customers ask about, ranked by priority."}
          </p>
        </div>
        <RunAnalysisButton />
      </div>

      {error && <Alert>{error}</Alert>}
      {!error && topics.length === 0 && (
        <p className="rounded-card border border-dashed border-outline-soft px-5 py-10 text-center text-ink-muted">
          No topics yet. Once customers have asked enough questions, run the analysis.
        </p>
      )}

      <ol className="flex flex-col gap-2">
        {topics.map((topic) => (
          <li key={topic.id}>
            <Link
              href={`/insights/${topic.id}`}
              className="grid grid-cols-[2rem_1fr] gap-x-3 gap-y-2 rounded-card bg-surface-2 p-4 transition-colors hover:bg-surface-3 sm:grid-cols-[2rem_1fr_auto]"
            >
              <span className="pt-0.5 text-lg font-medium text-ink-muted">{topic.rank}</span>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-medium">{topic.name}</h2>
                  <TrendBadge trend={topic.trend} />
                </div>
                <p className="mt-1 truncate text-sm text-ink-muted">{topic.keywords.join(" · ")}</p>
              </div>
              <dl className="col-start-2 flex gap-5 text-sm sm:col-start-3 sm:row-start-1 sm:text-right">
                <Stat label="Questions" value={`${topic.queryCount}`} sub={formatGrowth(topic.growth, topic.previousQueryCount)} />
                <Stat label="Confidence" value={formatPercent(topic.meanConfidence)} />
                <Stat label="Priority" value={topic.priority.toFixed(2)} />
              </dl>
            </Link>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className="font-medium">
        {value}
        {sub && <span className="ml-1 text-xs font-normal text-ink-muted">{sub}</span>}
      </dd>
    </div>
  );
}
