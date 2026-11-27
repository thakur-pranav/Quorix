import Link from "next/link";

import { FeatureSubNav } from "@/components/layout/FeatureSubNav";
import { requireUser } from "@/lib/auth";
import { isReadOnlyOrg } from "@/lib/read-only";

// Server actions and pages here may wait on the API: a chat answer (LLM, with retries) takes
// 10-20 s and a cold backend ~30 s. Vercel's default limit is shorter; 60 s is the Hobby maximum.
export const maxDuration = 60;

export default async function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const user = await requireUser(); // cached per request: the protected layout already called it
  return (
    <div className="flex min-h-[calc(100vh-4rem)] flex-col bg-md-background">
      <FeatureSubNav />
      <div className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
        {isReadOnlyOrg(user.organizationId) && (
          <p className="mb-6 rounded-2xl bg-[#E8DEF8] px-4 py-3 text-sm text-[#1D192B]">
            You&apos;re in the <strong className="font-semibold">read-only demo</strong>: browse everything and ask
            questions; adding, deleting and re-running are off.{" "}
            <Link href="/register" className="font-semibold text-[#6750A4] underline">
              Create your own workspace
            </Link>
            .
          </p>
        )}
        {children}
      </div>
    </div>
  );
}
