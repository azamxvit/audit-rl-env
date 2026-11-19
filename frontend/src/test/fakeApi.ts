import { vi } from "vitest";
import type { EpisodeInfo, Rec, ResetObservation, Review } from "../types";

/** Tiny in-memory stand-in for the backend API, enough to drive the UI in jsdom. */
export const EPISODES: EpisodeInfo[] = [
  {
    key: "dev/00",
    split: "dev",
    episode_id: "EP-TEST0001",
    company_name: "Testa Logistics LLC",
    period_start: "2026-01-01",
    period_end: "2026-03-31",
    base_currency: "USD",
    timezone: "+05:00",
    counts: { ledger_rows: 3, invoices: 1, payments: 1, fx_rates: 0, documents: 2 },
  },
];

const ledger: Rec[] = [
  {
    row_id: "LR-AAAA0001",
    timestamp: "2026-01-10T10:00:00+05:00",
    account: "1000",
    debit_minor: 50000,
    credit_minor: 0,
    currency: "USD",
    entity_id: "CUS-1",
    invoice_id: null,
    payment_id: "PAY-00000001",
    entry_id: "JE-1",
  },
  {
    row_id: "LR-AAAA0002",
    timestamp: "2026-01-10T10:00:00+05:00",
    account: "2200",
    debit_minor: 0,
    credit_minor: 50000,
    currency: "USD",
    entity_id: "CUS-1",
    invoice_id: null,
    payment_id: "PAY-00000001",
    entry_id: "JE-1",
  },
  {
    row_id: "LR-AAAA0003",
    timestamp: "2026-01-05T09:00:00+05:00",
    account: "1100",
    debit_minor: 50000,
    credit_minor: 0,
    currency: "USD",
    entity_id: "CUS-1",
    invoice_id: "INV-00000001",
    payment_id: null,
    entry_id: "JE-2",
  },
];
const invoices: Rec[] = [
  {
    doc_id: "DOC-INV00001",
    invoice_id: "INV-00000001",
    entity_id: "CUS-1",
    issued_at: "2026-01-05T09:00:00+05:00",
    due_at: "2026-02-04T09:00:00+05:00",
    currency: "USD",
    total_minor: 50000,
    line_items: [],
  },
];
const payments: Rec[] = [
  {
    doc_id: "DOC-PAY00001",
    payment_id: "PAY-00000001",
    entity_id: "CUS-1",
    kind: "receipt",
    timestamp: "2026-01-10T10:00:00+05:00",
    currency: "USD",
    amount_minor: 50000,
    invoice_refs: [{ invoice_id: "INV-00000001", amount_minor: 50000 }],
  },
];
const TABLES: Record<string, Rec[]> = { ledger, invoices, payments, fx: [] };
const ID: Record<string, string> = {
  ledger: "row_id",
  invoices: "invoice_id",
  payments: "payment_id",
  fx: "rate_id",
};

export const OBSERVATION: ResetObservation = {
  task: "Audit the books.",
  manifest: {
    schema_version: "1.0",
    env_version: "0.1.0",
    episode_id: "EP-TEST0001",
    company_name: "Testa Logistics LLC",
    base_currency: "USD",
    period_start: "2026-01-01",
    period_end: "2026-03-31",
    timezone: "+05:00",
    counts: EPISODES[0].counts,
    rounding: { mode: "half_even", scope: "once" },
  },
  policy: {
    functional_currency: "USD",
    ledger_currency: "functional",
    period: { start: "2026-01-01", end: "2026-03-31", timezone: "+05:00", membership: "local date" },
    revenue_recognition: "issued_at",
    fx: {
      direction: "1 src = rate dst",
      rate_date: "doc date",
      fallback: "last business day",
      conversion: "round",
    },
    rounding: { mode: "half_even", scope: "once" },
    payments: { application: "refs", carrying_amount: "booked", fx_difference: "7900", refunds: "2200" },
    accounts: { "1000": "Bank", "1100": "AR", "2200": "Unapplied cash" },
    currency_exponents: { USD: 2, JPY: 0 },
  },
  tables: {
    ledger: { id_field: "row_id", count: 3 },
    invoices: { id_field: "invoice_id", count: 1 },
    payments: { id_field: "payment_id", count: 1 },
    fx: { id_field: "rate_id", count: 0 },
  },
  tools: [],
  max_steps: 100,
  steps_remaining: 100,
};

export const REVIEW: Review = {
  metrics: {
    tp: 1,
    fp: 0,
    fn: 0,
    precision: 1,
    recall: 1,
    f1: 1,
    reward: 0.996,
    inspection_steps: 2,
    valid: true,
    termination: "submit",
  },
  issues: [
    {
      type: "payment_allocation",
      affected_ids: ["INV-00000001", "PAY-00000001"],
      expected_amount_minor: 50000,
      currency: "USD",
      evidence_sets: [["DOC-PAY00001", "LR-AAAA0002"]],
      status: "found",
      matched_finding: 0,
    },
  ],
  false_positives: [],
};

function json(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }),
  );
}

export function installFakeApi(pageSize = 2) {
  let steps = 100;
  let done = false;
  const submissions: unknown[] = [];
  const obs = (ok: boolean, result: unknown, error: unknown = null) => ({
    observation: { tool: null, ok, result, error, steps_remaining: steps },
    reward: 0,
    terminated: false,
    truncated: false,
    info: {},
  });
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/episodes") return json(EPISODES);
    if (url === "/api/reset") {
      steps = 100;
      done = false;
      return json({ session: "s1", observation: OBSERVATION });
    }
    if (url.startsWith("/api/review"))
      return done ? json(REVIEW) : json({ error: "episode_not_finished" }, 403);
    if (url === "/api/step") {
      const { action } = JSON.parse(String(init?.body));
      steps -= 1;
      const { tool, args } = action;
      if (tool === "list_records") {
        const rows = TABLES[args.table];
        const offset = args.cursor ? Number(args.cursor.slice(2)) : 0;
        const n = Math.min(args.limit, pageSize);
        const next = offset + n < rows.length ? `c_${offset + n}` : null;
        return json(
          obs(true, { table: args.table, records: rows.slice(offset, offset + n), next_cursor: next }),
        );
      }
      if (tool === "get_record") {
        const rec = TABLES[args.table].find((r) => r[ID[args.table]] === args.id || r.doc_id === args.id);
        return json(
          rec ? obs(true, rec) : obs(false, null, { code: "unknown_id", message: "No record with this id." }),
        );
      }
      if (tool === "get_document") {
        const inv = invoices.find((r) => r.doc_id === args.doc_id);
        const pay = payments.find((r) => r.doc_id === args.doc_id);
        const doc = inv ?? pay;
        return json(
          doc
            ? obs(true, { doc_type: inv ? "invoice" : "payment", document: doc })
            : obs(false, null, { code: "unknown_id", message: "No record with this id." }),
        );
      }
      if (tool === "calculator") {
        return args.expression === "1/0"
          ? json(
              obs(false, null, {
                code: "calculator_error",
                message: "Expression rejected or not computable.",
              }),
            )
          : json(obs(true, { value: "3" }));
      }
      if (tool === "submit") {
        submissions.push(args);
        done = true;
        return json({ ...obs(true, { status: "received" }), terminated: true });
      }
      return json(obs(false, null, { code: "unknown_tool", message: "Unknown tool." }));
    }
    return json({ error: "not_found" }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, submissions, steps: () => steps };
}
