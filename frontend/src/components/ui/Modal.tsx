"use client";

import { useI18n } from "@/lib/i18n/I18nProvider";

export function Modal({
  title,
  open,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  open: boolean;
  wide?: boolean;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const { t } = useI18n();
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center backdrop p-4" onClick={onClose}>
      <div
        className={`max-h-[90vh] w-full ${wide ? "max-w-3xl" : "max-w-lg"} overflow-y-auto rounded-panel border border-line bg-panel p-5 shadow-card`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="m-0 text-[17px] font-bold text-ink">{title}</h2>
          <button onClick={onClose} className="text-muted hover:text-ink" aria-label={t("common.close")}>
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
