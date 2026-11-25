import { describe, expect, it } from "vitest";

import { addWebsiteSchema, chatSchema, sourceIdSchema, uploadSchema } from "./intelligence";

describe("addWebsiteSchema", () => {
  it("accepts http(s) URLs and drops an empty label", () => {
    expect(addWebsiteSchema.parse({ url: " https://docs.example.com ", label: "" })).toEqual({
      url: "https://docs.example.com",
      label: undefined,
    });
  });

  it.each(["ftp://example.com", "javascript:alert(1)", "docs.example.com", ""])("rejects %s", (url) => {
    expect(addWebsiteSchema.safeParse({ url }).success).toBe(false);
  });
});

describe("uploadSchema", () => {
  const file = (name: string, size: number) => new File([new Uint8Array(size)], name);

  it("accepts the four allowed types", () => {
    for (const name of ["a.pdf", "b.DOCX", "c.txt", "d.md"]) {
      expect(uploadSchema.safeParse(file(name, 10)).success).toBe(true);
    }
  });

  it.each([
    ["exe", file("virus.exe", 10)],
    ["empty", file("empty.txt", 0)],
    ["over 10 MB", file("big.pdf", 10 * 1024 * 1024 + 1)],
  ])("rejects %s", (_label, f) => {
    expect(uploadSchema.safeParse(f).success).toBe(false);
  });
});

describe("chatSchema and sourceIdSchema", () => {
  it("trims the question and bounds it", () => {
    expect(chatSchema.parse({ question: "  hi  ", sessionId: "abc-123" }).question).toBe("hi");
    expect(chatSchema.safeParse({ question: "   ", sessionId: "s" }).success).toBe(false);
    expect(chatSchema.safeParse({ question: "x".repeat(2001), sessionId: "s" }).success).toBe(false);
    expect(chatSchema.safeParse({ question: "hi", sessionId: "bad id!" }).success).toBe(false);
  });

  it("only accepts real source ids (no path tricks)", () => {
    expect(sourceIdSchema.safeParse("src_ab12cd34ef56").success).toBe(true);
    expect(sourceIdSchema.safeParse("../../admin").success).toBe(false);
  });
});
