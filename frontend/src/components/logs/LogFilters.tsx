"use client";

import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { useI18n } from "@/lib/i18n/I18nProvider";
import type { Camera, EdgeDevice, Site } from "@/types";

export interface LogFilterValues {
  start: string; // yyyy-mm-dd (local)
  end: string;
  site_id: string;
  edge_device_id: string;
  camera_id: string;
  event_type: string;
  severity: string;
  q: string;
}

export const EMPTY_LOG_FILTERS: LogFilterValues = {
  start: "",
  end: "",
  site_id: "",
  edge_device_id: "",
  camera_id: "",
  event_type: "",
  severity: "",
  q: "",
};

export const SEVERITIES = ["debug", "info", "warning", "error", "critical"] as const;

export function LogFilters({
  value,
  onChange,
  onReset,
  sites,
  devices,
  cameras,
  types,
}: {
  value: LogFilterValues;
  onChange: (v: LogFilterValues) => void;
  onReset: () => void;
  sites: Site[];
  devices: EdgeDevice[];
  cameras: Camera[];
  types: string[];
}) {
  const { t } = useI18n();
  const set = (key: keyof LogFilterValues) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    onChange({ ...value, [key]: e.target.value });

  const visibleDevices = devices.filter((d) => !value.site_id || d.site_id === value.site_id);
  const visibleCameras = cameras.filter(
    (c) =>
      (!value.site_id || c.site_id === value.site_id) &&
      (!value.edge_device_id || c.edge_device_id === value.edge_device_id),
  );

  return (
    <div className="mb-4 grid grid-cols-2 gap-3 rounded-lg border border-slate-700/60 bg-surface-800 p-4 md:grid-cols-5 xl:grid-cols-9">
      <Field label={t("events.from")}>
        <Input type="date" value={value.start} onChange={set("start")} />
      </Field>
      <Field label={t("events.to")}>
        <Input type="date" value={value.end} onChange={set("end")} />
      </Field>
      <Field label={t("common.site")}>
        <Select value={value.site_id} onChange={set("site_id")}>
          <option value="">{t("common.all")}</option>
          {sites.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </Select>
      </Field>
      <Field label={t("common.edgeDevice")}>
        <Select value={value.edge_device_id} onChange={set("edge_device_id")}>
          <option value="">{t("common.all")}</option>
          {visibleDevices.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </Select>
      </Field>
      <Field label={t("common.camera")}>
        <Select value={value.camera_id} onChange={set("camera_id")}>
          <option value="">{t("common.all")}</option>
          {visibleCameras.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
      </Field>
      <Field label={t("logs.type")}>
        <Select value={value.event_type} onChange={set("event_type")}>
          <option value="">{t("common.all")}</option>
          {types.map((x) => (
            <option key={x} value={x}>
              {x}
            </option>
          ))}
        </Select>
      </Field>
      <Field label={t("logs.severity")}>
        <Select value={value.severity} onChange={set("severity")}>
          <option value="">{t("common.all")}</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {t(`severity.${s}`)}
            </option>
          ))}
        </Select>
      </Field>
      <Field label={t("logs.search")}>
        <Input value={value.q} onChange={set("q")} placeholder={t("logs.searchHint")} />
      </Field>
      <div className="flex items-end">
        <Button variant="secondary" className="w-full" onClick={onReset}>
          {t("events.reset")}
        </Button>
      </div>
    </div>
  );
}
