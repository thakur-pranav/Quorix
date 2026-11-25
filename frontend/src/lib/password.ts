import "server-only";

import bcrypt from "bcryptjs";

/** Cost 10 = 2^10 key-expansion rounds: ~70 ms per hash. Slow on purpose: makes guessing expensive. */
const BCRYPT_COST = 10;

export function hashPassword(password: string): Promise<string> {
  return bcrypt.hash(password, BCRYPT_COST); // a random salt is generated and stored in the hash
}

export function verifyPassword(password: string, hash: string): Promise<boolean> {
  return bcrypt.compare(password, hash);
}

/**
 * A real bcrypt hash of a random string, used when the email doesn't exist. Comparing against
 * it costs the same ~70 ms as a real check, so response time doesn't reveal which emails have
 * accounts (timing attack). The reference skipped bcrypt for unknown emails (SPEC section 9 #7).
 */
let dummyHash: Promise<string> | undefined;

export function getDummyHash(): Promise<string> {
  dummyHash ??= bcrypt.hash(crypto.randomUUID(), BCRYPT_COST);
  return dummyHash;
}
