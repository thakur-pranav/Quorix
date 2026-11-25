import "server-only";

import { isValidObjectId } from "mongoose";
import { redirect } from "next/navigation";
import { cache } from "react";

import { connectDB } from "@/lib/db";
import { readSessionUserId } from "@/lib/session";
import { type SafeUser, toSafeUser, User } from "@/models/user";

/**
 * The logged-in user, or null. Data Access Layer: the one place that turns a cookie into a
 * user. `cache()` dedupes it per request, so the layout, the page and the server actions
 * of one request share a single database lookup.
 */
export const getCurrentUser = cache(async (): Promise<SafeUser | null> => {
  const userId = await readSessionUserId();
  if (!userId || !isValidObjectId(userId)) return null;
  await connectDB();
  const user = await User.findById(userId).lean();
  return user ? toSafeUser(user) : null; // a deleted user's old cookie stops working
});

/** For protected pages and every server action: the user, or a redirect to /login. */
export async function requireUser(): Promise<SafeUser> {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  return user;
}
