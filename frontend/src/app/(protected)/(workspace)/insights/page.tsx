import type { Metadata } from "next";

import { InsightList } from "@/components/insights/InsightList";
import { BackendProblem } from "@/components/layout/backend-problem";
import { AnalyticsRunControl } from "@/components/overview/AnalyticsRunControl";
import { PageHeader } from "@/components/shared/PageHeader";
import { requireUser } from "@/lib/auth";
import { BackendError, fastapi } from "@/lib/fastapi/client";
import type { TopicOut } from "@/lib/fastapi/types";
import { isReadOnlyOrg } from "@/lib/read-only";

export const metadata: Metadata = { title: "Insights" };

export default async function InsightsPage() {
  const readOnly = isReadOnlyOrg((await requireUser()).organizationId);
  let insights: TopicOut[] = [];
  let error: BackendError | null = null;
  try {
    insights = await fastapi<TopicOut[]>("/insights");
  } catch (e) {
    if (!(e instanceof BackendError)) throw e;
    error = e;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Insights"
        period={insights[0]?.period}
        description="What customers are asking, what is changing, and where the knowledge base appears weakest."
        actions={readOnly ? undefined : <AnalyticsRunControl />}
      />
      {error ? <BackendProblem error={error} /> : <InsightList insights={insights} />}
    </div>
  );
}
