import { AppHeader } from "@/components/layout/app-header";
import { ChatSessionProvider } from "@/components/chat/chat-session-provider";
import { requireUser } from "@/lib/auth";

/**
 * Everything under (protected) needs a signed-in user. This check gives a fast redirect for
 * page loads, but it is NOT the security boundary: layouts don't re-render on every client
 * navigation, so each server action and backend call runs requireUser() itself.
 */
export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const user = await requireUser();
  return (
    <ChatSessionProvider>
      <AppHeader user={user} />
      {children}
    </ChatSessionProvider>
  );
}
