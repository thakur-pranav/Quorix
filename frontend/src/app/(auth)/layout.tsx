import Link from "next/link";
import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/auth";

export default async function AuthLayout({ children }: { children: React.ReactNode }) {
  if (await getCurrentUser()) redirect("/sources"); // already signed in

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4 py-12">
      <Link href="/" className="mb-8 text-2xl font-medium tracking-tight text-ink">
        Quorix
      </Link>
      <div className="w-full max-w-md rounded-card bg-surface-2 p-8">{children}</div>
      <p className="mt-6 max-w-md text-center text-sm text-ink-muted">
        Answers from your own docs, and a monthly report on the questions they don&apos;t answer yet.
      </p>
    </main>
  );
}
