"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Checkbox, Field, Input, Select } from "@/components/ui/Field";
import type { UserInput } from "@/lib/api/users";
import type { Role, User } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

export function UserForm({
  initial,
  busy,
  onSubmit,
}: {
  initial?: User | null;
  busy: boolean;
  onSubmit: (v: UserInput) => void;
}) {
  const { t } = useI18n();
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
      <Field label={t("common.username")}>
        <Input required disabled={!!initial} value={v.username} onChange={(e) => setV({ ...v, username: e.target.value })} />
      </Field>
      <Field label={t("users.fullName")}>
        <Input value={v.full_name ?? ""} onChange={(e) => setV({ ...v, full_name: e.target.value })} />
      </Field>
      <Field label={t("users.email")}>
        <Input type="email" value={v.email ?? ""} onChange={(e) => setV({ ...v, email: e.target.value })} />
      </Field>
      <Field label={t("users.role")} hint={t("users.roleHint")}>
        <Select value={v.role} onChange={(e) => setV({ ...v, role: e.target.value as Role })}>
          <option value="viewer">{t("role.viewer")}</option>
          <option value="operator">{t("role.operator")}</option>
          <option value="admin">{t("role.admin")}</option>
        </Select>
      </Field>
      <Field label={initial ? t("users.newPassword") : t("common.password")} hint={t("users.passwordHint")}>
        <Input
          type="password"
          required={!initial}
          minLength={8}
          value={v.password ?? ""}
          onChange={(e) => setV({ ...v, password: e.target.value })}
          autoComplete="new-password"
        />
      </Field>
      <Checkbox label={t("users.active")} checked={v.is_active} onChange={(e) => setV({ ...v, is_active: e.target.checked })} />
      <Button type="submit" disabled={busy} className="w-full">
        {t("common.save")}
      </Button>
    </form>
  );
}
