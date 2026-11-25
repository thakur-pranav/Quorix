import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { formatGrowth, TrendBadge } from "@/components/insights/trend-badge";
import { Alert, Card } from "@/components/ui/card";
import { BackendError, fastapi } from "@/lib/fastapi/client";
import type { TopicDetailOut } from "@/lib/fastapi/types";
import { formatPercent } from "@/lib/utils";
import { topicIdSchema } from "@/lib/validations/intelligence";

export const metadata: Metadata = { title: "Topic" };

export default async function InsightDetailPage({ params }: { params: Promise<{ insightId: string }> }) {
  const parsed = topicIdSchema.safeParse((await params).insightId);
  if (!parsed.success) notFound();

  let topic: TopicDetailOut;
  try {
    topic = await fastapi<TopicDetailOut>(`/insights/${parsed.data}`);
  } catch (e) {
    if (e instanceof BackendError && e.status === 404) notFound(); // includes another org's topic
    if (e instanceof BackendError) return <Alert>{e.message}</Alert>;
    throw e;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/insights" className="text-sm text-primary hover:underline">
          ← All topics
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h1 className="text-[28px] font-medium tracking-tight">{topic.name}</h1>
          <TrendBadge trend={topic.trend} />
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {topic.keywords.map((k) => (
            <span key={k} className="rounded-full bg-surface-3 px-2.5 py-0.5 text-xs text-ink-muted">
              {k}
            </span>
          ))}
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Metric label="Rank" value={`#${topic.rank}`} />
        <Metric label="Questions" value={`${topic.queryCount}`} sub={formatGrowth(topic.growth, topic.previousQueryCount)} />
        <Metric label="Mean confidence" value={formatPercent(topic.meanConfidence)} />
        <Metric label="Severity" value={topic.severity.toFixed(2)} />
        <Metric label="Priority" value={topic.priority.toFixed(2)} />
      </dl>

      {topic.severityReason && (
        <p className="text-sm text-ink-muted">
          <span className="font-medium text-ink">Why this severity: </span>
          {topic.severityReason}
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="font-medium">History</h2>
          <table className="mt-3 w-full text-sm">
            <thead className="text-left text-xs text-ink-muted">
              <tr>
                <th className="pb-2 font-normal">Month</th>
                <th className="pb-2 font-normal">Questions</th>
                <th className="pb-2 font-normal">Confidence</th>
                <th className="pb-2 font-normal">Trend</th>
              </tr>
            </thead>
            <tbody>
              {topic.history.map((h) => (
                <tr key={h.period} className="border-t border-outline-soft/50">
                  <td className="py-2">{h.period}</td>
                  <td className="py-2 font-medium">{h.queryCount}</td>
                  <td className="py-2">{formatPercent(h.meanConfidence)}</td>
                  <td className="py-2">
                    <TrendBadge trend={h.trend} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        <Card>
          <h2 className="font-medium">Pages to improve</h2>
          <p className="text-sm text-ink-muted">The passages these questions landed on, weakest match first.</p>
          {topic.weakestChunks.length === 0 ? (
            <p className="mt-3 text-sm text-ink-muted">No passages were retrieved for these questions.</p>
          ) : (
            <ul className="mt-3 flex flex-col gap-3">
              {topic.weakestChunks.map((c) => (
                <li key={c.chunkId} className="text-sm">
                  <p className="font-medium">
                    {c.url ? (
                      <a href={c.url} target="_blank" rel="noreferrer noopener" className="text-primary hover:underline">
                        {c.headingPath}
                      </a>
                    ) : (
                      c.headingPath
                    )}
                  </p>
                  <p className="text-xs text-ink-muted">
                    {c.sourceLabel} · retrieved {c.timesRetrieved}× · {formatPercent(c.meanSimilarity)} average match
                  </p>
                  <p className="mt-1 line-clamp-2 text-ink-muted">{c.excerpt}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card>
        <h2 className="font-medium">What customers asked</h2>
        <p className="text-sm text-ink-muted">Lowest confidence first: these are the ones the docs answered worst.</p>
        <ul className="mt-3 divide-y divide-outline-soft/50">
          {topic.memberQueries.map((q) => (
            <li key={q.messageId} className="flex items-start justify-between gap-4 py-2 text-sm">
              <span>{q.text}</span>
              <span className="shrink-0 text-xs text-ink-muted">{q.confidence === null ? "–" : formatPercent(q.confidence)}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-card bg-surface-2 px-4 py-3">
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className="mt-0.5 text-xl font-medium">
        {value}
        {sub && <span className="ml-1.5 text-xs font-normal text-ink-muted">{sub}</span>}
      </dd>
    </div>
  );
}
