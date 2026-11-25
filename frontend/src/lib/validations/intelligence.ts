import { z } from "zod";

/** Mirrors the backend limits (backend/app/config.py). The backend validates again. */
export const MAX_QUESTION_CHARS = 2000;
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const ALLOWED_UPLOAD_EXTENSIONS = [".pdf", ".docx", ".txt", ".md"] as const;

export const sourceIdSchema = z.string().regex(/^src_[0-9a-f]{12}$/, "Invalid source id");

export const addWebsiteSchema = z.object({
  url: z
    .string()
    .trim()
    .pipe(z.url({ protocol: /^https?$/, error: "Enter a full http(s) URL, e.g. https://docs.example.com" })),
  label: z
    .string()
    .trim()
    .max(200)
    .optional()
    .transform((value) => value || undefined),
});

export const uploadSchema = z
  .instanceof(File, { message: "Choose a file" })
  .refine((file) => file.size > 0, "The file is empty")
  .refine((file) => file.size <= MAX_UPLOAD_BYTES, "Files can be at most 10 MB")
  .refine(
    (file) => ALLOWED_UPLOAD_EXTENSIONS.some((ext) => file.name.toLowerCase().endsWith(ext)),
    `Allowed types: ${ALLOWED_UPLOAD_EXTENSIONS.join(", ")}`,
  );

export const chatSchema = z.object({
  question: z.string().trim().min(1, "Type a question").max(MAX_QUESTION_CHARS),
  sessionId: z.string().regex(/^[a-zA-Z0-9_-]{1,64}$/, "Invalid session"),
});

export type ChatInput = z.infer<typeof chatSchema>;

export const topicIdSchema = z.string().regex(/^ins_[0-9a-f]{12}$/, "Invalid topic id");
