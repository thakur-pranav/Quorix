import { SignJWT } from "jose";
import { describe, expect, it } from "vitest";

import { createSessionToken, SESSION_TTL_SECONDS, verifySessionToken } from "./session";

const authKey = () => new TextEncoder().encode(process.env.AUTH_SECRET);

describe("session tokens", () => {
  it("round-trips the user id and lasts 7 days", async () => {
    const token = await createSessionToken("665f1c2b9d3e4a0012345678");
    expect(await verifySessionToken(token)).toBe("665f1c2b9d3e4a0012345678");

    const [, payload] = token.split(".");
    const claims = JSON.parse(Buffer.from(payload, "base64url").toString());
    expect(claims.exp - claims.iat).toBe(SESSION_TTL_SECONDS);
  });

  it("rejects a missing, garbage, tampered or wrong-secret token", async () => {
    const token = await createSessionToken("user-1");
    const [h, p, s] = token.split(".");
    const forgedPayload = Buffer.from(JSON.stringify({ sub: "admin" })).toString("base64url");

    expect(await verifySessionToken(undefined)).toBeNull();
    expect(await verifySessionToken("not.a.jwt")).toBeNull();
    expect(await verifySessionToken(`${h}.${forgedPayload}.${s}`)).toBeNull();
    expect(await verifySessionToken(`${h}.${p}.${s.slice(0, -2)}xx`)).toBeNull();

    const other = await new SignJWT({}).setProtectedHeader({ alg: "HS256" }).setSubject("user-1")
      .setIssuer("quorix-web").setAudience("quorix-session").setExpirationTime("1h")
      .sign(new TextEncoder().encode("a-completely-different-secret-that-is-long-enough"));
    expect(await verifySessionToken(other)).toBeNull();
  });

  it("rejects an expired token", async () => {
    const expired = await new SignJWT({}).setProtectedHeader({ alg: "HS256" }).setSubject("user-1")
      .setIssuer("quorix-web").setAudience("quorix-session")
      .setIssuedAt(Math.floor(Date.now() / 1000) - 100).setExpirationTime(Math.floor(Date.now() / 1000) - 10)
      .sign(authKey());
    expect(await verifySessionToken(expired)).toBeNull();
  });

  it("rejects a service token used as a session (different audience)", async () => {
    const serviceShaped = await new SignJWT({ org: "org_x" }).setProtectedHeader({ alg: "HS256" })
      .setSubject("user-1").setIssuer("quorix-web").setAudience("quorix-api").setExpirationTime("1h")
      .sign(authKey());
    expect(await verifySessionToken(serviceShaped)).toBeNull();
  });
});
