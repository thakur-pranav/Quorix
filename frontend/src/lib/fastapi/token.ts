import "server-only";

import { SignJWT } from "jose";

import { getEnv } from "@/lib/env";
import type { SafeUser } from "@/models/user";

/** SPEC section 2: the token contract FastAPI's get_tenant() verifies. */
export const SERVICE_TOKEN_TTL_SECONDS = 60;
export const SERVICE_ISSUER = "quorix-web";
export const SERVICE_AUDIENCE = "quorix-api";

/**
 * A fresh 60-second token per backend call. Short-lived, so a leaked token is useless a minute
 * later. The org comes from the user record in MongoDB, never from the browser.
 */
export async function signServiceToken(user: SafeUser): Promise<string> {
  return new SignJWT({ org: user.organizationId, email: user.email })
    .setProtectedHeader({ alg: "HS256", typ: "JWT" })
    .setSubject(user.id)
    .setIssuer(SERVICE_ISSUER)
    .setAudience(SERVICE_AUDIENCE)
    .setIssuedAt()
    .setExpirationTime(`${SERVICE_TOKEN_TTL_SECONDS}s`)
    .sign(new TextEncoder().encode(getEnv().BACKEND_JWT_SECRET));
}
