import { LandingPage } from "@/components/landing/LandingPage";
import { getCurrentUser } from "@/lib/auth";

/** The public landing page; the navbar shows the workspace links when you're signed in. */
export default async function Home() {
  return <LandingPage user={await getCurrentUser()} />;
}
