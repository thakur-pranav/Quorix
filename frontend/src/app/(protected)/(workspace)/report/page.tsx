import type { Metadata } from "next";
import Link from "next/link";

import { RunAnalysisButton } from "@/components/insights/run-analysis-button";
import { Alert, Card } from "@/components/ui/card";
import { LocalTime } from "@/components/ui/local-time";
import { requireUser } from "@/lib/auth";
import { BackendError, fastapi } from "@/lib/fastapi/client";
import { isReadOnlyOrg } from "@/lib/read-only";
import type { RecommendationCategory, ReportOut, ReportSummaryOut } from "@/lib/fastapi/types";
import { cn, formatPercent } from "@/lib/utils";

export const metadata: Metadata = { title: "Report" };

const CATEGORY: Record<RecommendationCategory, { label: string; className: string }> = {
  documentation: { label: "Docs gap", className: "bg-warning-soft text-warning" },
  product: { label: "Product fix", className: "bg-danger-soft text-danger" },
  faq: { label: "FAQ", className: "bg-secondary-soft text-on-secondary-soft" },
  customer_issue: { label: "Customer follow-up", className: "bg-primary-soft text-on-primary-soft" },
};

export default async function ReportPage() {
  const readOnly = isReadOnlyOrg((await requireUser()).organizationId);
  let report: ReportOut | null = null;
  let history: ReportSummaryOut[] = [];
  let error: string | null = null;
  try {
    history = await fastapi<ReportSummaryOut[]>("/reports");
    if (history.length > 0) report = await fastapi<ReportOut>("/reports/latest");
  } catch (e) {
    if (!(e instanceof BackendError)) throw e;
    error = e.message;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[28px] font-medium tracking-tight">Report{report ? `: ${report.period}` : ""}</h1>
          <p className="mt-1 text-ink-muted">What to fix next, backed by the questions customers actually asked.</p>
        </div>
        {!readOnly && <RunAnalysisButton />}
      </div>

      {error && <Alert>{error}</Alert>}
      {!error && !report && (
        <p className="rounded-card border border-dashed border-outline-soft px-5 py-10 text-center text-ink-muted">
          No report yet. Run the analysis once customers have asked enough questions.
        </p>
      )}

      {report && (
        <>
          <Card className="flex flex-col gap-4">
            <p className="leading-relaxed">{report.summary}</p>
            <dl className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
              <div>
                <dt className="text-xs text-ink-muted">Questions</dt>
                <dd className="text-lg font-medium">{report.queryCount}</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-muted">Conversations</dt>
                <dd className="text-lg font-medium">{report.conversationCount}</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-muted">Weak doc match</dt>
                <dd className="text-lg font-medium">{formatPercent(report.unansweredRate)}</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-muted">Generated</dt>
                <dd className="text-lg font-medium">
                  <LocalTime iso={report.generatedAt} />
                </dd>
              </div>
            </dl>
          </Card>

          <section aria-labelledby="recs" className="flex flex-col gap-3">
            <h2 id="recs" className="text-lg font-medium">
              Recommendations
            </h2>
            <ol className="flex flex-col gap-3">
              {report.recommendations.map((rec, i) => (
                <li key={rec.id}>
                  <Card className="flex flex-col gap-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-ink-muted">{i + 1}.</span>
                      <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", CATEGORY[rec.category].className)}>
                        {CATEGORY[rec.category].label}
                      </span>
                      <Link href={`/insights/${rec.clusterId}`} className="text-sm text-primary hover:underline">
                        {rec.clusterName}
                      </Link>
                      <span className="text-xs text-ink-muted">{rec.volume} questions</span>
                    </div>
                    <h3 className="text-lg font-medium">{rec.headline}</h3>
                    <p className="text-ink-muted">{rec.body}</p>
                    {rec.faqAnswer && (
                      <div className="rounded-field bg-surface px-4 py-3 text-sm">
                        <p className="font-medium">Suggested FAQ answer</p>
                        <p className="mt-1 text-ink-muted">{rec.faqAnswer}</p>
                      </div>
                    )}
                    <p className="text-sm">
                      <span className="font-medium">Expected effect: </span>
                      <span className="text-ink-muted">{rec.expectedEffect}</span>
                    </p>
                    <details className="text-sm">
                      <summary className="cursor-pointer select-none text-ink-muted">
                        {rec.supportingQueries.length} questions behind this
                      </summary>
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-muted">
                        {rec.supportingQueries.map((q) => (
                          <li key={q}>{q}</li>
                        ))}
                      </ul>
                    </details>
                  </Card>
                </li>
              ))}
            </ol>
          </section>

          {history.length > 1 && (
            <section aria-labelledby="past" className="flex flex-col gap-2">
              <h2 id="past" className="text-lg font-medium">
                Past months
              </h2>
              <ul className="divide-y divide-outline-soft/50 rounded-card bg-surface-2 px-5">
                {history.map((r) => (
                  <li key={r.id} className="flex justify-between gap-4 py-3 text-sm">
                    <span className="font-medium">{r.period}</span>
                    <span className="text-ink-muted">
                      {r.queryCount} questions · {formatPercent(r.unansweredRate)} weak match
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
