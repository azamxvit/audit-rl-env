import { Download } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import type { EpisodeApi, Opened } from "../hooks/useEpisode";
import { formatMinor, formatTimestamp, ID_FIELD, TABLE_LABEL } from "../lib/format";
import type { Rec, TableName } from "../types";
import { Badge } from "../ui/Badge";
import { Button, Cost } from "../ui/Button";
import { EmptyState } from "../ui/Card";
import { SearchBox } from "../ui/Form";
import { Mono, Muted, Page } from "../ui/Page";
import { DataTable, type Column } from "../ui/Table";

function columns(table: TableName, exps: Record<string, number>, open: (r: Rec) => void): Column<Rec>[] {
  const money = (field: string) => (r: Rec) =>
    r[field] ? formatMinor(r[field], r.currency, exps) : <Muted>—</Muted>;
  const id = (field: string) => (r: Rec) => (r[field] ? <Mono>{r[field]}</Mono> : <Muted>null</Muted>);
  /** First column: a real button so rows are reachable by keyboard. */
  const opener = (field: string) => (r: Rec) => (
    <Button
      variant="link"
      onClick={(e) => {
        e.stopPropagation();
        open(r);
      }}
    >
      {r[field]}
    </Button>
  );
  switch (table) {
    case "ledger":
      return [
        { key: "row_id", header: "row_id", cell: opener("row_id") },
        { key: "ts", header: "Время", cell: (r) => formatTimestamp(r.timestamp) },
        { key: "account", header: "Счёт", cell: (r) => <Badge tone="neutral">{r.account}</Badge> },
        { key: "debit", header: "Дебет", cell: money("debit_minor"), numeric: true },
        { key: "credit", header: "Кредит", cell: money("credit_minor"), numeric: true },
        { key: "entity", header: "entity_id", cell: id("entity_id") },
        { key: "invoice", header: "invoice_id", cell: id("invoice_id") },
        { key: "payment", header: "payment_id", cell: id("payment_id") },
        { key: "entry", header: "entry_id", cell: id("entry_id") },
      ];
    case "invoices":
      return [
        { key: "doc", header: "doc_id", cell: opener("doc_id") },
        { key: "invoice", header: "invoice_id", cell: id("invoice_id") },
        { key: "entity", header: "entity_id", cell: id("entity_id") },
        { key: "issued", header: "Выставлен", cell: (r) => formatTimestamp(r.issued_at) },
        { key: "due", header: "Срок", cell: (r) => formatTimestamp(r.due_at) },
        { key: "total", header: "Сумма", cell: money("total_minor"), numeric: true },
        { key: "lines", header: "Строк", cell: (r) => r.line_items.length, numeric: true },
      ];
    case "payments":
      return [
        { key: "doc", header: "doc_id", cell: opener("doc_id") },
        { key: "payment", header: "payment_id", cell: id("payment_id") },
        {
          key: "kind",
          header: "Вид",
          cell: (r) => <Badge tone={r.kind === "refund" ? "warn" : "neutral"}>{r.kind}</Badge>,
        },
        { key: "ts", header: "Время", cell: (r) => formatTimestamp(r.timestamp) },
        { key: "entity", header: "entity_id", cell: id("entity_id") },
        { key: "amount", header: "Сумма", cell: money("amount_minor"), numeric: true },
        {
          key: "refs",
          header: "Ссылки",
          cell: (r) =>
            r.invoice_refs ? (
              <Mono>{r.invoice_refs.map((x: Rec) => x.invoice_id).join(", ")}</Mono>
            ) : (
              <Muted>null</Muted>
            ),
        },
      ];
    case "fx":
      return [
        { key: "rate_id", header: "rate_id", cell: opener("rate_id") },
        { key: "date", header: "Дата", cell: (r) => r.date },
        { key: "pair", header: "Пара", cell: (r) => `${r.source_currency} → ${r.target_currency}` },
        { key: "rate", header: "Курс", cell: (r) => <Mono>{r.rate}</Mono>, numeric: true },
      ];
  }
}

export function Records({
  table,
  ep,
  selected,
  onSelect,
}: {
  table: TableName;
  ep: EpisodeApi;
  selected?: string;
  onSelect: (o: Opened) => void;
}) {
  const [filter, setFilter] = useState("");
  const t = ep.tables[table];
  const total = ep.obs!.tables[table].count;
  const exps = ep.obs!.policy.currency_exponents;
  const open = useCallback((r: Rec) => onSelect({ table, record: r }), [onSelect, table]);
  const cols = useMemo(() => columns(table, exps, open), [table, exps, open]);
  const rows = useMemo(
    () =>
      filter ? t.rows.filter((r) => JSON.stringify(r).toLowerCase().includes(filter.toLowerCase())) : t.rows,
    [t.rows, filter],
  );
  const canLoad = !ep.done && (!t.started || !!t.next);
  return (
    <Page title={TABLE_LABEL[table]} wide>
      <div className="mb-3.5 flex items-center gap-3">
        <SearchBox
          label="Фильтр по загруженным записям (бесплатно)"
          placeholder="Фильтр по загруженным · бесплатно"
          className="w-80"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <p className="m-0 text-muted" aria-live="polite">
          Загружено {t.rows.length} из {total}
        </p>
        <Button className="ml-auto" disabled={!canLoad || ep.busy} onClick={() => ep.loadMore(table)}>
          <Download size={14} aria-hidden />
          {t.started ? "Загрузить ещё 50" : "Загрузить первые 50"} <Cost />
        </Button>
      </div>
      {!t.rows.length ? (
        <EmptyState>Записи ещё не загружены. Каждая страница — 1 шаг.</EmptyState>
      ) : (
        <DataTable
          caption={`${TABLE_LABEL[table]}: загружено ${t.rows.length} из ${total}`}
          columns={cols}
          rows={rows}
          rowKey={(r) => String(r[ID_FIELD[table]])}
          selectedKey={selected}
          onRowClick={open}
        />
      )}
    </Page>
  );
}
