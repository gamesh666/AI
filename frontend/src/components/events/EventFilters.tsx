"use client";

import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import type { Camera, EdgeDevice, Site } from "@/types";

export interface EventFilterValues {
  start: string; // yyyy-mm-dd (local)
  end: string;
  site_id: string;
  camera_id: string;
  edge_device_id: string;
  class_name: string;
  min_confidence: string; // 0-100
}

export const EMPTY_FILTERS: EventFilterValues = {
  start: "",
  end: "",
  site_id: "",
  camera_id: "",
  edge_device_id: "",
  class_name: "",
  min_confidence: "",
};

export function EventFilters({
  value,
  onChange,
  onReset,
  sites,
  cameras,
  devices,
  classes,
}: {
  value: EventFilterValues;
  onChange: (v: EventFilterValues) => void;
  onReset: () => void;
  sites: Site[];
  cameras: Camera[];
  devices: EdgeDevice[];
  classes: string[];
}) {
  const set = (key: keyof EventFilterValues) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    onChange({ ...value, [key]: e.target.value });

  const visibleCameras = cameras.filter(
    (c) => (!value.site_id || c.site_id === value.site_id) && (!value.edge_device_id || c.edge_device_id === value.edge_device_id),
  );
  const visibleDevices = devices.filter((d) => !value.site_id || d.site_id === value.site_id);

  return (
    <div className="mb-4 grid grid-cols-2 gap-3 rounded-lg border border-slate-700/60 bg-surface-800 p-4 md:grid-cols-4 xl:grid-cols-8">
      <Field label="From">
        <Input type="date" value={value.start} onChange={set("start")} />
      </Field>
      <Field label="To">
        <Input type="date" value={value.end} onChange={set("end")} />
      </Field>
      <Field label="Site">
        <Select value={value.site_id} onChange={set("site_id")}>
          <option value="">All</option>
          {sites.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Edge device">
        <Select value={value.edge_device_id} onChange={set("edge_device_id")}>
          <option value="">All</option>
          {visibleDevices.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Camera">
        <Select value={value.camera_id} onChange={set("camera_id")}>
          <option value="">All</option>
          {visibleCameras.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Class">
        <Select value={value.class_name} onChange={set("class_name")}>
          <option value="">All</option>
          {classes.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Min confidence %">
        <Input type="number" min={0} max={100} value={value.min_confidence} onChange={set("min_confidence")} />
      </Field>
      <div className="flex items-end">
        <Button variant="secondary" className="w-full" onClick={onReset}>
          Reset
        </Button>
      </div>
    </div>
  );
}
