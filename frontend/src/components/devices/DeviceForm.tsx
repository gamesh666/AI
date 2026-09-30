"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import type { DeviceInput } from "@/lib/api/devices";
import type { EdgeDevice, Site } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

export function DeviceForm({
  initial,
  sites,
  busy,
  onSubmit,
}: {
  initial?: EdgeDevice | null;
  sites: Site[];
  busy: boolean;
  onSubmit: (v: DeviceInput) => void;
}) {
  const { t } = useI18n();
  const [v, setV] = useState<DeviceInput>({
    device_uuid: initial?.device_uuid ?? "",
    name: initial?.name ?? "",
    site_id: initial?.site_id ?? "",
  });
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({ ...v, site_id: v.site_id || null });
      }}
    >
      <Field label={t("devices.deviceId")} hint={t("devices.deviceIdHint")}>
        <Input
          required
          disabled={!!initial}
          pattern="[A-Za-z0-9_\-]{3,64}"
          value={v.device_uuid}
          onChange={(e) => setV({ ...v, device_uuid: e.target.value })}
        />
      </Field>
      <Field label={t("common.name")}>
        <Input required value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
      </Field>
      <Field label={t("common.site")}>
        <Select value={v.site_id ?? ""} onChange={(e) => setV({ ...v, site_id: e.target.value })}>
          <option value="">{t("common.none")}</option>
          {sites.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </Select>
      </Field>
      <Button type="submit" disabled={busy} className="w-full">
        {t("common.save")}
      </Button>
    </form>
  );
}
