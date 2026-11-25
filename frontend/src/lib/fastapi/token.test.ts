import { decodeProtectedHeader, jwtVerify } from "jose";
import { describe, expect, it } from "vitest";

import type { SafeUser } from "@/models/user";

import { signServiceToken } from "./token";

const user: SafeUser = {
  id: "665f1c2b9d3e4a0012345678",
  name: "Ada",
  email: "ada@example.com",
  organizationName: "Acme",
  organizationId: "org_3f1c2b9d-3e4a-4012-8456-789abcdef012",
};

describe("signServiceToken (SPEC section 2 contract)", () => {
  it("produces exactly the claims FastAPI's get_tenant() verifies", async () => {
    const token = await signServiceToken(user);
    const { payload } = await jwtVerify(token, new TextEncoder().encode(process.env.BACKEND_JWT_SECRET), {
      algorithms: ["HS256"],
      issuer: "quorix-web",
      audience: "quorix-api",
    });

    expect(decodeProtectedHeader(token).alg).toBe("HS256");
    expect(payload.sub).toBe(user.id);
    expect(payload.org).toBe(user.organizationId);
    expect(payload.email).toBe(user.email);
    expect(payload.exp! - payload.iat!).toBe(60);
    expect(user.organizationId).toMatch(/^[a-zA-Z0-9_-]{1,64}$/); // the backend's org regex
  });

  it("is not signed with the session secret", async () => {
    const token = await signServiceToken(user);
    await expect(
      jwtVerify(token, new TextEncoder().encode(process.env.AUTH_SECRET), { algorithms: ["HS256"] }),
    ).rejects.toThrow();
  });
});
