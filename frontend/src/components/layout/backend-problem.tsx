import { WakingUp } from "@/components/layout/waking-up";
import { ErrorState } from "@/components/shared/ErrorState";
import { type BackendError, isWakingUp } from "@/lib/fastapi/client";

/** How a page shows a failed backend call: "waking up" (and retry) for a sleeping backend, else the error. */
export function BackendProblem({ error }: { error: BackendError }) {
  return isWakingUp(error) ? <WakingUp /> : <ErrorState title="Something went wrong" message={error.message} />;
}
