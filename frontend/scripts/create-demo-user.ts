/**
 * Create (or update) the login for the seeded demo organization, so its analytics are visible in
 * the app. Idempotent: running it again only resets the password and name.
 *
 * Credentials come from the environment, never from the code or the command line (shell history),
 * and are never printed. Put DEMO_EMAIL and DEMO_PASSWORD in .env.local, then:
 *     pnpm demo:user
 *
 * It reuses the app's own User model, password hashing and signup validation, so the demo login
 * follows exactly the rules a real signup does. Read-only enforcement for the demo account is Day 7.
 */
import mongoose from "mongoose";

import { connectDB } from "@/lib/db";
import { hashPassword } from "@/lib/password";
import { registerSchema } from "@/lib/validations/auth";
import { User } from "@/models/user";

/** The organization the backend's seed script fills (python -m scripts.seed_conversations --org org_demo). */
const DEMO_ORG_ID = process.env.DEMO_ORG_ID ?? "org_demo";
const ORG_ID_PATTERN = /^org_[a-z0-9_]{1,40}$/;

async function main(): Promise<void> {
  const password = process.env.DEMO_PASSWORD ?? "";
  const parsed = registerSchema.safeParse({
    name: "Demo user",
    organizationName: "Quorix demo (GitHub Billing docs)",
    email: process.env.DEMO_EMAIL ?? "",
    password,
    confirmPassword: password,
  });
  if (!parsed.success) {
    // Field names and rule messages only: the values themselves (a password) are never echoed.
    const problems = parsed.error.issues.map((issue) => `${issue.path.join(".")}: ${issue.message}`);
    throw new Error(`Set DEMO_EMAIL and DEMO_PASSWORD in .env.local.\n  ${problems.join("\n  ")}`);
  }
  if (!ORG_ID_PATTERN.test(DEMO_ORG_ID)) throw new Error("DEMO_ORG_ID must look like org_demo");

  await connectDB();
  const { email, name, organizationName } = parsed.data;
  const existing = await User.findOne({ email });
  if (existing && existing.organizationId !== DEMO_ORG_ID) {
    // Never move a real account into the demo tenant (or out of its own): that would hand it
    // another organization's data.
    throw new Error("That email already belongs to an account in another organization. Use a different DEMO_EMAIL.");
  }

  await User.updateOne(
    { email },
    {
      $set: { name, organizationName, passwordHash: await hashPassword(parsed.data.password) },
      $setOnInsert: { email, organizationId: DEMO_ORG_ID },
    },
    { upsert: true },
  );
  console.log(`${existing ? "Updated" : "Created"} the demo login for ${DEMO_ORG_ID}. Sign in with DEMO_EMAIL.`);
}

main()
  .catch((error: unknown) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  })
  .finally(() => mongoose.disconnect());
