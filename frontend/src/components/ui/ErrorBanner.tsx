export function ErrorBanner({ error }: { error: string | null | undefined }) {
  if (!error) return null;
  return <div className="notice mb-4" data-state="bad" role="alert">{error}</div>;
}
