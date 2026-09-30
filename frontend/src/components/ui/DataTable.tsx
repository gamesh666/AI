"use client";

import clsx from "clsx";
import { useI18n } from "@/lib/i18n/I18nProvider";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => React.ReactNode;
  className?: string;
}

export function DataTable<T extends { id: string }>({
  columns,
  rows,
  empty,
  loading = false,
}: {
  columns: Column<T>[];
  rows: T[];
  empty?: string;
  loading?: boolean;
}) {
  const { t } = useI18n();
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-700/60">
      <table className="min-w-full divide-y divide-slate-700/60 text-sm">
        <thead className="bg-surface-700/60">
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className={clsx("px-3 py-2 text-left text-xs font-semibold uppercase text-slate-400", c.className)}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800 bg-surface-800">
          {rows.map((row) => (
            <tr key={row.id} className="hover:bg-surface-700/40">
              {columns.map((c) => (
                <td key={c.key} className={clsx("whitespace-nowrap px-3 py-2 text-slate-200", c.className)}>
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-3 py-8 text-center text-slate-500">
                {loading ? t("common.loading") : (empty ?? t("common.noData"))}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
