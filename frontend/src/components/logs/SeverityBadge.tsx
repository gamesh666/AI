"use client";

import { Badge } from "@/components/ui/Badge";
import { useI18n } from "@/lib/i18n/I18nProvider";
import type { LogSeverity } from "@/types";

const TONE = { debug: "gray", info: "blue", warning: "yellow", error: "red", critical: "red" } as const;

export function SeverityBadge({ severity }: { severity: LogSeverity }) {
  const { t } = useI18n();
  return <Badge tone={TONE[severity] ?? "gray"}>{t(`severity.${severity}`)}</Badge>;
}
