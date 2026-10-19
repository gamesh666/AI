"use client";

import clsx from "clsx";
import { useState } from "react";

import { ModelRegistry } from "@/components/models/ModelRegistry";
import { ModelsInUse } from "@/components/models/ModelsInUse";
import { PageHeader } from "@/components/ui/PageHeader";
import { useI18n } from "@/lib/i18n/I18nProvider";

type Tab = "inUse" | "registry";

export default function ModelsPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("inUse");
  return (
    <>
      <PageHeader title={t("nav.models")} subtitle={t("models.inUseSubtitle")} />
      <div className="mb-4 flex gap-1 border-b border-line">
        {(["inUse", "registry"] as const).map((k) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={clsx(
              "-mb-px border-b-2 px-3 py-2 text-sm",
              tab === k ? "border-accent text-accent-hi font-semibold" : "border-transparent text-muted hover:text-ink",
            )}
          >
            {t(k === "inUse" ? "models.tabInUse" : "models.tabRegistry")}
          </button>
        ))}
      </div>
      {tab === "inUse" ? <ModelsInUse /> : <ModelRegistry />}
    </>
  );
}
