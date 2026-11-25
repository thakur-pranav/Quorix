import { cn } from "@/lib/utils";

const variants = {
  filled: "bg-primary text-on-primary hover:bg-primary-hover",
  tonal: "bg-secondary-soft text-on-secondary-soft hover:bg-primary-soft",
  outlined: "border border-outline-soft text-primary hover:bg-surface-2",
  text: "text-primary hover:bg-surface-2",
  danger: "text-danger hover:bg-danger-soft",
} as const;

const sizes = {
  md: "h-10 px-5 text-sm",
  sm: "h-8 px-3.5 text-[13px]",
} as const;

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
};

/** Pill-shaped button (MD3). Variants are a closed set, so the UI stays consistent. */
export function Button({ variant = "filled", size = "md", className, type = "button", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex shrink-0 items-center justify-center gap-2 rounded-full font-medium tracking-[0.01em]",
        "transition-colors duration-150 disabled:pointer-events-none disabled:opacity-50",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}
