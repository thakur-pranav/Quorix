"use client";

import { ArrowUp } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { chatSchema, MAX_QUESTION_CHARS } from "@/lib/validations/intelligence";

import { useChatSession } from "./chat-session-provider";
import { MessageBubble } from "./message-bubble";

export function ChatWindow() {
  const { messages, pending, send, reset } = useChatSession();
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, pending]);

  async function ask(question: string) {
    const parsed = chatSchema.shape.question.safeParse(question);
    if (!parsed.success) return setError(parsed.error.issues[0].message);
    setError(null);
    setDraft("");
    await send(parsed.data);
  }

  return (
    <section className="flex flex-col overflow-hidden rounded-card bg-surface-2">
      <div className="flex items-center justify-between border-b border-outline-soft/60 px-5 py-3">
        <p className="text-sm text-ink-muted">{messages.length === 0 ? "New conversation" : `${messages.length} messages`}</p>
        {messages.length > 0 && (
          <Button size="sm" variant="text" onClick={reset} disabled={pending}>
            New conversation
          </Button>
        )}
      </div>

      {/* aria-live: screen readers announce new answers as they arrive */}
      <div className="flex min-h-80 flex-col gap-5 px-5 py-6" aria-live="polite">
        {messages.length === 0 && (
          <p className="text-ink-muted">
            Ask anything your customers ask. If your sources don&apos;t cover it, Quorix says so instead of guessing.
          </p>
        )}
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {pending && <p className="text-sm text-ink-muted">Searching your docs…</p>}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void ask(draft);
        }}
        className="flex items-end gap-2 border-t border-outline-soft/60 bg-surface p-3"
      >
        <label htmlFor="question" className="sr-only">
          Your question
        </label>
        <textarea
          id="question"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void ask(draft);
            }
          }}
          rows={1}
          maxLength={MAX_QUESTION_CHARS}
          placeholder="Ask a question…"
          className="max-h-40 min-h-11 flex-1 resize-none rounded-field bg-surface-3 px-3.5 py-2.5 text-[15px] focus:outline-none"
        />
        <Button type="submit" disabled={pending || !draft.trim()} aria-label="Send question" className="size-11 px-0">
          <ArrowUp className="size-5" aria-hidden />
        </Button>
      </form>
      {error && <p className="px-5 pb-3 text-[13px] text-danger">{error}</p>}
    </section>
  );
}
