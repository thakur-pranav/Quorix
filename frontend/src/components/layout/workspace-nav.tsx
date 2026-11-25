"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

// Overview, Insights, Report and Evaluation join this list on Days 5 and 6.
const tabs = [
  { href: "/sources", label: "Sources" },
  { href: "/ask", label: "Ask" },
];

export function WorkspaceNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Workspace" className="border-b border-outline-soft/60 bg-bg">
      <div className="mx-auto flex max-w-5xl gap-1 overflow-x-auto px-4 py-2 sm:px-6">
        {tabs.map((tab) => {
          const active = pathname.startsWith(tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
                active ? "bg-secondary-soft text-on-secondary-soft" : "text-ink-muted hover:bg-surface-2 hover:text-ink",
              )}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
