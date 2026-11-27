import type { Metadata } from "next";
import Link from "next/link";

import { BackendProblem } from "@/components/layout/backend-problem";
import { ColumnChart } from "@/components/charts/column-chart";
import { StatTile } from "@/components/charts/stat-tile";
import { STRONG_MATCH } from "@/components/chat/confidence-meter";
import { Card } from "@/components/ui/card";
import { BackendError, fastapi } from "@/lib/fastapi/client";
import type { OverviewOut } from "@/lib/fastapi/types";
import { countDelta, histogramColumns, pointsDelta } from "@/lib/overview";
import { formatPercent } from "@/lib/utils";

export const metadata: Metadata = { title: "Overview" };

export default async function OverviewPage() {
  let data: OverviewOut | null = null;
  let error: BackendError | null = null;
  try {
    data = await fastapi<OverviewOut>("/overview");
  } catch (e) {
    if (!(e instanceof BackendError)) throw e;
    error = e;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[28px] font-medium tracking-tight">Overview</h1>
        <p className="mt-1 text-ink-muted">
          {data?.period ? `How customers' questions went in ${data.period}.` : "How customers' questions are going."}
        </p>
      </div>

      {error && <BackendProblem error={error} />}
      {data && !data.period && (
        <p className="rounded-card border border-dashed border-outline-soft px-5 py-10 text-center text-ink-muted">
          No questions yet. <Link href="/sources" className="text-primary underline">Add your docs</Link>, then{" "}
          <Link href="/ask" className="text-primary underline">ask something</Link>.
        </p>
      )}
      {data?.period && <OverviewBody data={data} />}
    </div>
  );
}

function OverviewBody({ data }: { data: OverviewOut }) {
  const months = data.volumeByPeriod;
  const previous = months.length > 1 ? months[months.length - 2] : undefined;
  const threshold = data.lowConfidenceThreshold;
  const questionsDelta = countDelta(data.queryCount, previous?.queryCount);
  const confidenceDelta = pointsDelta(data.meanConfidence, previous?.meanConfidence);

  return (
    <>
      <dl className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        <StatTile
          label="Questions this month"
          value={data.queryCount.toLocaleString()}
          delta={questionsDelta ? { ...questionsDelta, good: "neither" } : undefined}
        />
        <StatTile label="Conversations" value={data.conversationCount.toLocaleString()} />
        <StatTile
          label="Weak doc match"
          value={formatPercent(data.unansweredRate)}
          note={`questions below the ${threshold.toFixed(2)} threshold`}
        />
        <StatTile
          label="Mean confidence"
          value={data.meanConfidence.toFixed(2)}
          delta={confidenceDelta ? { ...confidenceDelta, good: "up" } : undefined}
        />
      </dl>

      <div className="grid gap-4 lg:grid-cols-[2fr_3fr]">
        <Card>
          <h2 className="font-medium">Questions per month</h2>
          <p className="mb-8 mt-1 text-sm text-ink-muted">Customer questions logged by the assistant.</p>
          <ColumnChart
            title="Questions per month"
            valueLabel="Questions"
            highlightKey={data.period ?? undefined}
            columns={months.map((m) => ({
              key: m.period,
              label: m.period,
              value: m.queryCount,
              tooltip: `${m.period}: ${m.queryCount} questions, mean confidence ${m.meanConfidence.toFixed(2)}`,
            }))}
          />
        </Card>

        <Card>
          <h2 className="font-medium">How well the docs matched, {data.period}</h2>
          <p className="mb-8 mt-1 text-sm text-ink-muted">
            Questions by retrieval confidence. Below {threshold.toFixed(2)} the assistant says it couldn&apos;t find it;
            from {STRONG_MATCH.toFixed(2)} it&apos;s a strong match.
          </p>
          <ColumnChart
            title={`Questions by retrieval confidence, ${data.period}`}
            valueLabel="Questions"
            dense
            columns={histogramColumns(data.confidenceHistogram)}
            markers={[
              { at: threshold, label: `Refused below ${threshold.toFixed(2)}`, side: "left" },
              { at: STRONG_MATCH, label: `Strong ${STRONG_MATCH.toFixed(2)}+`, side: "right" },
            ]}
            xTicks={[0, 0.25, 0.5, 0.75, 1].map((t) => ({ at: t, label: t.toFixed(2) }))}
          />
        </Card>
      </div>

      <Card className="flex flex-wrap items-center justify-between gap-3">
        <p>
          <span className="font-medium">{data.topicCount} topics</span> this month,{" "}
          <span className="font-medium">{data.emergingCount} emerging</span>.
        </p>
        <Link href="/insights" className="text-sm font-medium text-primary hover:underline">
          See the topics →
        </Link>
      </Card>
    </>
  );
}
