import "server-only";

import { getEnv } from "@/lib/env";

export const READ_ONLY_MESSAGE = "This is a read-only demo workspace: sign up to add your own docs.";

/**
 * Is this organization the public demo? Used to hide controls and to refuse write actions early.
 * The backend refuses the same writes with 403 on its own: this layer is UX, not the protection.
 */
export function isReadOnlyOrg(organizationId: string): boolean {
  return getEnv()
    .READ_ONLY_ORGS.split(",")
    .map((org) => org.trim())
    .includes(organizationId);
}
