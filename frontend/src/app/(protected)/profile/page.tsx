import type { Metadata } from "next";

import { ProfileCard } from "@/components/profile/ProfileCard";
import { requireUser } from "@/lib/auth";
import { BackendError, fastapi } from "@/lib/fastapi/client";
import type { OverviewOut, SourceOut } from "@/lib/fastapi/types";

export const metadata: Metadata = { title: "Profile" };

/** Account details, plus what the workspace holds. A sleeping backend leaves those as "–". */
export default async function ProfilePage() {
  const user = await requireUser();
  let sources: SourceOut[] | null = null;
  let overview: OverviewOut | null = null;
  try {
    [sources, overview] = await Promise.all([fastapi<SourceOut[]>("/sources"), fastapi<OverviewOut>("/overview")]);
  } catch (e) {
    if (!(e instanceof BackendError)) throw e;
  }

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <ProfileCard
        user={user}
        sources={sources}
        questionsThisMonth={overview ? overview.queryCount : null}
        topicsThisMonth={overview ? overview.topicCount : null}
      />
    </div>
  );
}
