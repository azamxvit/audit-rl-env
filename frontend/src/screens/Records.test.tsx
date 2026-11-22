import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { EpisodeApi } from "@/hooks";
import { Records } from "@/screens";

const line = { description: "Data migration", quantity: 2, unit_price_minor: 1000, amount_minor: 2000,
  service_period_start: "2025-04-01", service_period_end: "2025-04-30" }; // prettier-ignore
const invoices = [
  { doc_id: "DOC-A1", invoice_id: "INV-A1", entity_id: "CUS-7", issued_at: "2025-04-15T08:00:00+05:00",
    due_at: "2025-05-15T08:00:00+05:00", currency: "KZT", total_minor: 2000, line_items: [line] },
  { doc_id: "DOC-A2", invoice_id: "INV-A2", entity_id: "CUS-7", issued_at: "2025-04-15T12:00:00+05:00",
    due_at: "2025-05-15T12:00:00+05:00", currency: "KZT", total_minor: 2000, line_items: [line] },
  { doc_id: "DOC-Z9", invoice_id: "INV-Z9", entity_id: "CUS-8", issued_at: "2025-04-16T08:00:00+05:00",
    due_at: "2025-05-16T08:00:00+05:00", currency: "KZT", total_minor: 999, line_items: [line] },
]; // prettier-ignore

function fakeEp(rows: unknown[]): EpisodeApi {
  return {
    done: false,
    busy: false,
    loadMore: vi.fn(),
    tables: { invoices: { rows, started: true, next: "c_1" } },
    obs: {
      tables: { invoices: { id_field: "invoice_id", count: 82 } },
      policy: { currency_exponents: { KZT: 2 } },
    },
  } as unknown as EpisodeApi;
}

describe("Records: duplicate candidates", () => {
  it("toggles a free view of same-customer/same-amount groups and adds a whole pair in one click", async () => {
    const user = userEvent.setup();
    const onAdd = vi.fn();
    const ep = fakeEp(invoices);
    render(<Records table="invoices" ep={ep} onSelect={vi.fn()} onAdd={onAdd} />);
    const toggle = screen.getByRole("button", { name: /Кандидаты в дубли · 1/ });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    const group = screen.getByRole("region", { name: /Группа A/ });
    const table = within(group).getByRole("table", { name: "Группа A: кандидаты в дубли" });
    expect(within(table).getAllByRole("row")).toHaveLength(3); // header + 2 invoices
    expect(within(group).getByText("позиции совпадают")).toBeInTheDocument();
    expect(screen.queryByText("INV-Z9")).not.toBeInTheDocument();
    await user.click(within(group).getByRole("button", { name: "invoice_id → affected" }));
    expect(onAdd).toHaveBeenCalledWith("affected", ["INV-A1", "INV-A2"]);
    await user.click(within(group).getByRole("button", { name: "doc_id → доказательства" }));
    expect(onAdd).toHaveBeenCalledWith("evidence", ["DOC-A1", "DOC-A2"]);
    expect(ep.loadMore).not.toHaveBeenCalled(); // free: no step spent
  });

  it("is only offered for invoices and disabled until something is loaded", () => {
    render(<Records table="invoices" ep={fakeEp([])} onSelect={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Кандидаты в дубли · 0/ })).toBeDisabled();
  });
});
