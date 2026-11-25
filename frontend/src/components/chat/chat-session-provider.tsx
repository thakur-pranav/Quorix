"use client";

import { createContext, use, useCallback, useState } from "react";

import { askQuestionAction } from "@/actions/intelligence";
import type { Citation } from "@/lib/fastapi/types";

export type ChatMessage = {
  id: string;
  role: "customer" | "assistant";
  text: string;
  confidence?: number;
  lowConfidence?: boolean;
  citations?: Citation[];
  isError?: boolean;
};

type ChatSession = {
  messages: ChatMessage[];
  pending: boolean;
  send: (question: string) => Promise<void>;
  reset: () => void;
};

const ChatSessionContext = createContext<ChatSession | null>(null);

/**
 * Chat state lives in the protected layout, which stays mounted while you move between pages:
 * the conversation survives navigation. It's plain React state, so a full page reload starts
 * a new session (the backend still has the history, keyed by sessionId).
 */
export function ChatSessionProvider({ children }: { children: React.ReactNode }) {
  // Lazy initial state: randomUUID runs once per mount, not on every render.
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);

  const send = useCallback(
    async (question: string) => {
      // Functional updates: each one builds on the latest state, never a stale copy.
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "customer", text: question }]);
      setPending(true);
      try {
        const result = await askQuestionAction({ question, sessionId });
        const reply: ChatMessage = result.success
          ? { ...result.data, role: "assistant" }
          : { id: crypto.randomUUID(), role: "assistant", text: result.error, isError: true };
        setMessages((prev) => [...prev, reply]);
      } catch {
        setMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: "assistant", text: "Something went wrong. Please try again.", isError: true },
        ]);
      } finally {
        setPending(false);
      }
    },
    [sessionId],
  );

  const reset = useCallback(() => {
    setMessages([]);
    setSessionId(crypto.randomUUID());
  }, []);

  return <ChatSessionContext value={{ messages, pending, send, reset }}>{children}</ChatSessionContext>;
}

export function useChatSession(): ChatSession {
  const session = use(ChatSessionContext);
  if (!session) throw new Error("useChatSession must be used inside ChatSessionProvider");
  return session;
}
