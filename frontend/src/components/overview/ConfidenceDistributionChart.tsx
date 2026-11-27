"use client";

import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { OverviewOut } from "@/lib/fastapi/types";

interface ConfidenceDistributionChartProps {
  bins: OverviewOut["confidenceHistogram"];
  threshold: number; // the backend's live low-confidence threshold: refused below it
  strongMatch: number;
  period: string;
}

/**
 * This month's questions by retrieval confidence, with the two decision lines. An average hides
 * the shape; this shows how many questions the assistant refuses and how many match strongly.
 * Styled like the other overview cards (Recharts, Material You colours).
 */
export function ConfidenceDistributionChart({ bins, threshold, strongMatch, period }: ConfidenceDistributionChartProps) {
  if (bins.length === 0) return null;
  const width = 1 / bins.length;
  const data = bins.map((b) => ({ start: b.start, label: b.start.toFixed(2), count: b.count, range: `${b.start.toFixed(2)}–${(b.start + width).toFixed(2)}` }));
  // The x axis is categorical (one band per bin): a reference line sits on the bin it falls in.
  const binLabel = (value: number) => (Math.min(Math.floor(value / width), bins.length - 1) * width).toFixed(2);

  return (
    <div className="rounded-3xl border border-slate-200/70 bg-[#F3EDF7]/30 p-5 dark:border-zinc-800 dark:bg-zinc-900/30">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-white">How Well The Docs Matched, {period}</h3>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Questions by retrieval confidence. Below {threshold.toFixed(2)} the assistant says it couldn&apos;t find it;
          from {strongMatch.toFixed(2)} it&apos;s a strong match.
        </p>
      </div>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 18, right: 10, left: -20, bottom: 0 }} barCategoryGap={2}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
            <XAxis dataKey="label" tickLine={false} axisLine={false} interval={4} tick={{ fill: "#64748B", fontSize: 12 }} />
            <YAxis tickLine={false} axisLine={false} allowDecimals={false} tick={{ fill: "#64748B", fontSize: 12 }} />
            <Tooltip
              cursor={{ fill: "#E8DEF8", opacity: 0.5 }}
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const item = payload[0].payload as (typeof data)[number];
                  return (
                    <div className="rounded-xl border border-slate-200 bg-white p-2.5 shadow-md dark:border-zinc-700 dark:bg-zinc-900">
                      <p className="text-xs font-semibold text-slate-900 dark:text-white">Confidence {item.range}</p>
                      <p className="text-xs text-[#6750A4] dark:text-purple-400">
                        {item.count} question{item.count === 1 ? "" : "s"}
                      </p>
                    </div>
                  );
                }
                return null;
              }}
            />
            <ReferenceLine x={binLabel(threshold)} stroke="#7D5260" strokeDasharray="4 3" label={{ value: `Refused below ${threshold.toFixed(2)}`, position: "insideTopRight", fill: "#7D5260", fontSize: 11 }} />
            <ReferenceLine x={binLabel(strongMatch)} stroke="#386A20" strokeDasharray="4 3" label={{ value: `Strong ${strongMatch.toFixed(2)}+`, position: "insideTopLeft", fill: "#386A20", fontSize: 11 }} />
            <Bar dataKey="count" fill="#6750A4" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
