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
import { formatDateTime } from "@/lib/format";
import type { User } from "@/types";

export default function UsersPage() {
  const { hasRole, user: me } = useAuth();
  const isAdmin = hasRole("admin");
  const users = useAsync(async () => (isAdmin ? (await usersApi.list()).items : []), [isAdmin]);
  const m = useMutation();
  const [editing, setEditing] = useState<User | null | "new">(null);

  if (!isAdmin) {
    return <ErrorBanner error="User management requires the admin role." />;
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
    if (!confirm(`Delete user ${u.username}?`)) return;
    if ((await m.run(() => usersApi.remove(u.id))).ok) users.reload();
  };

  return (
    <>
      <PageHeader
        title="Users"
        subtitle="Role-based access control"
        actions={<Button onClick={() => setEditing("new")}>+ New user</Button>}
      />
      <ErrorBanner error={users.error ?? m.error} />
      <DataTable
        loading={users.loading}
        rows={users.data ?? []}
        columns={[
          { key: "username", header: "Username", render: (u) => <span className="font-medium">{u.username}</span> },
          { key: "name", header: "Name", render: (u) => u.full_name ?? "—" },
          { key: "email", header: "Email", render: (u) => u.email ?? "—" },
          {
            key: "role",
            header: "Role",
            render: (u) => <Badge tone={u.role === "admin" ? "red" : u.role === "operator" ? "blue" : "gray"}>{u.role}</Badge>,
          },
          { key: "active", header: "Active", render: (u) => (u.is_active ? "yes" : "no") },
          { key: "created", header: "Created", render: (u) => formatDateTime(u.created_at) },
          {
            key: "actions",
            header: "",
            className: "text-right",
            render: (u) => (
              <div className="flex justify-end gap-1">
                <Button variant="ghost" onClick={() => setEditing(u)}>
                  Edit
                </Button>
                {u.id !== me?.id && (
                  <Button variant="ghost" onClick={() => remove(u)}>
                    Delete
                  </Button>
                )}
              </div>
            ),
          },
        ]}
      />
      <Modal open={editing !== null} title={editing === "new" ? "New user" : "Edit user"} onClose={() => setEditing(null)}>
        <UserForm initial={editing === "new" ? null : editing} busy={m.busy} onSubmit={save} />
      </Modal>
    </>
  );
}
