import Link from "next/link";
import { Building, BriefcaseBusiness, Database, Globe, FileText, LogOut, Mail, Plus } from "lucide-react";

import { logoutAction } from "@/actions/auth";
import { SourceStatusBadge } from "@/components/sources/SourceStatusBadge";
import { UserAvatar } from "@/components/ui/user-avatar";
import type { SourceOut } from "@/lib/fastapi/types";
import { formatNumber } from "@/lib/formatters";
import type { SafeUser } from "@/models/user";

interface ProfileCardProps {
  user: SafeUser;
  sources: SourceOut[] | null; // null: the backend didn't answer (the rest of the profile still shows)
  questionsThisMonth: number | null;
  topicsThisMonth: number | null;
}

/**
 * The reference UI's profile layout, with real data. Its services, verification and subscription
 * fields described features Quorix doesn't have, so those cards show what the workspace really
 * holds instead: sources, indexed chunks, this month's questions and topics.
 */
export function ProfileCard({ user, sources, questionsThisMonth, topicsThisMonth }: ProfileCardProps) {
  const stats: [string, string][] = [
    ["Knowledge Sources", sources === null ? "–" : formatNumber(sources.length)],
    ["Chunks Indexed", sources === null ? "–" : formatNumber(sources.reduce((sum, s) => sum + s.chunkCount, 0))],
    ["Questions This Month", questionsThisMonth === null ? "–" : formatNumber(questionsThisMonth)],
    ["Topics This Month", topicsThisMonth === null ? "–" : formatNumber(topicsThisMonth)],
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-8 pb-16">
      {/* Header Account Card */}
      <div className="relative overflow-hidden rounded-[32px] border border-slate-200/80 bg-md-surface-container p-6 shadow-sm sm:p-8">
        <div aria-hidden="true" className="pointer-events-none absolute -right-20 -top-20 h-60 w-60 rounded-full bg-md-primary/10 blur-3xl" />

        <div className="relative flex flex-col items-start justify-between gap-6 sm:flex-row sm:items-center">
          <div className="flex items-center gap-4 sm:gap-5">
            <UserAvatar name={user.name} size="lg" className="h-16 w-16 text-xl" />
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-md-on-surface sm:text-3xl">{user.name}</h1>
              <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-md-on-surface-variant">
                <span className="inline-flex items-center gap-1.5">
                  <Mail className="h-4 w-4" />
                  {user.email}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <Building className="h-4 w-4" />
                  {user.organizationName}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 self-end sm:self-center">
            <Link
              href="/overview"
              className="inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white shadow-xs transition hover:bg-[#6750A4] active:scale-95 dark:bg-white dark:text-slate-950"
            >
              <BriefcaseBusiness className="h-4 w-4" />
              Open Workspace
            </Link>
            {/* A plain form posting to the server action: works before any JavaScript loads. */}
            <form action={logoutAction}>
              <button
                type="submit"
                className="inline-flex items-center rounded-full border border-slate-200 bg-white px-5 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 hover:text-rose-600 active:scale-95 dark:border-zinc-700 dark:bg-zinc-800 dark:text-slate-200"
              >
                <LogOut className="mr-2 h-4 w-4" />
                Sign Out
              </button>
            </form>
          </div>
        </div>

        {/* Status Indicators */}
        <div className="mt-8 grid grid-cols-2 gap-4 border-t border-md-outline/10 pt-6 sm:grid-cols-4">
          {stats.map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-slate-100 bg-white/70 p-3.5 dark:border-zinc-800 dark:bg-zinc-900/70">
              <span className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</span>
              <p className="mt-1 text-sm font-bold text-slate-900 dark:text-white">{value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Knowledge Sources Section */}
      <div className="rounded-[32px] border border-slate-200/80 bg-md-surface-container p-6 shadow-sm sm:p-8">
        <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-md-on-surface">Connected Knowledge Sources</h2>
            <p className="mt-1 text-sm text-md-on-surface-variant">The websites and documents your answers come from.</p>
          </div>
          <Link href="/sources" className="inline-flex items-center gap-1.5 text-sm font-semibold text-md-primary hover:underline">
            <Plus className="h-4 w-4" />
            Manage Sources &rarr;
          </Link>
        </div>

        {sources === null ? (
          <p className="py-4 text-center text-xs text-slate-400">The analysis service isn&apos;t answering right now.</p>
        ) : sources.length === 0 ? (
          <p className="py-4 text-center text-xs text-slate-400">No knowledge sources connected yet.</p>
        ) : (
          <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {sources.map((source) => {
              const Icon = source.kind === "website" ? Globe : FileText;
              return (
                <li
                  key={source.id}
                  className="flex items-center justify-between gap-3 rounded-[24px] border border-slate-200/80 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
                >
                  <span className="flex min-w-0 items-center gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#E8DEF8] text-[#6750A4]">
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-semibold text-slate-900 dark:text-white">{source.label}</span>
                      <span className="block text-xs text-slate-500">
                        <Database className="mr-1 inline h-3 w-3" />
                        {formatNumber(source.chunkCount)} chunks
                      </span>
                    </span>
                  </span>
                  <SourceStatusBadge status={source.status} />
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Organization & Account Details */}
      <div className="rounded-[32px] border border-slate-200/80 bg-md-surface-container p-6 shadow-sm sm:p-8">
        <h2 className="text-xl font-bold tracking-tight text-md-on-surface">Account & Organization Details</h2>
        <p className="mt-1 text-sm text-md-on-surface-variant">
          Organization identity used for tenant-scoped knowledge isolation.
        </p>
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-slate-200/80 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
            <span className="text-xs font-medium text-slate-500">Organization Name</span>
            <p className="mt-1 font-semibold text-slate-900 dark:text-white">{user.organizationName}</p>
          </div>
          <div className="rounded-2xl border border-slate-200/80 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
            <span className="text-xs font-medium text-slate-500">Tenant Identifier</span>
            <p className="mt-1 font-mono text-xs text-slate-600 dark:text-slate-400">{user.organizationId}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
