import type { ReactNode } from "react";

export function KeyValueCard({ icon, title, rows }: { icon: ReactNode; title: string; rows: [string, ReactNode][] }) {
  return (
    <div className="card">
      <div className="card-title">{icon}{title}</div>
      <dl className="kv">
        {rows.map(([k, v]) => [<dt key={`${k}-k`}>{k}</dt>, <dd key={`${k}-v`}>{v}</dd>])}
      </dl>
    </div>
  );
}
