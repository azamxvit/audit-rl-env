import type { ReactNode } from "react";
import { cx } from "./cx";

export interface Column<T> {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  numeric?: boolean;
  wrap?: boolean;
}

/** Semantic data table: <caption> (visually hidden), <th scope="col">, optional row selection. */
export function DataTable<T>({
  caption,
  columns,
  rows,
  rowKey,
  selectedKey,
  onRowClick,
}: {
  caption: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  selectedKey?: string;
  onRowClick?: (row: T) => void;
}) {
  return (
    <div className="overflow-auto rounded-[10px] border border-line bg-canvas">
      <table className="w-full border-collapse text-[13px]">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                className={cx(
                  "sticky top-0 border-b border-line bg-surface-muted px-3 py-2.5 text-[11px] font-semibold tracking-wide text-muted uppercase",
                  c.numeric ? "text-right" : "text-left",
                )}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const key = rowKey(r);
            return (
              <tr
                key={key}
                onClick={onRowClick ? () => onRowClick(r) : undefined}
                className={cx(
                  onRowClick && "cursor-pointer hover:bg-gray-50",
                  selectedKey === key && "bg-accent-soft hover:bg-accent-soft",
                )}
              >
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={cx(
                      "border-b border-line px-3 py-2",
                      c.numeric && "text-right tabular-nums",
                      c.wrap ? "min-w-72 whitespace-normal" : "whitespace-nowrap",
                    )}
                  >
                    {c.cell(r)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
