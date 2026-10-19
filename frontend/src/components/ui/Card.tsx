import clsx from "clsx";

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={clsx("card p-4", className)}>{children}</div>;
}

/** Card with the AI BOX header row: title (15px/700) + meta on the right. */
export function SectionCard({
  title,
  meta,
  actions,
  className,
  bodyClassName,
  children,
}: {
  title: React.ReactNode;
  meta?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={clsx("card flex flex-col", className)}>
      <div className="card-head">
        <h3 className="truncate">{title}</h3>
        <div className="flex shrink-0 items-center gap-2">
          {meta && <span className="meta">{meta}</span>}
          {actions}
        </div>
      </div>
      <div className={clsx("min-h-0 flex-1 px-4 pb-3", bodyClassName)}>{children}</div>
    </section>
  );
}
