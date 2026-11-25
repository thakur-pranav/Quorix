import { cn } from "@/lib/utils";

import type { ChatMessage } from "./chat-session-provider";
import { CitationList } from "./citation-list";
import { ConfidenceMeter } from "./confidence-meter";
import { RichText } from "./rich-text";

export function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "customer") {
    return (
      <div className="flex justify-end">
        <p className="max-w-[80%] whitespace-pre-wrap rounded-[20px] rounded-br-md bg-primary px-4 py-2.5 text-[15px] text-on-primary">
          {message.text}
        </p>
      </div>
    );
  }

  return (
    <div className="flex max-w-[90%] flex-col gap-3">
      <div
        className={cn(
          "rounded-[20px] rounded-bl-md px-4 py-3 text-[15px] leading-relaxed",
          message.isError ? "bg-danger-soft text-danger" : "bg-bg text-ink",
        )}
      >
        <RichText text={message.text} />
      </div>
      {!message.isError && message.confidence !== undefined && (
        <ConfidenceMeter confidence={message.confidence} lowConfidence={message.lowConfidence ?? false} />
      )}
      {!message.isError && message.citations && message.citations.length > 0 && (
        <CitationList citations={message.citations} />
      )}
    </div>
  );
}
