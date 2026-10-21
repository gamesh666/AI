"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Checkbox, Field, Input } from "@/components/ui/Field";
import type { CameraInput } from "@/lib/api/cameras";
import type { Camera } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

/**
 * Cameras come from the edge's own list (PUT /edge/cameras); its source and AI stay on the edge.
 * The platform only names them and switches them on / off.
 */
export function CameraForm({
  initial,
  busy,
  onSubmit,
}: {
  initial: Camera;
  busy: boolean;
  onSubmit: (v: Partial<CameraInput>) => void;
}) {
  const { t } = useI18n();
  const [name, setName] = useState(initial.name);
  const [enabled, setEnabled] = useState(initial.enabled);

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({ name, enabled });
      }}
    >
      <Field label={t("common.name")}>
        <Input required value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <div className="text-xs text-muted">
        {t("cameras.cameraId")}: <code>{initial.code}</code> · {initial.edge_device_name ?? "--"}
      </div>
      <Checkbox label={t("cameras.enabled")} checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
      <Button type="submit" disabled={busy} className="w-full">
        {t("common.save")}
      </Button>
    </form>
  );
}
