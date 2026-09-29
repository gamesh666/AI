export function ErrorBanner({ error }: { error: string | null | undefined }) {
  if (!error) return null;
  return <div className="mb-4 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>;
}
