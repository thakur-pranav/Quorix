import { describe, expect, it } from "vitest";

import { loginSchema, registerSchema } from "./auth";

const valid = {
  name: "Ada",
  organizationName: "Acme",
  email: "  Ada@Example.COM ",
  password: "correct horse",
  confirmPassword: "correct horse",
};

describe("registerSchema", () => {
  it("accepts valid input and normalises the email", () => {
    const parsed = registerSchema.parse(valid);
    expect(parsed.email).toBe("ada@example.com");
  });

  it.each([
    ["short password", { password: "short", confirmPassword: "short" }, "password"],
    ["73 characters", { password: "a".repeat(73), confirmPassword: "a".repeat(73) }, "password"],
    ["mismatched confirm", { confirmPassword: "something else" }, "confirmPassword"],
    ["bad email", { email: "not-an-email" }, "email"],
    ["blank name", { name: "   " }, "name"],
  ])("rejects %s", (_label, override, field) => {
    const result = registerSchema.safeParse({ ...valid, ...override });
    expect(result.success).toBe(false);
    expect(result.error?.issues.map((i) => i.path[0])).toContain(field);
  });

  it("allows exactly 72 ASCII characters", () => {
    const pw = "a".repeat(72);
    expect(registerSchema.safeParse({ ...valid, password: pw, confirmPassword: pw }).success).toBe(true);
  });

  it("rejects 72 characters that are more than 72 bytes (bcrypt would silently truncate)", () => {
    const pw = "é".repeat(40); // 40 characters, 80 bytes in UTF-8
    const result = registerSchema.safeParse({ ...valid, password: pw, confirmPassword: pw });
    expect(result.success).toBe(false);
  });
});

describe("loginSchema", () => {
  it("requires a password but doesn't apply signup rules to it", () => {
    expect(loginSchema.safeParse({ email: "a@b.co", password: "x" }).success).toBe(true);
    expect(loginSchema.safeParse({ email: "a@b.co", password: "" }).success).toBe(false);
  });
});
