"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import type { AIModelInput } from "@/lib/api/models";
import type { AIModel } from "@/types";

export function ModelForm({
  initial,
  busy,
  onSubmit,
}: {
  initial?: AIModel | null;
  busy: boolean;
  onSubmit: (v: AIModelInput) => void;
}) {
  const [v, setV] = useState({
    name: initial?.name ?? "",
    version: initial?.version ?? "",
    model_type: initial?.model_type ?? "yolov8",
    labels: initial?.labels.join(", ") ?? "person, car",
    model_path: initial?.model_path ?? "models/",
    description: initial?.description ?? "",
  });

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({
          ...v,
          labels: v.labels
            .split(",")
            .map((l) => l.trim())
            .filter(Boolean),
          description: v.description || null,
        });
      }}
    >
      <div className="grid grid-cols-2 gap-3">
        <Field label="Name">
          <Input required value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
        </Field>
        <Field label="Version">
          <Input required value={v.version} onChange={(e) => setV({ ...v, version: e.target.value })} />
        </Field>
      </div>
      <Field label="Model type" hint="yolov8 / yolo11 / onnx / tensorrt">
        <Input required value={v.model_type} onChange={(e) => setV({ ...v, model_type: e.target.value })} />
      </Field>
      <Field label="Model path (on the edge device)">
        <Input required value={v.model_path} onChange={(e) => setV({ ...v, model_path: e.target.value })} />
      </Field>
      <Field label="Labels" hint="Comma separated, index = class_id">
        <Input value={v.labels} onChange={(e) => setV({ ...v, labels: e.target.value })} />
      </Field>
      <Field label="Description">
        <Input value={v.description} onChange={(e) => setV({ ...v, description: e.target.value })} />
      </Field>
      <Button type="submit" disabled={busy} className="w-full">
        Save
      </Button>
    </form>
  );
}
