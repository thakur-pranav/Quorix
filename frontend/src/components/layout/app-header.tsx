import Link from "next/link";

import { logoutAction } from "@/actions/auth";
import { Button } from "@/components/ui/button";
import type { SafeUser } from "@/models/user";

export function AppHeader({ user }: { user: SafeUser }) {
  return (
    <header className="border-b border-outline-soft/60 bg-bg">
      <div className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/sources" className="text-xl font-medium tracking-tight">
          Quorix
        </Link>
        <div className="flex items-center gap-3">
          <div className="hidden text-right leading-tight sm:block">
            <p className="text-sm font-medium">{user.organizationName}</p>
            <p className="text-xs text-ink-muted">{user.email}</p>
          </div>
          <form action={logoutAction}>
            <Button type="submit" variant="text" size="sm">
              Sign out
            </Button>
          </form>
        </div>
      </div>
    </header>
  );
}
