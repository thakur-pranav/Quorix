import type { Metadata } from "next";
import { FileText } from "lucide-react";

import { BackendProblem } from "@/components/layout/backend-problem";
import { AnalyticsRunControl } from "@/components/overview/AnalyticsRunControl";
import { RecommendationCard } from "@/components/report/RecommendationCard";
import { ReportHistoryList } from "@/components/report/ReportHistoryList";
import { ReportSummary } from "@/components/report/ReportSummary";
import { EmptyState } from "@/components/shared/EmptyState";
import { PageHeader } from "@/components/shared/PageHeader";
import { requireUser } from "@/lib/auth";
import { BackendError, fastapi } from "@/lib/fastapi/client";
import type { ReportOut, ReportSummaryOut } from "@/lib/fastapi/types";
import { isReadOnlyOrg } from "@/lib/read-only";

export const metadata: Metadata = { title: "Report" };

export default async function ReportPage() {
  const readOnly = isReadOnlyOrg((await requireUser()).organizationId);
  let latestReport: ReportOut | null = null;
  let allReports: ReportSummaryOut[] = [];
  let error: BackendError | null = null;
  try {
    allReports = await fastapi<ReportSummaryOut[]>("/reports");
    if (allReports.length > 0) latestReport = await fastapi<ReportOut>("/reports/latest");
  } catch (e) {
    if (!(e instanceof BackendError)) throw e;
    error = e;
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title={latestReport ? `Report: ${latestReport.period}` : "Report"}
        description="The latest summary of what customers need and what to improve."
        actions={readOnly ? undefined : <AnalyticsRunControl />}
      />

      {error && <BackendProblem error={error} />}

      {!error && !latestReport && (
        <EmptyState
          icon={FileText}
          title="No report yet."
          description="Run the analysis once customers have asked enough questions to generate your first report and recommendations."
        />
      )}

      {latestReport && (
        <>
          {/* Latest Report Overview */}
          <section aria-labelledby="latest-report-heading">
            <h2 id="latest-report-heading" className="sr-only">
              Latest Analysis Report
            </h2>
            <ReportSummary report={latestReport} />
          </section>

          {/* Recommendations List */}
          <section aria-labelledby="recommendations-heading" className="space-y-4">
            <div className="border-b border-slate-200/60 pb-2.5 dark:border-zinc-800">
              <h3 id="recommendations-heading" className="text-base font-semibold text-slate-900 dark:text-white">
                Recommendations ({latestReport.recommendations.length})
              </h3>
              <p className="text-xs text-slate-500">Actionable interventions prioritised from customer conversation evidence</p>
            </div>
            {latestReport.recommendations.length > 0 ? (
              <div className="space-y-4">
                {latestReport.recommendations.map((rec, idx) => (
                  <RecommendationCard key={rec.id} recommendation={rec} index={idx} />
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">No specific recommendations generated for this period.</p>
            )}
          </section>

          {/* Previous Reports Archive */}
          <section aria-labelledby="history-heading" className="space-y-4 pt-4">
            <div className="border-b border-slate-200/60 pb-2.5 dark:border-zinc-800">
              <h3 id="history-heading" className="text-base font-semibold text-slate-900 dark:text-white">
                Previous Reports History
              </h3>
              <p className="text-xs text-slate-500">Historical executive reports from past analysis cycles</p>
            </div>
            <ReportHistoryList reports={allReports} currentReportId={latestReport.id} />
          </section>
        </>
      )}
    </div>
  );
}
