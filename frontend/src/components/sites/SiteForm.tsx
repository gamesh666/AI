"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import type { SiteInput } from "@/lib/api/sites";
import type { Site } from "@/types";

export function SiteForm({
  initial,
  busy,
  onSubmit,
}: {
  initial?: Site | null;
  busy: boolean;
  onSubmit: (v: SiteInput) => void;
}) {
  const [v, setV] = useState<SiteInput>({
    name: initial?.name ?? "",
    code: initial?.code ?? "",
    address: initial?.address ?? "",
    description: initial?.description ?? "",
  });
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(v);
      }}
    >
      <Field label="Name">
        <Input required value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
      </Field>
      <Field label="Site ID" hint="Slug used in stream paths: ai/<site>/<device>/<camera>, e.g. site01">
        <Input required pattern="[A-Za-z0-9][A-Za-z0-9_\-]{1,31}" value={v.code} onChange={(e) => setV({ ...v, code: e.target.value })} />
      </Field>
      <Field label="Address">
        <Input value={v.address ?? ""} onChange={(e) => setV({ ...v, address: e.target.value })} />
      </Field>
      <Field label="Description">
        <Input value={v.description ?? ""} onChange={(e) => setV({ ...v, description: e.target.value })} />
      </Field>
      <Button type="submit" disabled={busy} className="w-full">
        Save
      </Button>
    </form>
  );
}
