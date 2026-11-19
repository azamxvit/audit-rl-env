import { FileText, Plus, X } from "lucide-react";
import type { Opened } from "../hooks/useEpisode";
import { ID_FIELD, TABLE_LABEL, formatMinor } from "../lib/format";

const LINK_FIELDS = new Set(["row_id", "entry_id", "invoice_id", "payment_id", "doc_id", "rate_id"]);
const MONEY_FIELDS = new Set(["debit_minor", "credit_minor", "total_minor", "amount_minor", "unit_price_minor"]);

interface Props {
  opened: Opened; exps: Record<string, number>; accounts: Record<string, string>; readOnly: boolean;
  cached: (id: string) => boolean; onOpen: (id: string) => void; onAdd: (kind: "affected" | "evidence", id: string) => void; onClose: () => void;
}

export function RecordDrawer({ opened, exps, accounts, readOnly, cached, onOpen, onAdd, onClose }: Props) {
  const { table, record } = opened;
  const id = record[ID_FIELD[table]] as string;
  const ccy = (record.currency as string) ?? "";
  const value = (k: string, v: unknown) => {
    if (v === null || v === undefined) return <span className="muted">null</span>;
    if (MONEY_FIELDS.has(k) && typeof v === "number") return <span className="mono">{v} <span className="muted">({formatMinor(v, ccy, exps)})</span></span>;
    if (k === "account") return <span>{String(v)} <span className="muted">· {accounts[String(v)] ?? ""}</span></span>;
    if (typeof v === "string" && LINK_FIELDS.has(k) && v !== id && k !== "entry_id")
      return <button className="link" onClick={() => onOpen(v)}>{v}{!cached(v) && <span className="cost"> · 1 шаг</span>}</button>;
    if (typeof v === "object") return <pre className="json">{JSON.stringify(v, null, 2)}</pre>;
    return <span className={typeof v === "string" && v.includes("-") ? "mono" : ""}>{String(v)}</span>;
  };
  return (
    <aside className="drawer">
      <div className="drawer-head">
        <FileText size={18} />
        <div><div className="muted" style={{ fontSize: 12 }}>{TABLE_LABEL[table]}</div><div className="mono" style={{ fontWeight: 600 }}>{id}</div></div>
        <button className="btn ghost small" style={{ marginLeft: "auto" }} onClick={onClose} aria-label="закрыть"><X size={16} /></button>
      </div>
      <div className="drawer-body">
        <dl className="kv">
          {Object.entries(record).map(([k, v]) => [<dt key={`${k}-k`} className="mono">{k}</dt>, <dd key={`${k}-v`}>{value(k, v)}</dd>])}
        </dl>
      </div>
      {!readOnly && (
        <div className="drawer-foot">
          <button className="btn small" onClick={() => onAdd("affected", table === "ledger" || table === "fx" ? id : (record[ID_FIELD[table]] as string))}><Plus size={14} />в affected</button>
          <button className="btn small" onClick={() => onAdd("evidence", (record.doc_id as string) ?? id)}><Plus size={14} />в доказательства</button>
        </div>
      )}
    </aside>
  );
}
