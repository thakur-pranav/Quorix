"use server";

import { randomUUID } from "node:crypto";

import { redirect } from "next/navigation";

import { connectDB } from "@/lib/db";
import { getDummyHash, hashPassword, verifyPassword } from "@/lib/password";
import { clearSessionCookie, setSessionCookie } from "@/lib/session";
import { loginSchema, registerSchema } from "@/lib/validations/auth";
import { LOGIN_WINDOW_SECONDS, LoginAttempt, MAX_FAILED_LOGINS } from "@/models/login-attempt";
import { User } from "@/models/user";

/**
 * Server actions are public HTTP endpoints: anyone can POST to them, so every input is
 * validated here even though the form validated it in the browser too.
 */

export type AuthFormState = {
  error?: string;
  fieldErrors?: Partial<Record<string, string>>;
  values?: Record<string, string>; // echoed back so the form keeps what was typed (never passwords)
};

const INVALID_LOGIN = "Invalid email or password.";
const TOO_MANY = "Too many failed attempts. Please wait 15 minutes and try again.";

function firstErrors(issues: { path: PropertyKey[]; message: string }[]) {
  const fieldErrors: Record<string, string> = {};
  for (const issue of issues) {
    const field = String(issue.path[0] ?? "form");
    fieldErrors[field] ??= issue.message;
  }
  return fieldErrors;
}

export async function registerAction(_prev: AuthFormState, formData: FormData): Promise<AuthFormState> {
  const raw = Object.fromEntries(formData) as Record<string, string>;
  const values = { name: raw.name ?? "", organizationName: raw.organizationName ?? "", email: raw.email ?? "" };
  const parsed = registerSchema.safeParse(raw);
  if (!parsed.success) return { fieldErrors: firstErrors(parsed.error.issues), values };

  const { name, organizationName, email, password } = parsed.data;
  await connectDB();
  if (await User.exists({ email })) {
    return { fieldErrors: { email: "An account with this email already exists." }, values };
  }

  const user = await User.create({
    name,
    organizationName,
    email,
    passwordHash: await hashPassword(password),
    organizationId: `org_${randomUUID()}`, // generated here, never chosen by the client
  });
  await setSessionCookie(String(user._id));
  redirect("/sources");
}

export async function loginAction(_prev: AuthFormState, formData: FormData): Promise<AuthFormState> {
  const raw = Object.fromEntries(formData) as Record<string, string>;
  const values = { email: raw.email ?? "" };
  const parsed = loginSchema.safeParse(raw);
  if (!parsed.success) return { fieldErrors: firstErrors(parsed.error.issues), values };

  const { email, password } = parsed.data;
  await connectDB();

  // Rate limit per email, counted for unknown emails too, so it reveals nothing.
  const since = new Date(Date.now() - LOGIN_WINDOW_SECONDS * 1000);
  if ((await LoginAttempt.countDocuments({ email, createdAt: { $gt: since } })) >= MAX_FAILED_LOGINS) {
    return { error: TOO_MANY, values };
  }

  const user = await User.findOne({ email }).select("+passwordHash").lean();
  // Always run bcrypt, against a dummy hash if there's no such user: same time either way.
  const valid = await verifyPassword(password, user?.passwordHash ?? (await getDummyHash()));
  if (!user || !valid) {
    await LoginAttempt.create({ email });
    return { error: INVALID_LOGIN, values }; // same message: don't reveal which part was wrong
  }

  await LoginAttempt.deleteMany({ email });
  await setSessionCookie(String(user._id));
  redirect("/sources");
}

export async function logoutAction(): Promise<void> {
  await clearSessionCookie();
  redirect("/login");
}
