import { ChatSessionProvider } from "@/components/chat/ChatSessionProvider";
import { Navbar } from "@/components/navbar/Navbar";
import { requireUser } from "@/lib/auth";

/**
 * Everything under (protected) needs a signed-in user. This check gives a fast redirect for
 * page loads, but it is NOT the security boundary: layouts don't re-render on every client
 * navigation, so each server action and backend call runs requireUser() itself.
 */
export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const user = await requireUser();
  return (
    <div className="flex min-h-screen flex-col bg-md-background text-md-on-background">
      <Navbar user={user} />
      <ChatSessionProvider>
        <main className="flex flex-1 flex-col">{children}</main>
      </ChatSessionProvider>
    </div>
  );
}
