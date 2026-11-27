import type { Metadata } from "next";

import { STRONG_MATCH } from "@/components/chat/ConfidenceMeter";
import { BackendProblem } from "@/components/layout/backend-problem";
import { ActivityChart } from "@/components/overview/ActivityChart";
import { AnalyticsRunControl } from "@/components/overview/AnalyticsRunControl";
import { ConfidenceChart } from "@/components/overview/ConfidenceChart";
import { ConfidenceDistributionChart } from "@/components/overview/ConfidenceDistributionChart";
import { OverviewMetricGrid } from "@/components/overview/OverviewMetricGrid";
import { EmptyState } from "@/components/shared/EmptyState";
import { PageHeader } from "@/components/shared/PageHeader";
import { requireUser } from "@/lib/auth";
import { BackendError, fastapi } from "@/lib/fastapi/client";
import type { OverviewOut } from "@/lib/fastapi/types";
import { isReadOnlyOrg } from "@/lib/read-only";

export const metadata: Metadata = { title: "Overview" };

export default async function OverviewPage() {
  const readOnly = isReadOnlyOrg((await requireUser()).organizationId);
  let overviewData: OverviewOut | null = null;
  let error: BackendError | null = null;
  try {
    overviewData = await fastapi<OverviewOut>("/overview");
  } catch (e) {
    if (!(e instanceof BackendError)) throw e;
    error = e;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="This period"
        period={overviewData?.period}
        description="Customer conversation health and the topics gaining attention."
        actions={readOnly ? undefined : <AnalyticsRunControl />}
      />

      {error ? (
        <BackendProblem error={error} />
      ) : overviewData && !overviewData.period ? (
        <EmptyState
          title="No questions yet."
          description="Add your docs on the Sources page, then ask something: activity shows up here."
        />
      ) : overviewData ? (
        <>
          {/* Key Metrics */}
          <section aria-labelledby="kpi-heading">
            <h2 id="kpi-heading" className="sr-only">
              Key Performance Indicators
            </h2>
            <OverviewMetricGrid data={overviewData} />
          </section>

          {/* Activity Visualizations */}
          <section className="grid grid-cols-1 gap-6 lg:grid-cols-2" aria-labelledby="charts-heading">
            <h2 id="charts-heading" className="sr-only">
              Activity and Confidence Charts
            </h2>
            <ActivityChart data={overviewData.volumeByPeriod} />
            <ConfidenceChart data={overviewData.volumeByPeriod} />
          </section>

          <ConfidenceDistributionChart
            bins={overviewData.confidenceHistogram}
            threshold={overviewData.lowConfidenceThreshold}
            strongMatch={STRONG_MATCH}
            period={overviewData.period ?? ""}
          />

          {/* At a glance summary */}
          <section className="rounded-3xl border border-slate-200/70 bg-[#F3EDF7]/30 p-6 dark:border-zinc-800 dark:bg-zinc-900/30">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">At a glance</h3>
            <div className="mt-3 grid grid-cols-1 gap-4 text-xs text-slate-600 sm:grid-cols-3 dark:text-slate-400">
              <div className="rounded-2xl bg-white/70 p-4 dark:bg-zinc-800/60">
                <span className="font-semibold text-slate-800 dark:text-slate-200">Topic Breadth:</span>{" "}
                {overviewData.topicCount} customer themes identified across {overviewData.conversationCount} total
                sessions.
              </div>
              <div className="rounded-2xl bg-white/70 p-4 dark:bg-zinc-800/60">
                <span className="font-semibold text-slate-800 dark:text-slate-200">Documentation Gaps:</span>{" "}
                {Math.round(overviewData.unansweredRate * 100)}% of queries lacked strong knowledge matches.
              </div>
              <div className="rounded-2xl bg-white/70 p-4 dark:bg-zinc-800/60">
                <span className="font-semibold text-slate-800 dark:text-slate-200">Emerging Volume:</span>{" "}
                {overviewData.emergingCount} topic clusters are showing accelerated customer volume.
              </div>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
