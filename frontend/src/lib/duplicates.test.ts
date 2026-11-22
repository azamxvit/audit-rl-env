import { describe, expect, it } from "vitest";
import { duplicateGroups } from "@/lib";

const line = (period: string) => ({
  description: "Support plan",
  quantity: 1,
  unit_price_minor: 5000,
  amount_minor: 5000,
  service_period_start: `${period}-01`,
  service_period_end: `${period}-28`,
});
const inv = (id: string, entity: string, total: number, issued: string, period = "2025-02") => ({
  doc_id: `DOC-${id}`,
  invoice_id: `INV-${id}`,
  entity_id: entity,
  currency: "KZT",
  total_minor: total,
  issued_at: issued,
  line_items: [line(period)],
});

describe("duplicateGroups", () => {
  it("groups same customer + currency + total, identical lines first, and flags them", () => {
    const groups = duplicateGroups([
      inv("B2", "CUS-1", 5000, "2025-02-03T10:00:00+05:00"),
      inv("X1", "CUS-9", 7000, "2025-02-01T10:00:00+05:00"),
      inv("B1", "CUS-1", 5000, "2025-02-02T10:00:00+05:00"),
      inv("S1", "CUS-2", 5000, "2025-01-01T09:00:00+05:00", "2025-01"),
      inv("S2", "CUS-2", 5000, "2025-02-01T09:00:00+05:00", "2025-02"),
    ]);
    expect(groups.map((g) => [g.label, g.entity, g.rows.map((r) => r.invoice_id), g.sameLines])).toEqual([
      ["A", "CUS-1", ["INV-B1", "INV-B2"], true], // same lines: the strongest candidate comes first
      ["B", "CUS-2", ["INV-S1", "INV-S2"], false], // a subscription: same amount, another service period
    ]);
  });

  it("is empty when nothing repeats", () => {
    expect(
      duplicateGroups([
        inv("A", "CUS-1", 1, "2025-01-01T00:00:00Z"),
        inv("B", "CUS-1", 2, "2025-01-01T00:00:00Z"),
      ]),
    ).toEqual([]);
  });
});
