"use client";

import { useState, useTransition } from "react";

import { addWebsiteAction, uploadDocumentAction } from "@/actions/intelligence";
import { Button } from "@/components/ui/button";
import { Alert, Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { addWebsiteSchema, ALLOWED_UPLOAD_EXTENSIONS, uploadSchema } from "@/lib/validations/intelligence";

export function AddSourceForms({ onAdded }: { onAdded: () => Promise<void> }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <WebsiteForm onAdded={onAdded} />
      <UploadForm onAdded={onAdded} />
    </div>
  );
}

// onSubmit (not <form action>): React 19 resets a form after an action runs, which would wipe
// what the user typed whenever validation fails. These forms reset themselves only on success.
function WebsiteForm({ onAdded }: { onAdded: () => Promise<void> }) {
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const parsed = addWebsiteSchema.safeParse({ url: formData.get("url"), label: formData.get("label") || undefined });
    if (!parsed.success) return setError(parsed.error.issues[0].message);
    setError(null);
    startTransition(async () => {
      const result = await addWebsiteAction(parsed.data);
      if (!result.success) return setError(result.error);
      form.reset();
      await onAdded();
    });
  }

  return (
    <Card>
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <div>
          <h2 className="font-medium">Crawl a website</h2>
          <p className="text-sm text-ink-muted">We follow links inside the section you give us, up to 120 pages.</p>
        </div>
        <Field label="Help center URL" name="url" type="url" placeholder="https://docs.example.com/help" />
        <Field label="Label (optional)" name="label" placeholder="Help Center" maxLength={200} />
        {error && <Alert>{error}</Alert>}
        <Button type="submit" disabled={pending} className="self-start">
          {pending ? "Adding…" : "Add website"}
        </Button>
      </form>
    </Card>
  );
}

function UploadForm({ onAdded }: { onAdded: () => Promise<void> }) {
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const parsed = uploadSchema.safeParse(formData.get("file"));
    if (!parsed.success) return setError(parsed.error.issues[0].message);
    setError(null);
    startTransition(async () => {
      const result = await uploadDocumentAction(formData);
      if (!result.success) return setError(result.error);
      form.reset();
      await onAdded();
    });
  }

  return (
    <Card>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div>
          <h2 className="font-medium">Upload a document</h2>
          <p className="text-sm text-ink-muted">PDF, Word, text or Markdown, up to 10 MB.</p>
        </div>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          File
          <input
            name="file"
            type="file"
            accept={ALLOWED_UPLOAD_EXTENSIONS.join(",")}
            className="rounded-field bg-surface-3 px-3 py-2.5 text-sm font-normal file:mr-3 file:rounded-full file:border-0 file:bg-secondary-soft file:px-3.5 file:py-1.5 file:text-[13px] file:font-medium file:text-on-secondary-soft"
          />
        </label>
        {error && <Alert>{error}</Alert>}
        <Button type="submit" variant="tonal" disabled={pending} className="self-start">
          {pending ? "Uploading…" : "Upload"}
        </Button>
      </form>
    </Card>
  );
}
