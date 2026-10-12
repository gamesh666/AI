"use client";

import Link from "next/link";
import { useState } from "react";

import { ConnectionInfoPanel } from "@/components/devices/ConnectionInfoPanel";
import { DeviceForm } from "@/components/devices/DeviceForm";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/DataTable";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAsync } from "@/hooks/useAsync";
import { useLiveDevices } from "@/hooks/useLiveDevices";
import { useMutation } from "@/hooks/useMutation";
import { devicesApi, type DeviceInput } from "@/lib/api/devices";
import { ownersApi } from "@/lib/api/owners";
import { sitesApi } from "@/lib/api/sites";
import type { MessageKey } from "@/lib/i18n/messages";
import { useAuth } from "@/lib/auth/AuthContext";
import { pct } from "@/lib/format";
import type { EdgeConnectionInfo, EdgeDevice } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

const modelText = (m: { name: string; version?: string }) => [m.name, m.version].filter(Boolean).join(" ");

export default function DevicesPage() {
  const { t, formatRelative, formatDateTime } = useI18n();
  const { hasRole } = useAuth();
  const canEdit = hasRole("operator");
  const isAdmin = hasRole("admin");
  const devices = useLiveDevices();
  const sites = useAsync(async () => (await sitesApi.list()).items);
  const owners = useAsync(async () => (isAdmin ? ownersApi.list() : []), [isAdmin]);
  const m = useMutation();
  const [auditOf, setAuditOf] = useState<EdgeDevice | null>(null);
  const audit = useAsync(async () => (auditOf ? devicesApi.audit(auditOf.id) : []), [auditOf?.id]);
  const [editing, setEditing] = useState<EdgeDevice | null | "new">(null);
  // connection info to hand over; apiKey only right after create / rotate (shown once)
  const [revealed, setRevealed] = useState<{ info: EdgeConnectionInfo; apiKey: string | null } | null>(null);

  const save = async (v: DeviceInput) => {
    if (editing === "new") {
      const res = await m.run(() => devicesApi.create(v));
      if (!res.ok) return;
      if (res.value.connection) setRevealed({ info: res.value.connection, apiKey: res.value.api_key });
    } else if (editing) {
      const { device_uuid: _, ...changes } = v;
      const res = await m.run(() => devicesApi.update(editing.id, changes));
      if (!res.ok) return;
    }
    setEditing(null);
    devices.reload();
  };

  const rotate = async (d: EdgeDevice) => {
    if (!confirm(t("devices.confirmRotate", { name: d.name }))) return;
    const res = await m.run(() => devicesApi.rotateKey(d.id));
    if (res.ok && res.value.connection) setRevealed({ info: res.value.connection, apiKey: res.value.api_key });
  };

  const showConnection = async (d: EdgeDevice) => {
    const res = await m.run(() => devicesApi.connection(d.id));
    if (res.ok) setRevealed({ info: res.value, apiKey: null });
  };

  const remove = async (d: EdgeDevice) => {
    if (!confirm(t("devices.confirmDelete", { name: d.name }))) return;
    if ((await m.run(() => devicesApi.remove(d.id))).ok) devices.reload();
  };

  return (
    <>
      <PageHeader
        title={t("nav.devices")}
        subtitle={t("devices.subtitle")}
        actions={canEdit && <Button onClick={() => setEditing("new")}>{t("devices.provision")}</Button>}
      />
      <ErrorBanner error={devices.error ?? m.error} />
      <DataTable
        loading={devices.loading}
        rows={devices.data ?? []}
        columns={[
          {
            key: "name",
            header: t("devices.device"),
            render: (d) => (
              <div>
                <div className="font-medium">{d.name}</div>
                <div className="text-xs text-slate-500">{d.device_uuid}</div>
              </div>
            ),
          },
          { key: "site", header: t("common.site"), render: (d) => d.site_name ?? "—" },
          {
            key: "status",
            header: t("devices.status"),
            render: (d) =>
              d.admin_state !== "active" ? (
                <Badge tone="gray">{t(`devices.state.${d.admin_state}`)}</Badge>
              ) : (
                <StatusBadge status={d.status} />
              ),
          },
          {
            key: "mac",
            header: t("devices.mac"),
            render: (d) => (
              <div className="text-xs">
                <code>{d.mac_address ?? "—"}</code>
                {d.owner_name && <div className="text-slate-500">{d.owner_name}</div>}
              </div>
            ),
          },
          { key: "seen", header: t("devices.lastSeen"), render: (d) => formatRelative(d.last_seen) },
          {
            key: "outages",
            header: t("devices.disconnects24h"),
            render: (d) =>
              d.disconnects_24h ? (
                <Link
                  href={`/logs?edge_device_id=${d.id}&event_type=system.connection`}
                  className="text-red-300 underline-offset-2 hover:underline"
                >
                  {d.disconnects_24h}
                </Link>
              ) : (
                <span className="text-slate-500">0</span>
              ),
          },
          { key: "host", header: t("devices.host"), render: (d) => `${d.hostname ?? "—"} / ${d.ip_address ?? "—"}` },
          { key: "cpu", header: "CPU", render: (d) => pct(d.cpu_usage) },
          { key: "mem", header: t("devices.memory"), render: (d) => pct(d.memory_usage) },
          {
            key: "gpu",
            header: "GPU",
            render: (d) => (d.gpu_name ? `${d.gpu_name} · ${pct(d.gpu_usage)}` : "—"),
          },
          { key: "temp", header: t("devices.temp"), render: (d) => (d.temperature != null ? `${d.temperature.toFixed(0)}°C` : "—") },
          { key: "cams", header: t("common.cameras"), render: (d) => d.camera_count },
          {
            key: "models",
            header: t("nav.models"),
            render: (d) =>
              d.reported_models?.length ? (
                <Link href="/models" className="text-xs hover:underline" title={d.reported_models.map(modelText).join("\n")}>
                  {d.reported_models.map(modelText).join(", ")}
                </Link>
              ) : (
                <span className="text-xs text-slate-500">—</span>
              ),
          },
          { key: "ver", header: t("devices.agent"), render: (d) => d.agent_version ?? "—" },
          {
            key: "actions",
            header: "",
            className: "text-right",
            render: (d) =>
              canEdit && (
                <div className="flex justify-end gap-1">
                  <Button variant="ghost" onClick={() => m.run(() => devicesApi.command(d.id, "reload_config"))}>
                    {t("devices.reload")}
                  </Button>
                  <Button variant="ghost" onClick={() => setEditing(d)}>
                    {t("common.edit")}
                  </Button>
                  {isAdmin && (
                    <Button variant="ghost" onClick={() => setAuditOf(d)}>
                      {t("devices.audit")}
                    </Button>
                  )}
                  {isAdmin && (
                    <Button variant="ghost" onClick={() => showConnection(d)}>
                      {t("sheet.connectionInfo")}
                    </Button>
                  )}
                  {isAdmin && (
                    <Button variant="ghost" onClick={() => rotate(d)}>
                      {t("devices.rotateKey")}
                    </Button>
                  )}
                  <Button variant="ghost" onClick={() => remove(d)}>
                    {t("common.delete")}
                  </Button>
                </div>
              ),
          },
        ]}
      />
      <Modal
        open={editing !== null}
        title={editing === "new" ? t("devices.provisionTitle") : t("devices.editTitle")}
        onClose={() => setEditing(null)}
      >
        <DeviceForm
          initial={editing === "new" ? null : editing}
          sites={sites.data ?? []}
          owners={owners.data ?? []}
          isAdmin={isAdmin}
          busy={m.busy}
          onSubmit={save}
        />
      </Modal>
      <Modal
        open={!!auditOf}
        wide
        title={auditOf ? t("devices.auditTitle", { name: auditOf.name }) : ""}
        onClose={() => setAuditOf(null)}
      >
        <ul className="max-h-[60vh] divide-y divide-slate-800 overflow-y-auto text-sm">
          {(audit.data ?? []).length === 0 && <li className="py-6 text-center text-slate-500">{t("common.noData")}</li>}
          {audit.data?.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span>
                <Badge tone={a.action.startsWith("rejected") ? "red" : a.action === "registered" ? "green" : "blue"}>
                  {t(`audit.${a.action}` as MessageKey) || a.action}
                </Badge>
                <span className="ml-2 text-xs text-slate-500">
                  {[a.source_ip, a.token_prefix && `${a.token_prefix}…`, a.mac_address].filter(Boolean).join(" · ")}
                </span>
              </span>
              <span className="text-xs text-slate-400">{formatDateTime(a.created_at)}</span>
            </li>
          ))}
        </ul>
      </Modal>
      <Modal
        open={!!revealed}
        wide
        title={revealed ? `${t("devices.credentialsTitle")} · ${revealed.info.device_id}` : ""}
        onClose={() => setRevealed(null)}
      >
        {revealed && (
          <ConnectionInfoPanel info={revealed.info} apiKey={revealed.apiKey} onClose={() => setRevealed(null)} />
        )}
      </Modal>
    </>
  );
}
