import { describe, expect, it } from "vitest";

import { countDelta, histogramColumns, pointsDelta } from "./overview";

describe("countDelta", () => {
  it("is relative to last month", () => {
    expect(countDelta(256, 246)).toEqual({ text: "+4% vs last month", direction: "up" });
    expect(countDelta(200, 250)).toEqual({ text: "-20% vs last month", direction: "down" });
    expect(countDelta(10, 10)).toEqual({ text: "0% vs last month", direction: "flat" });
  });

  it("has nothing to say without a previous month, and no division by zero", () => {
    expect(countDelta(5, undefined)).toBeNull();
    expect(countDelta(5, 0)).toEqual({ text: "new vs last month", direction: "up" });
  });
});

describe("pointsDelta", () => {
  it("uses percentage points for rates, not a percent of a percent", () => {
    expect(pointsDelta(0.15, 0.18)).toEqual({ text: "-3 pts vs last month", direction: "down" });
    expect(pointsDelta(0.5, undefined)).toBeNull();
  });
});

describe("histogramColumns", () => {
  it("labels each bin by its range and says the count in words", () => {
    const [first, second] = histogramColumns([
      { start: 0, count: 1 },
      { start: 0.5, count: 3 },
    ]);
    expect(first).toMatchObject({ label: "0.00–0.50", value: 1, tooltip: "1 question at confidence 0.00–0.50" });
    expect(second.tooltip).toBe("3 questions at confidence 0.50–1.00");
  });
});
