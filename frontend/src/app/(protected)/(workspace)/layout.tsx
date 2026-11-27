import Link from "next/link";

import { WorkspaceNav } from "@/components/layout/workspace-nav";
import { requireUser } from "@/lib/auth";
import { isReadOnlyOrg } from "@/lib/read-only";

// Server actions and pages here may wait on the API: a chat answer (LLM, with retries) takes
// 10-20 s and a cold backend ~30 s. Vercel's default limit is shorter; 60 s is the Hobby maximum.
export const maxDuration = 60;

export default async function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const user = await requireUser(); // cached per request: the protected layout already called it
  return (
    <>
      <WorkspaceNav />
      <main className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6">
        {isReadOnlyOrg(user.organizationId) && (
          <p className="mb-6 rounded-field bg-secondary-soft px-4 py-3 text-sm text-on-secondary-soft">
            You&apos;re in the <strong className="font-medium">read-only demo</strong>: browse everything and ask
            questions; adding, deleting and re-running are off.{" "}
            <Link href="/register" className="font-medium underline">
              Create your own workspace
            </Link>
            .
          </p>
        )}
        {children}
      </main>
    </>
  );
}
