"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import type { SiteInput } from "@/lib/api/sites";
import type { Site } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

export function SiteForm({
  initial,
  busy,
  onSubmit,
}: {
  initial?: Site | null;
  busy: boolean;
  onSubmit: (v: SiteInput) => void;
}) {
  const { t } = useI18n();
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
      <Field label={t("common.name")}>
        <Input required value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
      </Field>
      <Field label={t("sites.siteId")} hint={t("sites.siteIdHint")}>
        <Input required pattern="[A-Za-z0-9][A-Za-z0-9_\-]{1,31}" value={v.code} onChange={(e) => setV({ ...v, code: e.target.value })} />
      </Field>
      <Field label={t("common.address")}>
        <Input value={v.address ?? ""} onChange={(e) => setV({ ...v, address: e.target.value })} />
      </Field>
      <Field label={t("common.description")}>
        <Input value={v.description ?? ""} onChange={(e) => setV({ ...v, description: e.target.value })} />
      </Field>
      <Button type="submit" disabled={busy} className="w-full">
        {t("common.save")}
      </Button>
    </form>
  );
}
