"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Checkbox, Field, Input, Select } from "@/components/ui/Field";
import type { UserInput } from "@/lib/api/users";
import type { Role, User } from "@/types";

export function UserForm({
  initial,
  busy,
  onSubmit,
}: {
  initial?: User | null;
  busy: boolean;
  onSubmit: (v: UserInput) => void;
}) {
  const [v, setV] = useState<UserInput>({
    username: initial?.username ?? "",
    email: initial?.email ?? "",
    full_name: initial?.full_name ?? "",
    role: initial?.role ?? "viewer",
    is_active: initial?.is_active ?? true,
    password: "",
  });

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        const body: UserInput = { ...v, email: v.email || null, full_name: v.full_name || null };
        if (!body.password) delete body.password;
        onSubmit(body);
      }}
    >
      <Field label="Username">
        <Input required disabled={!!initial} value={v.username} onChange={(e) => setV({ ...v, username: e.target.value })} />
      </Field>
      <Field label="Full name">
        <Input value={v.full_name ?? ""} onChange={(e) => setV({ ...v, full_name: e.target.value })} />
      </Field>
      <Field label="Email">
        <Input type="email" value={v.email ?? ""} onChange={(e) => setV({ ...v, email: e.target.value })} />
      </Field>
      <Field label="Role" hint="admin: everything · operator: manage resources · viewer: read-only">
        <Select value={v.role} onChange={(e) => setV({ ...v, role: e.target.value as Role })}>
          <option value="viewer">viewer</option>
          <option value="operator">operator</option>
          <option value="admin">admin</option>
        </Select>
      </Field>
      <Field label={initial ? "New password (optional)" : "Password"} hint="Minimum 8 characters">
        <Input
          type="password"
          required={!initial}
          minLength={8}
          value={v.password ?? ""}
          onChange={(e) => setV({ ...v, password: e.target.value })}
          autoComplete="new-password"
        />
      </Field>
      <Checkbox label="Active" checked={v.is_active} onChange={(e) => setV({ ...v, is_active: e.target.checked })} />
      <Button type="submit" disabled={busy} className="w-full">
        Save
      </Button>
    </form>
  );
}
