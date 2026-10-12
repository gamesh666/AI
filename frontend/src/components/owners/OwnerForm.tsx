"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import type { OwnerInput } from "@/lib/api/owners";
import { useI18n } from "@/lib/i18n/I18nProvider";
import type { Owner } from "@/types";

// same rules as the REACH site_profile contract (§3.6)
const PHONE = "[0-9+()#\\- ]{0,32}";

export function OwnerForm({
  initial,
  busy,
  onSubmit,
}: {
  initial?: Owner | null;
  busy: boolean;
  onSubmit: (v: OwnerInput) => void;
}) {
  const { t } = useI18n();
  const [v, setV] = useState<OwnerInput>({
    name: initial?.name ?? "",
    company_name: initial?.company_name ?? "",
    company_address: initial?.company_address ?? "",
    company_phone: initial?.company_phone ?? "",
    tax_id: initial?.tax_id ?? "",
    contact_name: initial?.contact_name ?? "",
    contact_phone: initial?.contact_phone ?? "",
  });
  const set = (k: keyof OwnerInput) => (e: React.ChangeEvent<HTMLInputElement>) => setV({ ...v, [k]: e.target.value });
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(v);
      }}
    >
      <Field label={t("owners.name")} hint={t("owners.nameHint")}>
        <Input required maxLength={128} value={v.name} onChange={set("name")} />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("owners.companyName")}>
          <Input maxLength={128} value={v.company_name ?? ""} onChange={set("company_name")} />
        </Field>
        <Field label={t("owners.taxId")} hint={t("owners.taxIdHint")}>
          <Input pattern="\d{8}" inputMode="numeric" value={v.tax_id ?? ""} onChange={set("tax_id")} />
        </Field>
      </div>
      <Field label={t("owners.companyAddress")}>
        <Input maxLength={256} value={v.company_address ?? ""} onChange={set("company_address")} />
      </Field>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t("owners.companyPhone")}>
          <Input pattern={PHONE} value={v.company_phone ?? ""} onChange={set("company_phone")} />
        </Field>
        <Field label={t("owners.contactName")}>
          <Input maxLength={128} value={v.contact_name ?? ""} onChange={set("contact_name")} />
        </Field>
        <Field label={t("owners.contactPhone")}>
          <Input pattern={PHONE} value={v.contact_phone ?? ""} onChange={set("contact_phone")} />
        </Field>
      </div>
      <Button type="submit" disabled={busy} className="w-full">
        {t("common.save")}
      </Button>
    </form>
  );
}
