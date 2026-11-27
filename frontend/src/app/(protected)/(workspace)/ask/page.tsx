import type { Metadata } from "next";

import { ChatWindow } from "@/components/chat/ChatWindow";
import { PageHeader } from "@/components/shared/PageHeader";

export const metadata: Metadata = { title: "Ask" };

export default function AskPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Ask" description="Ask questions grounded in your connected knowledge." />
      <ChatWindow />
    </div>
  );
}
