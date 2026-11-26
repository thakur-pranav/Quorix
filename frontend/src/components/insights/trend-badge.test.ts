import { describe, expect, it } from "vitest";

import { formatGrowth } from "./trend-badge";

describe("formatGrowth", () => {
  it("calls a topic with no questions last month new", () => {
    expect(formatGrowth(17, 0)).toBe("new");
  });

  it("shows signed percentages", () => {
    expect(formatGrowth(1.5, 8)).toBe("+150%");
    expect(formatGrowth(-0.6, 40)).toBe("-60%");
    expect(formatGrowth(0, 10)).toBe("0%");
  });

  it("caps huge growth instead of printing a scary number", () => {
    expect(formatGrowth(3, 5)).toBe("+300%");
    expect(formatGrowth(16, 1)).toBe(">+300%");
  });
});
