import { Download, Search } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import type { EpisodeApi, Opened } from "../hooks/useEpisode";
import type { Rec, TableName } from "../types";
import { Badge } from "../components/Badge";
import { ID_FIELD, TABLE_LABEL, formatMinor, formatTimestamp } from "../lib/format";

type Col = { title: string; render: (r: Rec) => ReactNode; num?: boolean };

function columns(table: TableName, exps: Record<string, number>): Col[] {
  const money = (field: string) => (r: Rec) => (r[field] ? formatMinor(r[field], r.currency, exps) : <span className="muted">—</span>);
  const id = (field: string) => (r: Rec) => (r[field] ? <span className="mono">{r[field]}</span> : <span className="muted">null</span>);
  switch (table) {
    case "ledger": return [
      { title: "row_id", render: id("row_id") }, { title: "Время", render: (r) => formatTimestamp(r.timestamp) },
      { title: "Счёт", render: (r) => <Badge tone="neutral">{r.account}</Badge> },
      { title: "Дебет", render: money("debit_minor"), num: true }, { title: "Кредит", render: money("credit_minor"), num: true },
      { title: "entity_id", render: id("entity_id") }, { title: "invoice_id", render: id("invoice_id") },
      { title: "payment_id", render: id("payment_id") }, { title: "entry_id", render: id("entry_id") }];
    case "invoices": return [
      { title: "doc_id", render: id("doc_id") }, { title: "invoice_id", render: id("invoice_id") },
      { title: "entity_id", render: id("entity_id") }, { title: "Выставлен", render: (r) => formatTimestamp(r.issued_at) },
      { title: "Срок", render: (r) => formatTimestamp(r.due_at) }, { title: "Сумма", render: money("total_minor"), num: true },
      { title: "Строк", render: (r) => r.line_items.length, num: true }];
    case "payments": return [
      { title: "doc_id", render: id("doc_id") }, { title: "payment_id", render: id("payment_id") },
      { title: "Вид", render: (r) => <Badge tone={r.kind === "refund" ? "warn" : "neutral"}>{r.kind}</Badge> },
      { title: "Время", render: (r) => formatTimestamp(r.timestamp) }, { title: "entity_id", render: id("entity_id") },
      { title: "Сумма", render: money("amount_minor"), num: true },
      { title: "Ссылки", render: (r) => (r.invoice_refs ? r.invoice_refs.map((x: Rec) => x.invoice_id).join(", ") : <span className="muted">null</span>) }];
    case "fx": return [
      { title: "rate_id", render: id("rate_id") }, { title: "Дата", render: (r) => r.date },
      { title: "Пара", render: (r) => `${r.source_currency} → ${r.target_currency}` },
      { title: "Курс", render: (r) => <span className="mono">{r.rate}</span>, num: true }];
  }
}

export function Records({ table, ep, selected, onSelect }: { table: TableName; ep: EpisodeApi; selected?: string; onSelect: (o: Opened) => void }) {
  const [filter, setFilter] = useState("");
  const t = ep.tables[table];
  const total = ep.obs!.tables[table].count;
  const cols = useMemo(() => columns(table, ep.obs!.policy.currency_exponents), [table, ep.obs]);
  const rows = useMemo(() => (filter ? t.rows.filter((r) => JSON.stringify(r).toLowerCase().includes(filter.toLowerCase())) : t.rows), [t.rows, filter]);
  const canLoad = !ep.done && (!t.started || !!t.next);
  return (
    <div className="page" style={{ maxWidth: "none" }}>
      <h1>{TABLE_LABEL[table]}</h1>
      <div className="toolbar">
        <div className="search" style={{ width: 320 }}>
          <Search size={16} /><input placeholder="Фильтр по загруженным · бесплатно" value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>
        <span className="muted">Загружено {t.rows.length} из {total}</span>
        <button className="btn" style={{ marginLeft: "auto" }} disabled={!canLoad || ep.busy} onClick={() => ep.loadMore(table)}>
          <Download size={14} />{t.started ? "Загрузить ещё 50" : "Загрузить первые 50"} <span className="cost">· 1 шаг</span>
        </button>
      </div>
      <div className="table-wrap">
        {!t.rows.length ? <div className="empty">Записи ещё не загружены. Каждая страница — 1 шаг.</div> : (
          <table>
            <thead><tr>{cols.map((c) => <th key={c.title} className={c.num ? "num" : ""}>{c.title}</th>)}</tr></thead>
            <tbody>
              {rows.map((r) => {
                const id = r[ID_FIELD[table]];
                return (
                  <tr key={id} className={selected === id ? "selected" : ""} onClick={() => onSelect({ table, record: r })}>
                    {cols.map((c) => <td key={c.title} className={c.num ? "num" : ""}>{c.render(r)}</td>)}
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
