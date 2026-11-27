"use server";

import { revalidatePath } from "next/cache";

import { requireUser } from "@/lib/auth";
import { isReadOnlyOrg, READ_ONLY_MESSAGE } from "@/lib/read-only";
import { BackendError, fastapi } from "@/lib/fastapi/client";
import type { ActionResult, ChatResponse, SourceOut } from "@/lib/fastapi/types";
import { addWebsiteSchema, chatSchema, sourceIdSchema, uploadSchema } from "@/lib/validations/intelligence";

/**
 * Sources and chat. Every action: requireUser() → Zod safeParse → backend client → a plain
 * {success, data | error} result. Errors become messages; nothing throws into the browser.
 */

async function run<T>(call: () => Promise<T>): Promise<ActionResult<T>> {
  try {
    return { success: true, data: await call() };
  } catch (error) {
    if (error instanceof BackendError) return { success: false, error: error.message };
    throw error; // redirects (no session) and real bugs must not be swallowed
  }
}

export async function listSourcesAction(): Promise<ActionResult<SourceOut[]>> {
  await requireUser();
  return run(() => fastapi<SourceOut[]>("/sources"));
}

export async function addWebsiteAction(input: { url: string; label?: string }): Promise<ActionResult<SourceOut>> {
  const user = await requireUser();
  if (isReadOnlyOrg(user.organizationId)) return { success: false, error: READ_ONLY_MESSAGE };
  const parsed = addWebsiteSchema.safeParse(input);
  if (!parsed.success) return { success: false, error: parsed.error.issues[0].message };
  const result = await run(() =>
    fastapi<SourceOut>("/sources", {
      method: "POST",
      json: { kind: "website", location: parsed.data.url, label: parsed.data.label },
    }),
  );
  revalidatePath("/sources");
  return result;
}

export async function uploadDocumentAction(formData: FormData): Promise<ActionResult<SourceOut>> {
  const user = await requireUser();
  if (isReadOnlyOrg(user.organizationId)) return { success: false, error: READ_ONLY_MESSAGE };
  const parsed = uploadSchema.safeParse(formData.get("file"));
  if (!parsed.success) return { success: false, error: parsed.error.issues[0].message };
  const body = new FormData();
  body.set("file", parsed.data, parsed.data.name);
  const result = await run(() => fastapi<SourceOut>("/sources/upload", { method: "POST", formData: body }));
  revalidatePath("/sources");
  return result;
}

export async function reindexSourceAction(sourceId: string): Promise<ActionResult<SourceOut>> {
  const user = await requireUser();
  if (isReadOnlyOrg(user.organizationId)) return { success: false, error: READ_ONLY_MESSAGE };
  const parsed = sourceIdSchema.safeParse(sourceId);
  if (!parsed.success) return { success: false, error: "Invalid source." };
  const result = await run(() => fastapi<SourceOut>(`/sources/${parsed.data}/reindex`, { method: "POST" }));
  revalidatePath("/sources");
  return result;
}

export async function deleteSourceAction(sourceId: string): Promise<ActionResult<null>> {
  const user = await requireUser();
  if (isReadOnlyOrg(user.organizationId)) return { success: false, error: READ_ONLY_MESSAGE };
  const parsed = sourceIdSchema.safeParse(sourceId);
  if (!parsed.success) return { success: false, error: "Invalid source." };
  const result = await run(async () => {
    await fastapi<void>(`/sources/${parsed.data}`, { method: "DELETE" });
    return null;
  });
  revalidatePath("/sources");
  return result;
}

export async function askQuestionAction(input: { question: string; sessionId: string }): Promise<ActionResult<ChatResponse>> {
  await requireUser();
  const parsed = chatSchema.safeParse(input);
  if (!parsed.success) return { success: false, error: parsed.error.issues[0].message };
  return run(() => fastapi<ChatResponse>("/chat", { method: "POST", json: parsed.data }));
}

/** Queue the analytics batch for every period (oldest first). Runs in the background on FastAPI. */
export async function runAnalyticsAction(): Promise<ActionResult<{ periods: string[] }>> {
  const user = await requireUser();
  if (isReadOnlyOrg(user.organizationId)) return { success: false, error: READ_ONLY_MESSAGE };
  const result = await run(() => fastapi<{ status: string; periods: string[] }>("/analytics/run", { method: "POST", json: {} }));
  revalidatePath("/insights");
  revalidatePath("/overview");
  revalidatePath("/report");
  return result.success ? { success: true, data: { periods: result.data.periods } } : result;
}
