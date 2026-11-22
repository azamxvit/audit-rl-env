import { Copy, Download } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import type { EpisodeApi, Opened } from "@/hooks";
import {
  duplicateGroups,
  formatMinor,
  formatTimestamp,
  ID_FIELD,
  TABLE_LABEL,
  type DuplicateGroup,
} from "@/lib";
import type { Rec, TableName } from "@/types";
import {
  Badge,
  Button,
  Card,
  Cost,
  EmptyState,
  SearchBox,
  Mono,
  Muted,
  Page,
  DataTable,
  type Column,
} from "@/ui";

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

export type AddIds = (kind: "affected" | "evidence", ids: string[]) => void;

function DuplicateCandidates({
  groups,
  cols,
  exps,
  selected,
  onOpen,
  onAdd,
}: {
  groups: DuplicateGroup[];
  cols: Column<Rec>[];
  exps: Record<string, number>;
  selected?: string;
  onOpen: (r: Rec) => void;
  onAdd?: AddIds;
}) {
  const hint = (
    <p className="mt-0 mb-1 text-muted">
      Счета одного клиента с той же валютой и суммой среди загруженных. Бесплатно, эталон не используется:
      решение — за аудитором.
    </p>
  );
  if (!groups.length)
    return (
      <EmptyState>
        Среди загруженных счетов нет пар с тем же клиентом, валютой и суммой. Загрузите ещё страницу.
      </EmptyState>
    );
  return (
    <div className="flex flex-col gap-4">
      {hint}
      {groups.map((g) => (
        <Card
          key={g.label}
          level={2}
          title={
            <>
              Группа {g.label} · <Mono>{g.entity}</Mono> · {formatMinor(g.totalMinor, g.currency, exps)} ·{" "}
              {g.rows.length} счёта
            </>
          }
          actions={
            onAdd && (
              <>
                <Button
                  size="sm"
                  onClick={() =>
                    onAdd(
                      "affected",
                      g.rows.map((r) => r.invoice_id),
                    )
                  }
                >
                  invoice_id → affected
                </Button>
                <Button
                  size="sm"
                  onClick={() =>
                    onAdd(
                      "evidence",
                      g.rows.map((r) => r.doc_id),
                    )
                  }
                >
                  doc_id → доказательства
                </Button>
              </>
            )
          }
        >
          <p className="mt-0 mb-3 flex items-center gap-2 text-muted">
            {g.sameLines ? (
              <Badge tone="danger">позиции совпадают</Badge>
            ) : (
              <Badge tone="neutral">позиции различаются</Badge>
            )}
            {g.sameLines
              ? "Те же позиции и период услуг — проверьте проводки обоих счетов."
              : "Скорее законный повтор (например, подписка за другой период)."}
          </p>
          <DataTable
            caption={`Группа ${g.label}: кандидаты в дубли`}
            columns={cols}
            rows={g.rows}
            rowKey={(r) => String(r.invoice_id)}
            selectedKey={selected}
            onRowClick={onOpen}
          />
        </Card>
      ))}
    </div>
  );
}

export function Records({
  table,
  ep,
  selected,
  onSelect,
  onAdd,
}: {
  table: TableName;
  ep: EpisodeApi;
  selected?: string;
  onSelect: (o: Opened) => void;
  onAdd?: AddIds;
}) {
  const [filter, setFilter] = useState("");
  const [dupes, setDupes] = useState(false);
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
  const groups = useMemo(() => (table === "invoices" ? duplicateGroups(t.rows) : []), [table, t.rows]);
  const showDupes = table === "invoices" && dupes;
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
        {table === "invoices" && (
          <Button
            variant={dupes ? "primary" : "secondary"}
            aria-pressed={dupes}
            disabled={!t.rows.length}
            onClick={() => setDupes((v) => !v)}
          >
            <Copy size={14} aria-hidden />
            Кандидаты в дубли · {groups.length}
          </Button>
        )}
        <Button className="ml-auto" disabled={!canLoad || ep.busy} onClick={() => ep.loadMore(table)}>
          <Download size={14} aria-hidden />
          {t.started ? "Загрузить ещё 50" : "Загрузить первые 50"} <Cost />
        </Button>
      </div>
      {!t.rows.length ? (
        <EmptyState>Записи ещё не загружены. Каждая страница — 1 шаг.</EmptyState>
      ) : showDupes ? (
        <DuplicateCandidates
          groups={groups}
          cols={cols}
          exps={exps}
          selected={selected}
          onOpen={open}
          onAdd={onAdd}
        />
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
