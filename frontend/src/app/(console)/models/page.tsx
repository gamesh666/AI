"use client";

import { useState } from "react";

import { ModelForm } from "@/components/models/ModelForm";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/DataTable";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAsync } from "@/hooks/useAsync";
import { useMutation } from "@/hooks/useMutation";
import { modelsApi, type AIModelInput } from "@/lib/api/models";
import { useAuth } from "@/lib/auth/AuthContext";
import type { AIModel } from "@/types";

export default function ModelsPage() {
  const { hasRole } = useAuth();
  const canEdit = hasRole("operator");
  const models = useAsync(async () => (await modelsApi.list()).items);
  const m = useMutation();
  const [editing, setEditing] = useState<AIModel | null | "new">(null);

  const save = async (v: AIModelInput) => {
    const res = await m.run(() => (editing === "new" ? modelsApi.create(v) : modelsApi.update((editing as AIModel).id, v)));
    if (res.ok) {
      setEditing(null);
      models.reload();
    }
  };

  const remove = async (model: AIModel) => {
    if (!confirm(`Delete model ${model.name} ${model.version}?`)) return;
    if ((await m.run(() => modelsApi.remove(model.id))).ok) models.reload();
  };

  return (
    <>
      <PageHeader
        title="AI Models"
        subtitle="Models deployed to edge devices (inference always runs on the edge)"
        actions={canEdit && <Button onClick={() => setEditing("new")}>+ Register model</Button>}
      />
      <ErrorBanner error={models.error ?? m.error} />
      <DataTable
        loading={models.loading}
        rows={models.data ?? []}
        columns={[
          { key: "name", header: "Name", render: (x) => <span className="font-medium">{x.name}</span> },
          { key: "version", header: "Version", render: (x) => x.version },
          { key: "type", header: "Type", render: (x) => x.model_type },
          { key: "path", header: "Path", render: (x) => <code className="text-xs">{x.model_path}</code> },
          {
            key: "labels",
            header: "Labels",
            render: (x) => (
              <span className="text-xs text-slate-400" title={x.labels.join(", ")}>
                {x.labels.slice(0, 5).join(", ")}
                {x.labels.length > 5 && ` +${x.labels.length - 5}`}
              </span>
            ),
          },
          {
            key: "actions",
            header: "",
            className: "text-right",
            render: (x) =>
              canEdit && (
                <div className="flex justify-end gap-1">
                  <Button variant="ghost" onClick={() => setEditing(x)}>
                    Edit
                  </Button>
                  <Button variant="ghost" onClick={() => remove(x)}>
                    Delete
                  </Button>
                </div>
              ),
          },
        ]}
      />
      <Modal open={editing !== null} title={editing === "new" ? "Register model" : "Edit model"} onClose={() => setEditing(null)}>
        <ModelForm initial={editing === "new" ? null : editing} busy={m.busy} onSubmit={save} />
      </Modal>
    </>
  );
}
