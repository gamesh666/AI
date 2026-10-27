"use client";

import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Field, Input, Select } from "@/components/ui/Field";
import { useAsync } from "@/hooks/useAsync";
import { useMutation } from "@/hooks/useMutation";
import { devicesApi } from "@/lib/api/devices";
import { useI18n } from "@/lib/i18n/I18nProvider";
import type { MessageKey } from "@/lib/i18n/messages";
import type { DeviceReport, EdgeDevice, ReportFilters, ReportPeriod } from "@/types";

// fixed codes of the edge's report filters (docs/edge-integration.md §報表)
const ATTENDANCE = [
  "on_time",
  "late_pending_review",
  "late_confirmed",
  "late_rejected",
  "identity_conflict",
  "not_arrived",
  "normal_departure",
  "early_leave_pending_review",
  "early_leave_confirmed",
  "early_leave_rejected",
  "not_judged",
  "unverifiable",
] as const;
const VLM = ["supported", "not_supported", "undetermined", "model_unavailable", "disabled"] as const;
const REVIEW = ["pending", "confirmed", "rejected", "not_required"] as const;
const FACE = ["matched", "unverified"] as const;
const PERIODS: ReportPeriod[] = ["yesterday", "last_week", "last_month", "last_year", "custom"];

const STATE_TONE = {
  queued: "blue",
  generating: "yellow",
  ready: "green",
  failed: "red",
  expired: "gray",
} as const;
const POLL_MS = 3000;

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Date range of a quick period, in the browser's local time; the edge uses the dates as given. */
function periodRange(p: ReportPeriod, today = new Date()): [string, string] | null {
  const y = today.getFullYear();
  const m = today.getMonth();
  const d = today.getDate();
  switch (p) {
    case "yesterday": {
      // previous working day (Mon–Fri)
      const day = new Date(y, m, d - 1);
      while (day.getDay() === 0 || day.getDay() === 6) day.setDate(day.getDate() - 1);
      return [iso(day), iso(day)];
    }
    case "last_week": {
      const monday = new Date(y, m, d - ((today.getDay() + 6) % 7) - 7);
      return [iso(monday), iso(new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 6))];
    }
    case "last_month":
      return [iso(new Date(y, m - 1, 1)), iso(new Date(y, m, 0))];
    case "last_year":
      return [iso(new Date(y - 1, 0, 1)), iso(new Date(y - 1, 11, 31))];
    default:
      return null;
  }
}

function emptyFilters(): ReportFilters {
  const [start, end] = periodRange("yesterday")!;
  return {
    employee_id: null,
    department: null,
    seat: null,
    period: "yesterday",
    start_date: start,
    end_date: end,
    event: null,
    status: null,
    attendance_status: null,
    vlm: null,
    review: null,
    face: null,
  };
}

/** 產生報表: the edge builds the 出勤事件報表 PDF from its own database and uploads it here. */
export function ReportDialog({ device }: { device: EdgeDevice }) {
  const { t, formatDateTime } = useI18n();
  const options = useAsync(() => devicesApi.reportOptions(device.id), [device.id]);
  const reports = useAsync(() => devicesApi.reports(device.id), [device.id]);
  const m = useMutation();
  const [f, setF] = useState<ReportFilters>(emptyFilters);

  const pending = (reports.data ?? []).some((r) => r.status === "queued" || r.status === "generating");
  useEffect(() => {
    if (!pending) return;
    const id = setInterval(() => reports.reload(), POLL_MS);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending]);

  const o = options.data;
  const employees = useMemo(
    () => (o?.employees ?? []).filter((e) => !f.department || e.department === f.department),
    [o, f.department],
  );

  const set = <K extends keyof ReportFilters>(key: K, value: ReportFilters[K]) =>
    setF((cur) => ({ ...cur, [key]: value }));
  const choose = (key: keyof ReportFilters) => (e: React.ChangeEvent<HTMLSelectElement>) =>
    set(key, (e.target.value || null) as never);
  const pickPeriod = (p: ReportPeriod) => {
    const range = periodRange(p);
    setF((cur) => (range ? { ...cur, period: p, start_date: range[0], end_date: range[1] } : { ...cur, period: p }));
  };
  const setDate = (key: "start_date" | "end_date") => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF((cur) => ({ ...cur, period: "custom", [key]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((await m.run(() => devicesApi.requestReport(device.id, f))).ok) reports.reload();
  };

  const download = async (r: DeviceReport) => {
    const res = await m.run(() => devicesApi.reportDownload(r.id));
    if (!res.ok) return;
    const a = document.createElement("a");
    a.href = res.value.url;
    a.download = res.value.filename;
    a.click();
  };

  const codeSelect = (key: keyof ReportFilters, codes: readonly string[], prefix: string) => (
    <Select value={(f[key] as string | null) ?? ""} onChange={choose(key)}>
      <option value="">{t("common.all")}</option>
      {codes.map((c) => (
        <option key={c} value={c}>
          {t(`${prefix}.${c}` as MessageKey)}
        </option>
      ))}
    </Select>
  );
  const optionSelect = (key: keyof ReportFilters, list: { value: string; label: string }[]) => (
    <Select value={(f[key] as string | null) ?? ""} onChange={choose(key)}>
      <option value="">{t("common.all")}</option>
      {list.map((x) => (
        <option key={x.value} value={x.value}>
          {x.label}
        </option>
      ))}
    </Select>
  );

  return (
    <div className="space-y-4 text-sm">
      <ErrorBanner error={options.error ?? reports.error ?? m.error} />
      <p className="text-xs text-muted">
        {t("reports.hint")}
        {device.status !== "online" && <span className="text-warn"> {t("reports.offline")}</span>}
      </p>
      {o && !o.updated_at && (
        <p className="notice p-2 text-xs" data-state="warn">
          {t("reports.noOptions")}
        </p>
      )}

      <form onSubmit={submit} className="space-y-3 rounded border border-line p-3">
        <div className="text-xs font-semibold text-muted">{t("reports.attendance")}</div>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label={t("reports.employee")}>
            <Select value={f.employee_id ?? ""} onChange={choose("employee_id")}>
              <option value="">{t("common.all")}</option>
              {employees.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name} ({e.id})
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("reports.department")}>{optionSelect("department", o?.departments ?? [])}</Field>
          <Field label={t("reports.seat")}>{optionSelect("seat", o?.seats ?? [])}</Field>
        </div>

        <div className="space-y-1">
          <span className="text-xs font-semibold text-muted">{t("reports.period")}</span>
          <div className="flex flex-wrap gap-1">
            {PERIODS.map((p) => (
              <Button
                key={p}
                type="button"
                variant={f.period === p ? "primary" : "secondary"}
                onClick={() => pickPeriod(p)}
              >
                {t(`reports.period.${p}`)}
              </Button>
            ))}
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label={t("reports.start")}>
            <Input type="date" required value={f.start_date} max={f.end_date} onChange={setDate("start_date")} />
          </Field>
          <Field label={t("reports.end")}>
            <Input type="date" required value={f.end_date} min={f.start_date} onChange={setDate("end_date")} />
          </Field>
          <Field label={t("reports.event")}>{optionSelect("event", o?.events ?? [])}</Field>
          <Field label={t("reports.status")}>{optionSelect("status", o?.statuses ?? [])}</Field>
          <Field label={t("reports.attendanceStatus")}>
            {codeSelect("attendance_status", ATTENDANCE, "reports.att")}
          </Field>
          <Field label={t("reports.vlm")}>{codeSelect("vlm", VLM, "reports.vlmv")}</Field>
          <Field label={t("reports.review")}>{codeSelect("review", REVIEW, "reports.rev")}</Field>
          <Field label={t("reports.face")}>{codeSelect("face", FACE, "reports.facev")}</Field>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={m.busy}>
            {t("reports.generate")}
          </Button>
          <Button type="button" variant="ghost" onClick={() => setF(emptyFilters())}>
            {t("reports.reset")}
          </Button>
        </div>
      </form>

      <div>
        <div className="mb-1 flex items-center justify-between">
          <span className="text-xs font-semibold text-muted">{t("reports.recent")}</span>
          <Button variant="ghost" onClick={() => reports.reload()}>
            {t("tokens.refresh")}
          </Button>
        </div>
        <ul className="divide-y divide-line rounded border border-line">
          {(reports.data ?? []).length === 0 && (
            <li className="px-3 py-4 text-center text-muted">{t("reports.none")}</li>
          )}
          {reports.data?.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <Badge tone={STATE_TONE[r.status]}>{t(`reports.state.${r.status}`)}</Badge>
                  <code className="text-xs">{r.filename}</code>
                </div>
                <div className="text-xs text-muted">
                  {formatDateTime(r.created_at)}
                  {r.size_bytes != null && ` · ${(r.size_bytes / 1024).toFixed(0)} KB`}
                  {r.message && ` · ${r.message}`}
                </div>
              </div>
              {r.status === "ready" && (
                <Button variant="secondary" onClick={() => download(r)}>
                  {t("reports.download")}
                </Button>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
