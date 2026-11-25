import type { Metadata } from "next";

import { SourcesView } from "@/components/sources/sources-view";
import { Alert } from "@/components/ui/card";
import { BackendError, fastapi } from "@/lib/fastapi/client";
import type { SourceOut } from "@/lib/fastapi/types";

export const metadata: Metadata = { title: "Sources" };

export default async function SourcesPage() {
  let sources: SourceOut[] = [];
  let error: string | null = null;
  try {
    sources = await fastapi<SourceOut[]>("/sources");
  } catch (e) {
    if (!(e instanceof BackendError)) throw e;
    error = e.message;
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-[28px] font-medium tracking-tight">Sources</h1>
        <p className="mt-1 text-ink-muted">
          Connect your help center or upload documents. Answers come only from what you add here.
        </p>
      </div>
      {error ? <Alert>{error}</Alert> : <SourcesView initialSources={sources} />}
    </div>
  );
}
