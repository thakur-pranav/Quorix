"use client";

import { createContext, use, useCallback, useState } from "react";

import { askQuestionAction } from "@/actions/intelligence";

import type { ChatMessage } from "./MessageBubble";

export interface ChatSessionContextValue {
  messages: ChatMessage[];
  isSending: boolean;
  sendMessage: (question: string) => Promise<void>;
  clearChat: () => void;
}

const ChatSessionContext = createContext<ChatSessionContextValue | null>(null);

/**
 * Chat state lives in the protected layout, which stays mounted while you move between pages:
 * the conversation survives navigation. Plain React state, so a full reload starts a new session
 * (the backend still has the history, keyed by sessionId). Every question goes through a server
 * action: the browser never calls FastAPI.
 */
export function ChatSessionProvider({ children }: { children: React.ReactNode }) {
  // Lazy initial state: randomUUID runs once per mount, not on every render.
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);

  const sendMessage = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed) return;
      // Functional updates: each one builds on the latest state, never a stale copy.
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "user", text: trimmed }]);
      setIsSending(true);
      try {
        const result = await askQuestionAction({ question: trimmed, sessionId });
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
        setIsSending(false);
      }
    },
    [sessionId],
  );

  const clearChat = useCallback(() => {
    setMessages([]);
    setSessionId(crypto.randomUUID());
  }, []);

  return <ChatSessionContext value={{ messages, isSending, sendMessage, clearChat }}>{children}</ChatSessionContext>;
}

export function useChatSession(): ChatSessionContextValue {
  const session = use(ChatSessionContext);
  if (!session) throw new Error("useChatSession must be used inside ChatSessionProvider");
  return session;
}
