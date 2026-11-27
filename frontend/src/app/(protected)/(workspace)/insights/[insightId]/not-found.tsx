import Link from "next/link";
import { ArrowLeft, SearchX } from "lucide-react";

import { EmptyState } from "@/components/shared/EmptyState";

/**
 * Rendered when the topic page calls notFound(): a malformed id, or a 404 from the API. Next.js
 * shows the nearest not-found.tsx inside the layouts, so the navbar and workspace nav stay.
 * One message for "doesn't exist" and "belongs to another organization", so it can't be used
 * to discover which topic ids exist elsewhere.
 */
export default function TopicNotFound() {
  return (
    <div className="space-y-6">
      <Link
        href="/insights"
        className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-[#6750A4] dark:text-slate-400"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to Insights
      </Link>
      <EmptyState
        icon={SearchX}
        title="Topic not found"
        description="This topic doesn't exist, or it isn't part of your workspace. Topics are rebuilt each time analytics runs, so an old link may point to one that's gone."
        action={
          <Link
            href="/insights"
            className="inline-flex items-center rounded-full bg-[#6750A4] px-5 py-2 text-sm font-medium text-white shadow-xs transition hover:bg-[#6750A4]/90 active:scale-95"
          >
            See current topics
          </Link>
        }
      />
    </div>
  );
}
