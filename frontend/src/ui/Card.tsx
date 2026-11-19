import { useId, type ReactNode } from "react";
import { cx } from "./cx";

interface CardProps {
  title?: ReactNode;
  icon?: ReactNode;
  /** Heading level for the card title (keeps the document outline correct). */
  level?: 2 | 3;
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}

/** A titled region: renders <section aria-labelledby> with a real heading. */
export function Card({ title, icon, level = 3, actions, className, children }: CardProps) {
  const id = useId();
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <section
      aria-labelledby={title ? id : undefined}
      className={cx("rounded-[10px] border border-line bg-canvas p-[18px] shadow-card", className)}
    >
      {title && (
        <header className="mb-3.5 flex items-center gap-2.5">
          {icon}
          <Heading id={id} className="m-0 text-sm font-semibold">
            {title}
          </Heading>
          {actions && <div className="ml-auto flex items-center gap-1">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="m-0 p-10 text-center text-muted">{children}</p>;
}
