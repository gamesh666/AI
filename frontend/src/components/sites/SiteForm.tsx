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
