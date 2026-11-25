import type { Metadata } from "next";

import { ChatWindow } from "@/components/chat/chat-window";

export const metadata: Metadata = { title: "Ask" };

export default function AskPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[28px] font-medium tracking-tight">Ask your docs</h1>
        <p className="mt-1 text-ink-muted">
          See what your customers see: answers come only from your sources, with citations and a confidence score.
        </p>
      </div>
      <ChatWindow />
    </div>
  );
}
