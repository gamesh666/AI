"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import type { SiteInput } from "@/lib/api/sites";
import type { Owner, Site } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

const PROFILES = ["office", "construction", "factory", "security"] as const;

export function SiteForm({
  initial,
  owners = [],
  busy,
  onSubmit,
}: {
  initial?: Site | null;
  owners?: Owner[];
  busy: boolean;
  onSubmit: (v: SiteInput) => void;
}) {
  const { t } = useI18n();
  const [v, setV] = useState<SiteInput>({
    name: initial?.name ?? "",
    code: initial?.code ?? "",
    address: initial?.address ?? "",
    description: initial?.description ?? "",
    owner_id: initial?.owner_id ?? "",
    profile: initial?.profile ?? "",
    license_code: initial?.license_code ?? "",
    license_until: initial?.license_until ?? "",
    contract_no: initial?.contract_no ?? "",
    term_years: initial?.term_years ?? null,
    transaction_type: initial?.transaction_type ?? "",
  });
  const text = (k: keyof SiteInput) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setV({ ...v, [k]: e.target.value });
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        // empty selections / fields are sent as null ("not set")
        onSubmit({
          ...v,
          owner_id: v.owner_id || null,
          profile: v.profile || null,
          license_code: v.license_code || null,
          license_until: v.license_until || null,
          contract_no: v.contract_no || null,
          transaction_type: v.transaction_type || null,
        });
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

      <fieldset className="space-y-3 rounded-item border border-line p-3">
        <legend className="px-1 text-xs uppercase text-muted">{t("sites.contractLegend")}</legend>
        <p className="text-xs text-muted">{t("sites.contractHint")}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("nav.owners")}>
            <Select value={v.owner_id ?? ""} onChange={text("owner_id")}>
              <option value="">{t("common.none")}</option>
              {owners.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("sites.profile")}>
            <Select value={v.profile ?? ""} onChange={text("profile")}>
              <option value="">{t("common.none")}</option>
              {PROFILES.map((p) => (
                <option key={p} value={p}>
                  {t(`sites.profile.${p}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("sites.licenseCode")}>
            <Input maxLength={128} value={v.license_code ?? ""} onChange={text("license_code")} />
          </Field>
          <Field label={t("sites.licenseUntil")}>
            <Input type="date" value={v.license_until ?? ""} onChange={text("license_until")} />
          </Field>
          <Field label={t("sites.contractNo")}>
            <Input maxLength={128} value={v.contract_no ?? ""} onChange={text("contract_no")} />
          </Field>
          <Field label={t("sites.termYears")}>
            <Input
              type="number"
              min={0}
              max={99}
              value={v.term_years ?? ""}
              onChange={(e) => setV({ ...v, term_years: e.target.value === "" ? null : Number(e.target.value) })}
            />
          </Field>
          <Field label={t("sites.transactionType")}>
            <Select value={v.transaction_type ?? ""} onChange={text("transaction_type")}>
              <option value="">{t("common.none")}</option>
              <option value="buyout">{t("sites.buyout")}</option>
              <option value="lease">{t("sites.lease")}</option>
            </Select>
          </Field>
        </div>
      </fieldset>
      <Button type="submit" disabled={busy} className="w-full">
        {t("common.save")}
      </Button>
    </form>
  );
}
