"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Checkbox, Field, Input, Select } from "@/components/ui/Field";
import type { CameraInput } from "@/lib/api/cameras";
import type { AIModel, Camera, EdgeDevice } from "@/types";

/**
 * The camera source (RTSP URL, username, password) is WRITE-ONLY: the API never sends it back,
 * because the camera address is an edge-site internal. Leave the fields empty to keep what is stored.
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
    code: initial?.code ?? "",
    name: initial?.name ?? "",
    rtsp_url: "",
    rtsp_username: "",
    rtsp_password: "",
    onvif_url: "",
    enabled: initial?.enabled ?? true,
    ai_enabled: initial?.ai_enabled ?? true,
    ai_model_id: initial?.ai_model_id ?? models[0]?.id ?? "",
    stream_enabled: initial?.stream_enabled ?? true,
    annotated_stream_enabled: initial?.annotated_stream_enabled ?? true,
    original_stream_enabled: initial?.original_stream_enabled ?? false,
    resolution: initial?.resolution ?? "",
    stream_fps: initial?.stream_fps ?? 25,
    inference_fps: initial?.inference_fps ?? 5,
    bitrate: initial?.bitrate ?? "2M",
    gop_size: initial?.gop_size ?? 50,
  });
  const set = <K extends keyof typeof v>(key: K, value: (typeof v)[K]) => setV({ ...v, [key]: value });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const body: Partial<CameraInput> = {
      edge_device_id: v.edge_device_id,
      code: v.code,
      name: v.name,
      enabled: v.enabled,
      ai_enabled: v.ai_enabled,
      ai_model_id: v.ai_model_id || null,
      stream_enabled: v.stream_enabled,
      annotated_stream_enabled: v.annotated_stream_enabled,
      original_stream_enabled: v.original_stream_enabled,
      resolution: v.resolution || null,
      stream_fps: Number(v.stream_fps),
      inference_fps: Number(v.inference_fps),
      bitrate: v.bitrate,
      gop_size: Number(v.gop_size),
    };
    if (v.rtsp_url) body.rtsp_url = v.rtsp_url;
    if (v.rtsp_username) body.rtsp_username = v.rtsp_username;
    if (v.rtsp_password) body.rtsp_password = v.rtsp_password;
    if (v.onvif_url) body.onvif_url = v.onvif_url;
    onSubmit(body);
  };

  const unchanged = initial ? "(unchanged — write-only)" : "";

  return (
    <form className="space-y-3" onSubmit={submit}>
      <div className="grid grid-cols-3 gap-3">
        <div className="col-span-2">
          <Field label="Name">
            <Input required value={v.name} onChange={(e) => set("name", e.target.value)} />
          </Field>
        </div>
        <Field label="Camera ID" hint="e.g. cam01">
          <Input required pattern="[a-z0-9][a-z0-9_\-]{1,31}" value={v.code} onChange={(e) => set("code", e.target.value)} />
        </Field>
      </div>
      <Field label="Edge device" hint="The edge device on the camera's network connects to it; the server never does.">
        <Select required value={v.edge_device_id} onChange={(e) => set("edge_device_id", e.target.value)}>
          {devices.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name} ({d.device_uuid}) · {d.site_name ?? "no site"}
            </option>
          ))}
        </Select>
      </Field>

      <fieldset className="space-y-3 rounded-md border border-slate-700 p-3">
        <legend className="px-1 text-xs uppercase text-slate-400">Source (edge-side, write-only)</legend>
        <Field label="RTSP URL" hint="Credentials in the URL are stripped and stored encrypted. mock://scene?seed=1 for a synthetic camera.">
          <Input
            required={!initial}
            value={v.rtsp_url}
            placeholder={initial ? unchanged : "rtsp://192.168.1.101:554/stream1"}
            onChange={(e) => set("rtsp_url", e.target.value)}
            autoComplete="off"
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Username">
            <Input value={v.rtsp_username} placeholder={unchanged} onChange={(e) => set("rtsp_username", e.target.value)} autoComplete="off" />
          </Field>
          <Field label="Password">
            <Input
              type="password"
              value={v.rtsp_password}
              placeholder={unchanged}
              onChange={(e) => set("rtsp_password", e.target.value)}
              autoComplete="new-password"
            />
          </Field>
        </div>
      </fieldset>

      <fieldset className="space-y-3 rounded-md border border-slate-700 p-3">
        <legend className="px-1 text-xs uppercase text-slate-400">AI</legend>
        <div className="grid grid-cols-2 gap-3">
          <Field label="AI model">
            <Select value={v.ai_model_id} onChange={(e) => set("ai_model_id", e.target.value)}>
              <option value="">— none —</option>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} {m.version}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Inference FPS">
            <Input type="number" min={0.1} max={60} step={0.1} value={v.inference_fps} onChange={(e) => set("inference_fps", Number(e.target.value))} />
          </Field>
        </div>
      </fieldset>

      <fieldset className="space-y-3 rounded-md border border-slate-700 p-3">
        <legend className="px-1 text-xs uppercase text-slate-400">Stream (edge → media server, H.264)</legend>
        <div className="grid grid-cols-4 gap-3">
          <Field label="Resolution" hint="empty = source">
            <Input pattern="\d{2,5}x\d{2,5}" placeholder="1920x1080" value={v.resolution} onChange={(e) => set("resolution", e.target.value)} />
          </Field>
          <Field label="Stream FPS">
            <Input type="number" min={1} max={60} value={v.stream_fps} onChange={(e) => set("stream_fps", Number(e.target.value))} />
          </Field>
          <Field label="Bitrate">
            <Input pattern="\d+(\.\d+)?[kKmM]?" value={v.bitrate} onChange={(e) => set("bitrate", e.target.value)} />
          </Field>
          <Field label="GOP">
            <Input type="number" min={1} max={600} value={v.gop_size} onChange={(e) => set("gop_size", Number(e.target.value))} />
          </Field>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          <Checkbox label="Streaming" checked={v.stream_enabled} onChange={(e) => set("stream_enabled", e.target.checked)} />
          <Checkbox
            label="AI annotated stream"
            checked={v.annotated_stream_enabled}
            onChange={(e) => set("annotated_stream_enabled", e.target.checked)}
          />
          <Checkbox
            label="Original stream (extra RTSP session)"
            checked={v.original_stream_enabled}
            onChange={(e) => set("original_stream_enabled", e.target.checked)}
          />
        </div>
      </fieldset>

      <div className="flex gap-6">
        <Checkbox label="Enabled" checked={v.enabled} onChange={(e) => set("enabled", e.target.checked)} />
        <Checkbox label="AI detection" checked={v.ai_enabled} onChange={(e) => set("ai_enabled", e.target.checked)} />
      </div>
      <Button type="submit" disabled={busy || !v.edge_device_id} className="w-full">
        Save
      </Button>
    </form>
  );
}
