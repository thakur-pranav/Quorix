import { Fragment } from "react";

/**
 * Renders an answer with **bold** and [n] citation markers, WITHOUT dangerouslySetInnerHTML.
 * LLM output is untrusted (a crawled page can inject text into it), so it only ever becomes
 * React text nodes and elements, which React escapes. A "<script>" in an answer is shown as text.
 */
const TOKEN = /(\*\*[^*]+\*\*|\[\d+\])/g;

export function RichText({ text }: { text: string }) {
  return (
    <div className="flex flex-col gap-2">
      {text.split(/\n{2,}/).map((paragraph, p) => (
        <p key={p} className="whitespace-pre-wrap">
          {paragraph.split(TOKEN).map((part, i) => {
            if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={i} className="font-medium">{part.slice(2, -2)}</strong>;
            if (/^\[\d+\]$/.test(part)) {
              return (
                <sup key={i} className="mx-0.5 rounded bg-md-secondary-container px-1 text-[11px] font-medium text-md-on-secondary-container">
                  {part.slice(1, -1)}
                </sup>
              );
            }
            return <Fragment key={i}>{part}</Fragment>;
          })}
        </p>
      ))}
    </div>
  );
}
