"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

// Analytics first (what a support lead reads), then the tools (Ask, Sources), then quality.
const tabs = [
  { href: "/overview", label: "Overview" },
  { href: "/insights", label: "Insights" },
  { href: "/report", label: "Report" },
  { href: "/ask", label: "Ask" },
  { href: "/sources", label: "Sources" },
  { href: "/evaluation", label: "Evaluation" },
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
