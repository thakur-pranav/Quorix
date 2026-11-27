import type { Metadata } from "next";

import { BackendProblem } from "@/components/layout/backend-problem";
import { SourcesView } from "@/components/sources/sources-view";
import { BackendError, fastapi } from "@/lib/fastapi/client";
import type { SourceOut } from "@/lib/fastapi/types";
import { requireUser } from "@/lib/auth";
import { isReadOnlyOrg } from "@/lib/read-only";

export const metadata: Metadata = { title: "Sources" };

export default async function SourcesPage() {
  const readOnly = isReadOnlyOrg((await requireUser()).organizationId);
  let sources: SourceOut[] = [];
  let error: BackendError | null = null;
  try {
    sources = await fastapi<SourceOut[]>("/sources");
  } catch (e) {
    if (!(e instanceof BackendError)) throw e;
    error = e;
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-[28px] font-medium tracking-tight">Sources</h1>
        <p className="mt-1 text-ink-muted">
          Connect your help center or upload documents. Answers come only from what you add here.
        </p>
      </div>
      {error ? <BackendProblem error={error} /> : <SourcesView initialSources={sources} readOnly={readOnly} />}
    </div>
  );
}
