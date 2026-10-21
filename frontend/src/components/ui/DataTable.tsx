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
    <div className="card overflow-x-auto">
      <table className="min-w-full text-[13px]">
        <thead className="border-b border-line bg-panel2">
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className={clsx("whitespace-nowrap px-3 py-2.5 text-left text-xs font-semibold text-muted", c.className)}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((row) => (
            <tr key={row.id} className="hover:bg-panel2">
              {columns.map((c) => (
                <td key={c.key} className={clsx("whitespace-nowrap px-3 py-2 text-ink", c.className)}>
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-3 py-8 text-center text-muted">
                {loading ? t("common.loading") : (empty ?? t("common.noData"))}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
