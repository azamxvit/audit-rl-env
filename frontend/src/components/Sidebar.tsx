import { BookOpen, Calculator, CircleHelp, ClipboardCheck, FolderOpen, House, Layers, ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import type { TableName } from "../types";
import { TABLE_LABEL } from "../lib/format";
import type { View } from "../App";

interface Props { view: View; go: (v: View) => void; hasEpisode: boolean; done: boolean; findings: number }

function Item({ active, disabled, onClick, icon, children, count, sub }:
  { active: boolean; disabled?: boolean; onClick: () => void; icon?: ReactNode; children: ReactNode; count?: number; sub?: boolean }) {
  return (
    <button className={`nav-item${active ? " active" : ""}${sub ? " nav-sub" : ""}`} disabled={disabled} onClick={onClick}>
      {icon}<span>{children}</span>{count !== undefined && <span className="nav-count">{count}</span>}
    </button>
  );
}

const TABLES: TableName[] = ["ledger", "invoices", "payments", "fx"];

export function Sidebar({ view, go, hasEpisode, done, findings }: Props) {
  const off = !hasEpisode;
  return (
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">A</span>AuditDesk</div>
      <div className="nav-section">Расследование</div>
      <Item active={view.name === "overview"} disabled={off} onClick={() => go({ name: "overview" })} icon={<House size={16} />}>Обзор</Item>
      <Item active={false} disabled={off} onClick={() => go({ name: "records", table: "ledger" })} icon={<Layers size={16} />}>
        Записи <ChevronDown size={14} style={{ verticalAlign: "middle" }} />
      </Item>
      {TABLES.map((t) => (
        <Item key={t} sub active={view.name === "records" && view.table === t} disabled={off}
              onClick={() => go({ name: "records", table: t })}>{TABLE_LABEL[t]}</Item>
      ))}
      <Item active={view.name === "findings"} disabled={off} onClick={() => go({ name: "findings" })}
            icon={<ClipboardCheck size={16} />} count={hasEpisode ? findings : undefined}>Выводы</Item>
      {done && <Item active={view.name === "review"} onClick={() => go({ name: "review" })} icon={<ClipboardCheck size={16} />}>Разбор</Item>}
      <div className="nav-section">Инструменты</div>
      <Item active={view.name === "calculator"} disabled={off} onClick={() => go({ name: "calculator" })} icon={<Calculator size={16} />}>Калькулятор</Item>
      <Item active={view.name === "policy"} disabled={off} onClick={() => go({ name: "policy" })} icon={<BookOpen size={16} />}>Политика</Item>
      <div className="nav-section">Эпизоды</div>
      <Item active={view.name === "episodes"} onClick={() => go({ name: "episodes" })} icon={<FolderOpen size={16} />}>Сменить эпизод</Item>
      <div className="nav-section">Справка</div>
      <Item active={view.name === "help"} onClick={() => go({ name: "help" })} icon={<CircleHelp size={16} />}>Как играть</Item>
    </aside>
  );
}
