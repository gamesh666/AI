"use client";

import { ModelsInUse } from "@/components/models/ModelsInUse";
import { PageHeader } from "@/components/ui/PageHeader";
import { useI18n } from "@/lib/i18n/I18nProvider";

/** Models the edges report running (heartbeat), per device and camera. */
export default function ModelsPage() {
  const { t } = useI18n();
  return (
    <>
      <PageHeader title={t("nav.models")} subtitle={t("models.inUseSubtitle")} />
      <ModelsInUse />
    </>
  );
}
