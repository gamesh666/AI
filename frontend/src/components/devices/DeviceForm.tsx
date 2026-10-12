"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import type { DeviceInput } from "@/lib/api/devices";
import type { AdminState, EdgeDevice, Owner, Site } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

export function DeviceForm({
  initial,
  sites,
  owners = [],
  isAdmin = false,
  busy,
  onSubmit,
}: {
  initial?: EdgeDevice | null;
  sites: Site[];
  owners?: Owner[];
  isAdmin?: boolean;
  busy: boolean;
  onSubmit: (v: DeviceInput) => void;
}) {
  const { t } = useI18n();
  const [v, setV] = useState<DeviceInput>({
    device_uuid: initial?.device_uuid ?? "",
    name: initial?.name ?? "",
    site_id: initial?.site_id ?? "",
    mac_address: initial?.mac_address ?? "",
    owner_id: initial?.owner_id ?? "",
    admin_state: initial?.admin_state ?? "active",
  });
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        const body: DeviceInput = { device_uuid: v.device_uuid, name: v.name, site_id: v.site_id || null };
        if (isAdmin) {
          body.mac_address = v.mac_address || (initial?.mac_address ? "" : null);
          body.owner_id = v.owner_id || null;
          if (initial) body.admin_state = v.admin_state;
        }
        onSubmit(body);
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
      {isAdmin && (
        <fieldset className="space-y-3 rounded-md border border-slate-700 p-3">
          <legend className="px-1 text-xs uppercase text-slate-400">{t("devices.provisioningLegend")}</legend>
          <Field label={t("devices.mac")} hint={t("devices.macHint")}>
            <Input
              value={v.mac_address ?? ""}
              placeholder="aa:bb:cc:dd:ee:ff"
              pattern="([0-9A-Fa-f]{2}[:\-.]?){5}[0-9A-Fa-f]{2}"
              onChange={(e) => setV({ ...v, mac_address: e.target.value })}
            />
          </Field>
          <Field label={t("nav.owners")}>
            <Select value={v.owner_id ?? ""} onChange={(e) => setV({ ...v, owner_id: e.target.value })}>
              <option value="">{t("common.none")}</option>
              {owners.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </Select>
          </Field>
          {initial && (
            <Field label={t("devices.adminState")} hint={t("devices.adminStateHint")}>
              <Select value={v.admin_state} onChange={(e) => setV({ ...v, admin_state: e.target.value as AdminState })}>
                {(["active", "disabled", "retired"] as const).map((s) => (
                  <option key={s} value={s}>
                    {t(`devices.state.${s}`)}
                  </option>
                ))}
              </Select>
            </Field>
          )}
        </fieldset>
      )}
      <Button type="submit" disabled={busy} className="w-full">
        {t("common.save")}
      </Button>
    </form>
  );
}
