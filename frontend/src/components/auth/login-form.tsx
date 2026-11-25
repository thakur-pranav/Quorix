"use client";

import Link from "next/link";
import { useActionState } from "react";

import { type AuthFormState, loginAction } from "@/actions/auth";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { loginSchema } from "@/lib/validations/auth";

import { useValidatedForm } from "./use-validated-form";

export function LoginForm() {
  const [state, formAction, pending] = useActionState<AuthFormState, FormData>(loginAction, {});
  const { clientErrors, onSubmit } = useValidatedForm(loginSchema);
  const errors = { ...state.fieldErrors, ...clientErrors };

  return (
    <form action={formAction} onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-medium">Sign in</h1>
        <p className="mt-1 text-sm text-ink-muted">Welcome back.</p>
      </div>

      {state.error && <Alert>{state.error}</Alert>}

      <Field label="Email" name="email" type="email" autoComplete="email" defaultValue={state.values?.email} error={errors.email} />
      <Field label="Password" name="password" type="password" autoComplete="current-password" error={errors.password} />

      <Button type="submit" disabled={pending} className="mt-1 w-full">
        {pending ? "Signing in…" : "Sign in"}
      </Button>

      <p className="text-center text-sm text-ink-muted">
        New to Quorix?{" "}
        <Link href="/register" className="font-medium text-primary hover:underline">
          Create an account
        </Link>
      </p>
    </form>
  );
}
