import type { Metadata } from "next";

import { BackendProblem } from "@/components/layout/backend-problem";
import { BackendStatus } from "@/components/shared/BackendStatus";
import { PageHeader } from "@/components/shared/PageHeader";
import { AddWebsiteForm } from "@/components/sources/AddWebsiteForm";
import { SourceList } from "@/components/sources/SourceList";
import { UploadDocumentForm } from "@/components/sources/UploadDocumentForm";
import { requireUser } from "@/lib/auth";
import { BackendError, fastapi } from "@/lib/fastapi/client";
import type { SourceOut } from "@/lib/fastapi/types";
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
    <div className="space-y-6">
      <PageHeader
        title="Sources"
        description="Manage the documents and websites Quorix uses as knowledge."
        actions={<BackendStatus status={error ? "unavailable" : "connected"} />}
      />

      {error ? (
        <BackendProblem error={error} />
      ) : (
        <>
          {!readOnly && (
            <section aria-labelledby="connect-sources-heading" className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <h2 id="connect-sources-heading" className="sr-only">
                Connect New Knowledge Sources
              </h2>
              <AddWebsiteForm />
              <UploadDocumentForm />
            </section>
          )}

          <section aria-labelledby="connected-sources-heading" className="space-y-3">
            <h2 id="connected-sources-heading" className="text-base font-semibold text-slate-900 dark:text-white">
              Connected Knowledge ({sources.length})
            </h2>
            <SourceList sources={sources} readOnly={readOnly} />
          </section>
        </>
      )}
    </div>
  );
}
