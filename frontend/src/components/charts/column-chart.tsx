import { cn } from "@/lib/utils";

export type Column = { key: string; label: string; value: number; tooltip: string };
// A vertical rule at a fraction (0..1) of the x axis; its label sits on one side so two close
// markers never print over each other.
export type Marker = { at: number; label: string; side: "left" | "right" };

/**
 * Single-series column chart in plain HTML, rendered on the server: no chart library and no
 * client JavaScript. Specs from the dataviz rules: one hue, columns at most 24px wide with a
 * 4px rounded data end and a square base, a 2px surface gap between touching columns, a
 * hairline baseline, a value printed only on the highlighted column, a hover/focus tooltip on
 * every column, and a table view as the accessible twin of the picture.
 */
export function ColumnChart({
  title,
  columns,
  highlightKey,
  markers = [],
  xTicks,
  height = 160,
  dense = false,
  valueLabel,
}: {
  title: string;
  columns: Column[];
  highlightKey?: string; // the one column that gets its value printed on the cap
  markers?: Marker[];
  xTicks?: { at: number; label: string }[]; // for continuous axes (the histogram); else column labels
  height?: number;
  dense?: boolean; // contiguous bins (histogram): 2px gap, no per-column labels
  valueLabel: string; // the table's value column header
}) {
  const max = Math.max(1, ...columns.map((c) => c.value));
  return (
    <figure className="flex flex-col gap-3">
      <div className="relative" style={{ height }} role="img" aria-label={`${title}. Exact values in the table below.`}>
        {/* hairline baseline; the plot area sits on it */}
        <div className={cn("absolute inset-0 flex items-end border-b border-outline-soft", dense ? "gap-[2px]" : "justify-around")}>
          {columns.map((c) => {
            const pct = (c.value / max) * 100;
            return (
              <div
                key={c.key}
                tabIndex={0}
                aria-label={c.tooltip}
                className={cn("group relative flex h-full items-end justify-center outline-none", dense ? "flex-1" : "w-16")}
              >
                {/* the hit target is the whole slot, taller and wider than the mark */}
                <div
                  className={cn(
                    "w-full max-w-6 rounded-t-[4px] bg-primary transition-opacity group-hover:opacity-80 group-focus:opacity-80",
                    c.value === 0 && "invisible",
                  )}
                  style={{ height: `${pct}%` }}
                />
                {c.key === highlightKey && c.value > 0 && (
                  <span className="absolute text-xs font-medium text-ink" style={{ bottom: `calc(${pct}% + 4px)` }}>
                    {c.value}
                  </span>
                )}
                <span
                  role="tooltip"
                  className="pointer-events-none absolute bottom-full z-10 mb-1 hidden whitespace-nowrap rounded-field bg-ink px-2.5 py-1.5 text-xs text-bg group-hover:block group-focus:block"
                >
                  {c.tooltip}
                </span>
              </div>
            );
          })}
        </div>
        {markers.map((m) => (
          <div key={m.label} className="pointer-events-none absolute inset-y-0 border-l border-ink/40" style={{ left: `${m.at * 100}%` }}>
            <span className={cn("absolute -top-5 whitespace-nowrap text-xs text-ink-muted", m.side === "left" ? "right-1" : "left-1")}>
              {m.label}
            </span>
          </div>
        ))}
      </div>

      {/* x axis: column labels, or ticks on a continuous scale */}
      {xTicks ? (
        <div className="relative h-4 text-xs text-ink-muted tabular-nums">
          {xTicks.map((t) => (
            <span key={t.label} className="absolute -translate-x-1/2" style={{ left: `${t.at * 100}%` }}>
              {t.label}
            </span>
          ))}
        </div>
      ) : (
        <div className="flex justify-around text-xs text-ink-muted">
          {columns.map((c) => (
            <span key={c.key} className="w-16 text-center">
              {c.label}
            </span>
          ))}
        </div>
      )}

      <details className="text-sm">
        <summary className="cursor-pointer text-ink-muted hover:text-ink">Show as table</summary>
        <table className="mt-2 w-full text-left tabular-nums">
          <thead className="text-xs text-ink-muted">
            <tr>
              <th className="py-1 font-medium">{dense ? "Range" : "Month"}</th>
              <th className="py-1 text-right font-medium">{valueLabel}</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((c) => (
              <tr key={c.key} className="border-t border-outline-soft/60">
                <td className="py-1">{c.label}</td>
                <td className="py-1 text-right">{c.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
