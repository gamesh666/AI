"use client";

import { useState } from "react";

import { UserForm } from "@/components/users/UserForm";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/DataTable";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAsync } from "@/hooks/useAsync";
import { useMutation } from "@/hooks/useMutation";
import { usersApi, type UserInput } from "@/lib/api/users";
import { useAuth } from "@/lib/auth/AuthContext";
import type { User } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

export default function UsersPage() {
  const { t, tEnum, formatDateTime } = useI18n();
  const { hasRole, user: me } = useAuth();
  const isAdmin = hasRole("admin");
  const users = useAsync(async () => (isAdmin ? (await usersApi.list()).items : []), [isAdmin]);
  const m = useMutation();
  const [editing, setEditing] = useState<User | null | "new">(null);

  if (!isAdmin) {
    return <ErrorBanner error={t("users.adminRequired")} />;
  }

  const save = async (v: UserInput) => {
    const res = await m.run(() =>
      editing === "new"
        ? usersApi.create(v as UserInput & { password: string })
        : usersApi.update((editing as User).id, { ...v, username: undefined }),
    );
    if (res.ok) {
      setEditing(null);
      users.reload();
    }
  };

  const remove = async (u: User) => {
    if (!confirm(t("users.confirmDelete", { name: u.username }))) return;
    if ((await m.run(() => usersApi.remove(u.id))).ok) users.reload();
  };

  return (
    <>
      <PageHeader
        title={t("nav.users")}
        subtitle={t("users.subtitle")}
        actions={<Button onClick={() => setEditing("new")}>{t("users.new")}</Button>}
      />
      <ErrorBanner error={users.error ?? m.error} />
      <DataTable
        loading={users.loading}
        rows={users.data ?? []}
        columns={[
          { key: "username", header: t("common.username"), render: (u) => <span className="font-medium">{u.username}</span> },
          { key: "name", header: t("common.name"), render: (u) => u.full_name ?? "—" },
          { key: "email", header: t("users.email"), render: (u) => u.email ?? "—" },
          {
            key: "role",
            header: t("users.role"),
            render: (u) => <Badge tone={u.role === "admin" ? "red" : u.role === "operator" ? "blue" : "gray"}>{tEnum("role", u.role)}</Badge>,
          },
          { key: "active", header: t("users.active"), render: (u) => (u.is_active ? t("common.yes") : t("common.no")) },
          { key: "created", header: t("common.created"), render: (u) => formatDateTime(u.created_at) },
          {
            key: "actions",
            header: "",
            className: "text-right",
            render: (u) => (
              <div className="flex justify-end gap-1">
                <Button variant="ghost" onClick={() => setEditing(u)}>
                  {t("common.edit")}
                </Button>
                {u.id !== me?.id && (
                  <Button variant="ghost" onClick={() => remove(u)}>
                    {t("common.delete")}
                  </Button>
                )}
              </div>
            ),
          },
        ]}
      />
      <Modal open={editing !== null} title={editing === "new" ? t("users.newTitle") : t("users.editTitle")} onClose={() => setEditing(null)}>
        <UserForm initial={editing === "new" ? null : editing} busy={m.busy} onSubmit={save} />
      </Modal>
    </>
  );
}
