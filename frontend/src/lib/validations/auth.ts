import { z } from "zod";

/** bcrypt only uses the first 72 BYTES. "72 characters" isn't enough: é or 😀 take 2–4 bytes. */
const BCRYPT_MAX_BYTES = 72;
const utf8Bytes = (value: string) => new TextEncoder().encode(value).length;

const email = z.string().trim().toLowerCase().pipe(z.email("Enter a valid email address"));

const password = z
  .string()
  .min(8, "Password must be at least 8 characters")
  .max(72, "Password must be at most 72 characters")
  .refine((value) => utf8Bytes(value) <= BCRYPT_MAX_BYTES, {
    message: "Password is too long (special characters count as more than one)",
  });

export const registerSchema = z
  .object({
    name: z.string().trim().min(1, "Enter your name").max(80),
    organizationName: z.string().trim().min(1, "Enter your company name").max(120),
    email,
    password,
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ["confirmPassword"],
  });

export const loginSchema = z.object({
  email,
  password: z.string().min(1, "Enter your password").max(200),
});

export type RegisterInput = z.infer<typeof registerSchema>;
export type LoginInput = z.infer<typeof loginSchema>;
