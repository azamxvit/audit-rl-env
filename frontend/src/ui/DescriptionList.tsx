import type { ReactNode } from "react";
import { cx } from "./cx";

export type Pair = readonly [string, ReactNode];

/** Key/value grid as a real <dl>. */
export function DescriptionList({
  items,
  keyWidth = "130px",
  monoKeys = false,
}: {
  items: readonly Pair[];
  keyWidth?: string;
  monoKeys?: boolean;
}) {
  return (
    <dl
      className="m-0 grid gap-x-3 gap-y-3 text-[13px]"
      style={{ gridTemplateColumns: `${keyWidth} minmax(0, 1fr)` }}
    >
      {items.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className={cx("text-muted", monoKeys && "font-mono text-xs")}>{k}</dt>
          <dd className="m-0 min-w-0 font-medium break-words">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Horizontal attribute strip (label above value), like the NovaPay detail header. */
export function AttributeBar({ items }: { items: readonly Pair[] }) {
  return (
    <dl className="m-0 mb-[18px] grid grid-cols-6 border-y border-line py-4">
      {items.map(([k, v], i) => (
        <div key={k} className={cx(i > 0 && "border-l border-line pl-[18px]")}>
          <dt className="mb-1.5 text-[11px] tracking-wide text-muted uppercase">{k}</dt>
          <dd className="m-0 font-medium">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
