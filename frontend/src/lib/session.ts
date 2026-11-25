import "server-only";

import { jwtVerify, SignJWT } from "jose";
import { cookies } from "next/headers";

import { getEnv, isProduction } from "@/lib/env";

/**
 * Browser session: a signed JWT (HS256, AUTH_SECRET) in an httpOnly cookie. Stateless: the
 * server stores nothing per session. Not the same token as the 60 s service token for FastAPI:
 * different secret, different audience, so one can never be used as the other.
 */
export const SESSION_COOKIE = "quorix_session";
export const SESSION_TTL_SECONDS = 7 * 24 * 60 * 60;
const ISSUER = "quorix-web";
const AUDIENCE = "quorix-session";

const key = () => new TextEncoder().encode(getEnv().AUTH_SECRET);

export async function createSessionToken(userId: string): Promise<string> {
  return new SignJWT({})
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(userId)
    .setIssuer(ISSUER)
    .setAudience(AUDIENCE)
    .setIssuedAt()
    .setExpirationTime(`${SESSION_TTL_SECONDS}s`)
    .sign(key());
}

/** The user id from a valid token, or null for a missing, forged, expired or wrong-audience one. */
export async function verifySessionToken(token: string | undefined): Promise<string | null> {
  if (!token) return null;
  try {
    const { payload } = await jwtVerify(token, key(), {
      algorithms: ["HS256"], // pinned: an "alg: none" token is rejected
      issuer: ISSUER,
      audience: AUDIENCE,
    });
    return typeof payload.sub === "string" && payload.sub ? payload.sub : null;
  } catch {
    return null;
  }
}

export async function setSessionCookie(userId: string): Promise<void> {
  (await cookies()).set(SESSION_COOKIE, await createSessionToken(userId), {
    httpOnly: true, // JavaScript can't read it, so an XSS bug can't steal the session
    secure: isProduction(), // HTTPS only in production (localhost is plain HTTP)
    sameSite: "lax", // not sent on cross-site POSTs: a basic CSRF defence
    path: "/",
    maxAge: SESSION_TTL_SECONDS,
  });
}

export async function clearSessionCookie(): Promise<void> {
  (await cookies()).delete(SESSION_COOKIE);
}

export async function readSessionUserId(): Promise<string | null> {
  return verifySessionToken((await cookies()).get(SESSION_COOKIE)?.value);
}
