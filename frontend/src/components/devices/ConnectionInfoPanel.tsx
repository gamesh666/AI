"use client";

import clsx from "clsx";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { copyText, downloadText } from "@/lib/clipboard";
import { API_BASE } from "@/lib/config";
import { buildConnectionSheet, type SheetFormat } from "@/lib/connectionSheet";
import { useI18n } from "@/lib/i18n/I18nProvider";
import type { EdgeConnectionInfo } from "@/types";

/**
 * Everything to send to whoever connects the edge. `apiKey` is only known right after the device is
 * created or its key rotated; afterwards the sheet carries a placeholder.
 */
export function ConnectionInfoPanel({
  info,
  apiKey,
  onClose,
}: {
  info: EdgeConnectionInfo;
  apiKey: string | null;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const [format, setFormat] = useState<SheetFormat>("partner");
  const [copied, setCopied] = useState<"all" | "key" | "failed" | null>(null);
  const sheet = useMemo(() => buildConnectionSheet(info, API_BASE, apiKey, format, t), [info, apiKey, format, t]);

  const copy = async (what: "all" | "key", text: string) => {
    setCopied((await copyText(text)) ? what : "failed");
    setTimeout(() => setCopied(null), 2500);
  };

  return (
    <div className="space-y-3 text-sm">
      {apiKey && <p className="text-amber-300">{t("devices.copyNow")}</p>}
      <p className="text-xs text-slate-400">{t("sheet.secretWarning")}</p>

      {apiKey && (
        <div>
          <div className="text-xs uppercase text-slate-400">{t("devices.apiKey")}</div>
          <div className="flex gap-2">
            <code className="block flex-1 break-all rounded bg-surface-900 p-2">{apiKey}</code>
            <Button variant="secondary" onClick={() => copy("key", apiKey)}>
              {copied === "key" ? t("sheet.copied") : t("devices.copyKey")}
            </Button>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between gap-2">
        <div className="text-xs uppercase text-slate-400">{t("sheet.connectionInfo")}</div>
        <div className="inline-flex overflow-hidden rounded-md border border-slate-600 text-xs">
          {(["partner", "agent"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFormat(f)}
              className={clsx(
                "px-2.5 py-1",
                format === f ? "bg-brand-600 text-white" : "bg-surface-800 text-slate-300 hover:bg-surface-700",
              )}
            >
              {t(f === "partner" ? "sheet.formatPartner" : "sheet.formatAgent")}
            </button>
          ))}
        </div>
      </div>
      <textarea
        readOnly
        value={sheet}
        rows={18}
        onFocus={(e) => e.currentTarget.select()}
        className="w-full rounded bg-surface-900 p-2 font-mono text-xs text-slate-200"
      />
      {copied === "failed" && <p className="text-xs text-red-300">{t("sheet.copyFailed")}</p>}
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => copy("all", sheet)}>{copied === "all" ? t("sheet.copied") : t("sheet.copyAll")}</Button>
        <Button variant="secondary" onClick={() => downloadText(`${info.device_id}-aivms.env`, sheet)}>
          {t("sheet.download")}
        </Button>
        <Button variant="ghost" onClick={onClose}>
          {t("devices.done")}
        </Button>
      </div>
    </div>
  );
}
