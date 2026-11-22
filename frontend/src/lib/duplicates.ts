import type { Rec } from "@/types";

export interface DuplicateGroup {
  /** "A", "B", ... in order of the earliest issue date */
  label: string;
  entity: string;
  currency: string;
  totalMinor: number;
  /** sorted by issued_at, then invoice_id */
  rows: Rec[];
  /** every invoice in the group has the same line items (incl. service period) */
  sameLines: boolean;
}

const LINE_KEYS = [
  "description",
  "quantity",
  "unit_price_minor",
  "amount_minor",
  "service_period_start",
  "service_period_end",
];

function linesKey(inv: Rec): string {
  const lines = (inv.line_items ?? []) as Rec[];
  return JSON.stringify(
    lines
      .map((li) => LINE_KEYS.map((k) => li[k]))
      .map((x) => JSON.stringify(x))
      .sort(),
  );
}

/**
 * Candidate duplicates among the invoices loaded so far: same customer, currency and total.
 * Groups whose line items are identical come first.
 * Purely a reading aid computed in the browser - it never looks at the answer, costs no step,
 * and legitimate repeats (e.g. monthly subscriptions with another service period) are flagged
 * with sameLines = false so the auditor still has to judge.
 */
export function duplicateGroups(invoices: Rec[]): DuplicateGroup[] {
  const groups = new Map<string, Rec[]>();
  for (const inv of invoices) {
    const key = JSON.stringify([inv.entity_id, inv.currency, inv.total_minor]);
    groups.set(key, [...(groups.get(key) ?? []), inv]);
  }
  const ts = (r: Rec) => new Date(r.issued_at).getTime();
  return (
    [...groups.values()]
      .filter((rows) => rows.length > 1)
      .map((rows) => {
        const sorted = rows
          .slice()
          .sort((a, b) => ts(a) - ts(b) || String(a.invoice_id).localeCompare(b.invoice_id));
        return { rows: sorted, sameLines: new Set(sorted.map(linesKey)).size === 1 };
      })
      // identical line items first (the strongest candidates), then by the earliest issue date
      .sort((a, b) => Number(b.sameLines) - Number(a.sameLines) || ts(a.rows[0]) - ts(b.rows[0]))
      .map(({ rows, sameLines }, i) => ({
        label: String.fromCharCode(65 + (i % 26)) + (i >= 26 ? String(Math.floor(i / 26)) : ""),
        entity: rows[0].entity_id,
        currency: rows[0].currency,
        totalMinor: rows[0].total_minor,
        rows,
        sameLines,
      }))
  );
}
