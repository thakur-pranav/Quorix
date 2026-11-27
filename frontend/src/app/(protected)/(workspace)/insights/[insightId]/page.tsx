import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, MessageSquare } from "lucide-react";

import { InsightEvidence } from "@/components/insights/InsightEvidence";
import { InsightHistoryChart } from "@/components/insights/InsightHistoryChart";
import { InsightTrendBadge } from "@/components/insights/InsightTrendBadge";
import { MemberQueriesList } from "@/components/insights/MemberQueriesList";
import { BackendProblem } from "@/components/layout/backend-problem";
import { BackendError, fastapi } from "@/lib/fastapi/client";
import type { TopicDetailOut } from "@/lib/fastapi/types";
import { formatNumber, formatPercent, formatTopicGrowth } from "@/lib/formatters";
import { topicIdSchema } from "@/lib/validations/intelligence";

export const metadata: Metadata = { title: "Topic" };

const SAMPLE_QUESTIONS = 4;

export default async function InsightDetailPage({ params }: { params: Promise<{ insightId: string }> }) {
  const parsed = topicIdSchema.safeParse((await params).insightId);
  if (!parsed.success) notFound();

  let insight: TopicDetailOut;
  try {
    insight = await fastapi<TopicDetailOut>(`/insights/${parsed.data}`);
  } catch (e) {
    if (e instanceof BackendError && e.status === 404) notFound(); // includes another org's topic
    if (e instanceof BackendError) return <BackendProblem error={e} />;
    throw e;
  }
  const samples = insight.memberQueries.slice(0, SAMPLE_QUESTIONS);
  const metrics: [string, string][] = [
    [formatNumber(insight.queryCount), `Queries (${formatTopicGrowth(insight.growth, insight.previousQueryCount)})`],
    [formatPercent(insight.meanConfidence), "Mean Confidence"],
    [insight.priority.toFixed(2), "Priority Score"],
    [insight.severity.toFixed(2), "Severity Index"],
  ];

  return (
    <div className="space-y-8">
      {/* Navigation & Header */}
      <div>
        <Link
          href="/insights"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-[#6750A4] dark:text-slate-400"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Insights
        </Link>

        <div className="mt-3 flex flex-col gap-4 border-b border-slate-200/60 pb-5 sm:flex-row sm:items-center sm:justify-between dark:border-zinc-800">
          <div>
            <div className="flex items-center gap-3">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#E8DEF8] text-xs font-bold text-[#6750A4] dark:bg-purple-950/60 dark:text-purple-300">
                #{insight.rank}
              </span>
              <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl dark:text-white">{insight.name}</h1>
            </div>
            {insight.keywords.length > 0 && (
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {insight.keywords.map((kw) => (
                  <span key={kw} className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-zinc-800 dark:text-slate-300">
                    {kw}
                  </span>
                ))}
              </div>
            )}
            {insight.severityReason && (
              <p className="mt-3 max-w-3xl text-sm text-slate-600 dark:text-slate-400">
                <span className="font-semibold text-slate-800 dark:text-slate-200">Why this severity: </span>
                {insight.severityReason}
              </p>
            )}
          </div>
          <InsightTrendBadge trend={insight.trend} />
        </div>
      </div>

      {/* Metrics Row */}
      <section className="grid grid-cols-2 gap-4 sm:grid-cols-4" aria-labelledby="detail-metrics-heading">
        <h2 id="detail-metrics-heading" className="sr-only">
          Topic Metrics
        </h2>
        {metrics.map(([value, label]) => (
          <div key={label} className="rounded-2xl border border-slate-200/70 bg-[#F3EDF7]/40 p-4 text-center dark:border-zinc-800 dark:bg-zinc-900/40">
            <span className="block text-2xl font-bold text-slate-900 dark:text-white">{value}</span>
            <span className="mt-0.5 block text-xs text-slate-500">{label}</span>
          </div>
        ))}
      </section>

      {/* History and Sample Questions */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <InsightHistoryChart history={insight.history} />

        <div className="rounded-3xl border border-slate-200/70 bg-[#F3EDF7]/30 p-5 dark:border-zinc-800 dark:bg-zinc-900/30">
          <h4 className="text-sm font-semibold text-slate-900 dark:text-white">Sample Questions</h4>
          <p className="text-xs text-slate-500 dark:text-slate-400">The ones the docs answered worst</p>
          <div className="mt-4 space-y-2.5">
            {samples.length > 0 ? (
              samples.map((query) => (
                <div
                  key={query.messageId}
                  className="flex items-start gap-2.5 rounded-2xl bg-white/70 p-3 text-xs italic text-slate-700 dark:bg-zinc-800/60 dark:text-slate-300"
                >
                  <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-[#6750A4]" />
                  <span>&ldquo;{query.text}&rdquo;</span>
                </div>
              ))
            ) : (
              <p className="text-xs text-slate-500">No sample queries available.</p>
            )}
          </div>
        </div>
      </section>

      {/* Customer Inquiries Evidence */}
      <section className="space-y-3">
        <div>
          <h3 className="text-base font-semibold text-slate-900 dark:text-white">
            Customer Questions ({insight.memberQueries.length})
          </h3>
          <p className="text-xs text-slate-500">Real questions grouped into this topic, lowest confidence first</p>
        </div>
        <MemberQueriesList queries={insight.memberQueries} />
      </section>

      {/* Weakest Knowledge Matches Evidence */}
      <section className="space-y-3">
        <div>
          <h3 className="text-base font-semibold text-slate-900 dark:text-white">Weakest Knowledge Matches</h3>
          <p className="text-xs text-slate-500">
            The doc sections this topic&apos;s questions landed on, worst match first: the pages to improve
          </p>
        </div>
        <InsightEvidence weakestChunks={insight.weakestChunks} />
      </section>
    </div>
  );
}
