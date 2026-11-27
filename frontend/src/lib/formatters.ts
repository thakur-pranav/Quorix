/**
 * Formatting utilities for Quorix metrics, dates, and values (from the reference UI, growth fixed).
 */

export function formatPercent(value?: number | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "0%";
  }

  // If value is between 0 and 1, convert to 0-100 scale
  const normalized = value <= 1 && value >= -1 ? value * 100 : value;
  return `${Math.round(normalized)}%`;
}

export function formatConfidence(value?: number | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "N/A";
  }

  const normalized = value <= 1 && value >= 0 ? value * 100 : value;
  return `${Math.round(normalized)}%`;
}

/**
 * Growth is always a ratio from the API (1.5 = +150%). The zip version only multiplied values
 * between -1 and 1, so +150% printed as "+2%". Capped like the backend's priority formula.
 */
export function formatGrowth(value?: number | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "0%";
  }
  const pct = Math.round(value * 100);
  if (pct > 300) return ">+300%";
  return `${pct > 0 ? "+" : ""}${pct}%`;
}

export function formatNumber(value?: number | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "0";
  }
  return new Intl.NumberFormat("en-US").format(value);
}

export function formatDate(isoString?: string | null): string {
  if (!isoString) {
    return "N/A";
  }
  try {
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) {
      return isoString;
    }
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    }).format(date);
  } catch {
    return isoString;
  }
}

export function formatDateTime(isoString?: string | null): string {
  if (!isoString) {
    return "N/A";
  }
  try {
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) {
      return isoString;
    }
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  } catch {
    return isoString;
  }
}

/** A topic's growth vs last month: "new" when it had no questions then (growth = its count). */
export function formatTopicGrowth(growth: number, previousCount: number): string {
  if (previousCount === 0) return "new";
  return formatGrowth(growth);
}
