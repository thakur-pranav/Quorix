import { cn } from "@/lib/utils";

/** A tonal surface. Depth comes from the surface tint, not from shadows. */
export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-card bg-surface-2 p-5", className)} {...props} />;
}

export function Alert({ tone = "danger", className, ...props }: React.HTMLAttributes<HTMLDivElement> & { tone?: "danger" | "warning" | "success" }) {
  const tones = {
    danger: "bg-danger-soft text-danger",
    warning: "bg-warning-soft text-warning",
    success: "bg-success-soft text-success",
  };
  return <div role="alert" className={cn("rounded-field px-4 py-3 text-sm", tones[tone], className)} {...props} />;
}
