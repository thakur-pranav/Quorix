"use client";

import { useState } from "react";
import type { z } from "zod";

/**
 * Client-side check with the SAME Zod schema the server action uses. If it fails, stop the
 * submit and show field errors at once; if it passes, the form posts to the server action,
 * which validates again (it's a public endpoint, so the browser check is only a convenience).
 */
export function useValidatedForm(schema: z.ZodType) {
  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    const result = schema.safeParse(Object.fromEntries(new FormData(event.currentTarget)));
    if (result.success) {
      setClientErrors({});
      return;
    }
    event.preventDefault();
    const errors: Record<string, string> = {};
    for (const issue of result.error.issues) errors[String(issue.path[0])] ??= issue.message;
    setClientErrors(errors);
  }

  return { clientErrors, onSubmit };
}
