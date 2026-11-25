import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Join class names; later Tailwind classes win over earlier conflicting ones. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPercent(value: number): string {
  return `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%`;
}
