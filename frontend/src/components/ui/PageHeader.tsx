/** Section page title (`.vhead h2`, 21px / 600); the dashboard uses the larger Hero instead. */
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="vhead mb-4 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h2>{title}</h2>
        {subtitle && <p className="m-0 mt-0.5 text-[13px] text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
