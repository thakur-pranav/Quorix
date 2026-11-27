import { describe, expect, it } from "vitest";

import { formatGrowth, formatTopicGrowth } from "./formatters";

describe("formatTopicGrowth", () => {
  it("calls a topic with no questions last month new", () => {
    expect(formatTopicGrowth(17, 0)).toBe("new");
  });

  it("shows signed percentages", () => {
    expect(formatTopicGrowth(1.5, 8)).toBe("+150%");
    expect(formatTopicGrowth(-0.6, 40)).toBe("-60%");
    expect(formatTopicGrowth(0, 10)).toBe("0%");
  });

  it("caps huge growth instead of printing a scary number", () => {
    expect(formatTopicGrowth(3, 5)).toBe("+300%");
    expect(formatTopicGrowth(16, 1)).toBe(">+300%");
  });
});

describe("formatGrowth", () => {
  it("treats every value as a ratio (the reference printed +150% as '+2%')", () => {
    expect(formatGrowth(1.5)).toBe("+150%");
    expect(formatGrowth(0.25)).toBe("+25%");
    expect(formatGrowth(null)).toBe("0%");
  });
});
