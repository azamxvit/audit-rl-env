import { FileText, Plus, X } from "lucide-react";
import type { Opened } from "../hooks/useEpisode";
import { formatMinor, ID_FIELD, TABLE_LABEL } from "../lib/format";
import { Button, Cost } from "../ui/Button";
import { DescriptionList } from "../ui/DescriptionList";
import { Drawer } from "../ui/Overlay";
import { Mono, Muted } from "../ui/Page";

const LINK_FIELDS = new Set(["row_id", "invoice_id", "payment_id", "doc_id", "rate_id"]);
const MONEY_FIELDS = new Set([
  "debit_minor",
  "credit_minor",
  "total_minor",
  "amount_minor",
  "unit_price_minor",
]);

interface Props {
  opened: Opened;
  exps: Record<string, number>;
  accounts: Record<string, string>;
  readOnly: boolean;
  cached: (id: string) => boolean;
  onOpen: (id: string) => void;
  onAdd: (kind: "affected" | "evidence", id: string) => void;
  onClose: () => void;
}

export function RecordDrawer({ opened, exps, accounts, readOnly, cached, onOpen, onAdd, onClose }: Props) {
  const { table, record } = opened;
  const id = record[ID_FIELD[table]] as string;
  const ccy = (record.currency as string) ?? "";
  const evidenceId = (record.doc_id as string | undefined) ?? id;

  const value = (k: string, v: unknown) => {
    if (v === null || v === undefined) return <Muted>null</Muted>;
    if (MONEY_FIELDS.has(k) && typeof v === "number")
      return (
        <Mono>
          {v} <Muted>({formatMinor(v, ccy, exps)})</Muted>
        </Mono>
      );
    if (k === "account")
      return (
        <span>
          {String(v)} <Muted>· {accounts[String(v)] ?? ""}</Muted>
        </span>
      );
    if (typeof v === "string" && LINK_FIELDS.has(k) && v !== id)
      return (
        <Button variant="link" onClick={() => onOpen(v)}>
          {v}
          {!cached(v) && <Cost />}
        </Button>
      );
    if (typeof v === "object")
      return (
        <pre className="m-0 rounded-lg border border-line bg-surface-muted p-3 font-mono text-xs break-all whitespace-pre-wrap">
          {JSON.stringify(v, null, 2)}
        </pre>
      );
    return (
      <span className={typeof v === "string" && v.includes("-") ? "font-mono text-[12.5px]" : ""}>
        {String(v)}
      </span>
    );
  };

  return (
    <Drawer
      label={`Запись ${id}`}
      header={
        <>
          <FileText size={18} aria-hidden />
          <hgroup className="m-0">
            <p className="m-0 text-xs text-muted">{TABLE_LABEL[table]}</p>
            <h2 className="m-0 font-mono text-sm font-semibold">{id}</h2>
          </hgroup>
          <Button variant="ghost" size="sm" className="ml-auto" aria-label="Закрыть" onClick={onClose}>
            <X size={16} aria-hidden />
          </Button>
        </>
      }
      footer={
        !readOnly && (
          <>
            <Button size="sm" onClick={() => onAdd("affected", id)}>
              <Plus size={14} aria-hidden />в affected
            </Button>
            <Button size="sm" onClick={() => onAdd("evidence", evidenceId)}>
              <Plus size={14} aria-hidden />в доказательства
            </Button>
          </>
        )
      }
    >
      <DescriptionList
        monoKeys
        keyWidth="130px"
        items={Object.entries(record).map(([k, v]) => [k, value(k, v)] as const)}
      />
    </Drawer>
  );
}
