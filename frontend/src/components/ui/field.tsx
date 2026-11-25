import { useId } from "react";

import { cn } from "@/lib/utils";

type FieldProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
  hint?: string;
};

/** Label + filled input + error, wired for screen readers (aria-invalid, aria-describedby). */
export function Field({ label, error, hint, className, id, ...props }: FieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const messageId = `${inputId}-message`;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-medium text-ink">
        {label}
      </label>
      <input
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={error || hint ? messageId : undefined}
        className={cn(
          "h-11 rounded-field border-b-2 border-outline bg-surface-3 px-3.5 text-[15px] text-ink",
          "placeholder:text-ink-muted/60 focus:border-primary focus:outline-none",
          "aria-invalid:border-danger",
          className,
        )}
        {...props}
      />
      {(error || hint) && (
        <p id={messageId} className={cn("text-[13px]", error ? "text-danger" : "text-ink-muted")}>
          {error ?? hint}
        </p>
      )}
    </div>
  );
}
