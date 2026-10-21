"use client";

import { useState } from "react";

import { errorMessage } from "@/lib/format";

export type MutationResult<T> = { ok: true; value: T } | { ok: false };

/** Wraps an async action with busy/error state. */
export function useMutation() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run<T>(fn: () => Promise<T>): Promise<MutationResult<T>> {
    setBusy(true);
    setError(null);
    try {
      return { ok: true, value: await fn() };
    } catch (e) {
      setError(errorMessage(e));
      return { ok: false };
    } finally {
      setBusy(false);
    }
  }

  return { busy, error, setError, run };
}
