"use client";

import { Button } from "@/components/ui/Button";
import type { EdgeDeviceWithKey } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

/** The device key is returned exactly once by the API; it is never retrievable again. */
export function ApiKeyReveal({ device, onClose }: { device: EdgeDeviceWithKey; onClose: () => void }) {
  const { t } = useI18n();
  return (
    <div className="space-y-3 text-sm">
      <p className="text-amber-300">{t("devices.copyNow")}</p>
      <div>
        <div className="text-xs uppercase text-slate-400">{t("devices.deviceId")}</div>
        <code className="block rounded bg-surface-900 p-2">{device.device_uuid}</code>
      </div>
      <div>
        <div className="text-xs uppercase text-slate-400">{t("devices.apiKey")}</div>
        <code className="block break-all rounded bg-surface-900 p-2">{device.api_key}</code>
      </div>
      <div className="flex gap-2">
        <Button variant="secondary" onClick={() => navigator.clipboard?.writeText(device.api_key)}>
          {t("devices.copyKey")}
        </Button>
        <Button onClick={onClose}>{t("devices.done")}</Button>
      </div>
    </div>
  );
}
