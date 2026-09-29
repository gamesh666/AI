"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Checkbox, Field, Input, Select } from "@/components/ui/Field";
import type { CameraInput } from "@/lib/api/cameras";
import type { AIModel, Camera, EdgeDevice } from "@/types";

/**
 * RTSP credentials are write-only: existing values are never sent to the browser.
 * Leaving the password empty on edit keeps the stored one.
 */
export function CameraForm({
  initial,
  devices,
  models,
  busy,
  onSubmit,
}: {
  initial?: Camera | null;
  devices: EdgeDevice[];
  models: AIModel[];
  busy: boolean;
  onSubmit: (v: Partial<CameraInput>) => void;
}) {
  const [v, setV] = useState({
    edge_device_id: initial?.edge_device_id ?? devices[0]?.id ?? "",
    name: initial?.name ?? "",
    rtsp_url: initial?.rtsp_url_masked ?? "rtsp://",
    rtsp_username: "",
    rtsp_password: "",
    onvif_url: initial?.onvif_url ?? "",
    enabled: initial?.enabled ?? true,
    ai_enabled: initial?.ai_enabled ?? true,
    ai_model_id: initial?.ai_model_id ?? models[0]?.id ?? "",
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const body: Partial<CameraInput> = {
      edge_device_id: v.edge_device_id,
      name: v.name,
      onvif_url: v.onvif_url || null,
      enabled: v.enabled,
      ai_enabled: v.ai_enabled,
      ai_model_id: v.ai_model_id || null,
    };
    if (!initial || v.rtsp_url !== initial.rtsp_url_masked) body.rtsp_url = v.rtsp_url;
    if (v.rtsp_username) body.rtsp_username = v.rtsp_username;
    if (v.rtsp_password) body.rtsp_password = v.rtsp_password;
    onSubmit(body);
  };

  return (
    <form className="space-y-3" onSubmit={submit}>
      <Field label="Name">
        <Input required value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
      </Field>
      <Field label="Edge device">
        <Select required value={v.edge_device_id} onChange={(e) => setV({ ...v, edge_device_id: e.target.value })}>
          {devices.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name} ({d.device_uuid})
            </option>
          ))}
        </Select>
      </Field>
      <Field label="RTSP URL" hint="Credentials in the URL are stripped and stored encrypted. mock://testsrc for a synthetic feed.">
        <Input required value={v.rtsp_url} onChange={(e) => setV({ ...v, rtsp_url: e.target.value })} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="RTSP username">
          <Input
            value={v.rtsp_username}
            placeholder={initial?.has_credentials ? "(unchanged)" : ""}
            onChange={(e) => setV({ ...v, rtsp_username: e.target.value })}
            autoComplete="off"
          />
        </Field>
        <Field label="RTSP password">
          <Input
            type="password"
            value={v.rtsp_password}
            placeholder={initial?.has_credentials ? "(unchanged)" : ""}
            onChange={(e) => setV({ ...v, rtsp_password: e.target.value })}
            autoComplete="new-password"
          />
        </Field>
      </div>
      <Field label="ONVIF URL (optional)">
        <Input value={v.onvif_url} onChange={(e) => setV({ ...v, onvif_url: e.target.value })} />
      </Field>
      <Field label="AI model">
        <Select value={v.ai_model_id} onChange={(e) => setV({ ...v, ai_model_id: e.target.value })}>
          <option value="">— none —</option>
          {models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name} {m.version}
            </option>
          ))}
        </Select>
      </Field>
      <div className="flex gap-6">
        <Checkbox label="Enabled" checked={v.enabled} onChange={(e) => setV({ ...v, enabled: e.target.checked })} />
        <Checkbox label="AI detection" checked={v.ai_enabled} onChange={(e) => setV({ ...v, ai_enabled: e.target.checked })} />
      </div>
      <Button type="submit" disabled={busy || !v.edge_device_id} className="w-full">
        Save
      </Button>
    </form>
  );
}
