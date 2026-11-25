"use client";

import Link from "next/link";
import { useActionState } from "react";

import { type AuthFormState, registerAction } from "@/actions/auth";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { registerSchema } from "@/lib/validations/auth";

import { useValidatedForm } from "./use-validated-form";

export function RegisterForm() {
  const [state, formAction, pending] = useActionState<AuthFormState, FormData>(registerAction, {});
  const { clientErrors, onSubmit } = useValidatedForm(registerSchema);
  const errors = { ...state.fieldErrors, ...clientErrors };
  const values = state.values ?? {};

  return (
    <form action={formAction} onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-medium">Create your workspace</h1>
        <p className="mt-1 text-sm text-ink-muted">One workspace per company. Your docs stay private to it.</p>
      </div>

      {state.error && <Alert>{state.error}</Alert>}

      <Field label="Your name" name="name" autoComplete="name" defaultValue={values.name} error={errors.name} />
      <Field label="Company" name="organizationName" autoComplete="organization" defaultValue={values.organizationName} error={errors.organizationName} />
      <Field label="Work email" name="email" type="email" autoComplete="email" defaultValue={values.email} error={errors.email} />
      <Field label="Password" name="password" type="password" autoComplete="new-password" hint="8–72 characters" error={errors.password} />
      <Field label="Confirm password" name="confirmPassword" type="password" autoComplete="new-password" error={errors.confirmPassword} />

      <Button type="submit" disabled={pending} className="mt-1 w-full">
        {pending ? "Creating workspace…" : "Create account"}
      </Button>

      <p className="text-center text-sm text-ink-muted">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
