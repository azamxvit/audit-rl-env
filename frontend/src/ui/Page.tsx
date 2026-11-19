import type { ReactNode } from "react";
import { cx } from "./cx";

/** Page wrapper: <article> with the single <h1> of the view. */
export function Page({
  title,
  lead,
  before,
  wide = false,
  children,
}: {
  title: ReactNode;
  lead?: ReactNode;
  before?: ReactNode;
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <article className={cx(!wide && "max-w-[1120px]")}>
      {before}
      <h1 className="m-0 mb-2.5 text-[22px] font-semibold">{title}</h1>
      {lead && <p className="mt-0 text-muted">{lead}</p>}
      {children}
    </article>
  );
}

export function SectionTitle({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <h2 id={id} className="mt-7 mb-3.5 flex items-center gap-2 text-[17px] font-semibold">
      {children}
    </h2>
  );
}

export function Mono({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cx("font-mono text-[12.5px]", className)}>{children}</span>;
}

export function Muted({ children }: { children: ReactNode }) {
  return <span className="text-muted">{children}</span>;
}
