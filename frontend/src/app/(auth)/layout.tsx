import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/auth";

/** The login and register pages bring their own full-screen layout (reference UI). */
export default async function AuthLayout({ children }: { children: React.ReactNode }) {
  if (await getCurrentUser()) redirect("/overview"); // already signed in
  return children;
}
