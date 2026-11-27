import { jwtVerify } from "jose";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth", () => ({
  requireUser: vi.fn(async () => ({
    id: "665f1c2b9d3e4a0012345678",
    name: "Ada",
    email: "ada@example.com",
    organizationName: "Acme",
    organizationId: "org_acme",
  })),
}));

import { BackendError, fastapi, isWakingUp, readableError } from "./client";

afterEach(() => vi.unstubAllGlobals());

function stubFetch(response: Response) {
  const spy = vi.fn<(url: string, init: RequestInit) => Promise<Response>>(async () => response);
  vi.stubGlobal("fetch", spy);
  return spy;
}

describe("fastapi client", () => {
  it("sends a Bearer token that verifies, to the backend URL, uncached", async () => {
    const spy = stubFetch(Response.json([{ id: "src_1" }]));
    const data = await fastapi<{ id: string }[]>("/sources");

    expect(data).toEqual([{ id: "src_1" }]);
    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("http://backend.test/api/sources");
    expect(init.cache).toBe("no-store");

    const token = String((init.headers as Record<string, string>).Authorization).replace("Bearer ", "");
    const { payload } = await jwtVerify(token, new TextEncoder().encode(process.env.BACKEND_JWT_SECRET), {
      issuer: "quorix-web",
      audience: "quorix-api",
    });
    expect(payload.org).toBe("org_acme");
  });

  it("never sends an org header: the org travels only inside the signed token", async () => {
    const spy = stubFetch(Response.json({}));
    await fastapi("/chat", { method: "POST", json: { question: "hi", sessionId: "s" } });
    const headers = spy.mock.calls[0][1].headers as Record<string, string>;
    expect(Object.keys(headers).map((h) => h.toLowerCase())).not.toContain("x-organization-id");
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("maps a network failure to a 503 BackendError", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("fetch failed"); }));
    await expect(fastapi("/sources")).rejects.toMatchObject({ status: 503 });
  });

  it("says 'waking up' for a sleeping backend: no connection, or a proxy's 502-504 page", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("fetch failed"); }));
    const unreachable = await fastapi("/sources").catch((e: unknown) => e);
    expect(isWakingUp(unreachable)).toBe(true);
    expect((unreachable as BackendError).message).toMatch(/waking up/);

    stubFetch(new Response("<html>Space is starting</html>", { status: 503 }));
    await expect(fastapi("/sources")).rejects.toMatchObject({ status: 503, message: expect.stringMatching(/waking up/) });
  });

  it("keeps FastAPI's own message on a 503 it sent itself, and doesn't call other errors 'waking up'", async () => {
    stubFetch(Response.json({ detail: "Database is busy" }, { status: 503 }));
    await expect(fastapi("/sources")).rejects.toMatchObject({ message: "Database is busy" });
    expect(isWakingUp(new BackendError(500, "boom"))).toBe(false);
    expect(isWakingUp(new Error("not a backend error"))).toBe(false);
  });

  it("turns FastAPI error bodies into readable BackendErrors", async () => {
    stubFetch(Response.json({ detail: "URL not allowed: internal address" }, { status: 400 }));
    await expect(fastapi("/sources", { method: "POST", json: {} })).rejects.toEqual(
      new BackendError(400, "URL not allowed: internal address"),
    );
  });

  it("returns undefined for 204 No Content", async () => {
    stubFetch(new Response(null, { status: 204 }));
    await expect(fastapi("/sources/src_1", { method: "DELETE" })).resolves.toBeUndefined();
  });
});

describe("readableError", () => {
  it("formats a 422 list and falls back by status", () => {
    const detail = [{ loc: ["body", "question"], msg: "String should have at least 1 character" }];
    expect(readableError(422, { detail })).toBe("question: String should have at least 1 character");
    expect(readableError(500, null)).toMatch(/problem/);
    expect(readableError(401, {})).toMatch(/sign in/);
  });
});
