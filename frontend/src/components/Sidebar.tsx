import {
  BookOpen,
  Calculator,
  CircleHelp,
  ClipboardCheck,
  FileSearch,
  FolderOpen,
  House,
  Layers,
} from "lucide-react";
import { useId, type ReactNode } from "react";
import type { View, TableName } from "@/types";
import { TABLE_LABEL } from "@/lib";
import { cx } from "@/ui";

interface Props {
  view: View;
  go: (v: View) => void;
  hasEpisode: boolean;
  done: boolean;
  findings: number;
}

const TABLES: TableName[] = ["ledger", "invoices", "payments", "fx"];

function NavItem({
  current,
  disabled,
  onClick,
  icon,
  count,
  nested,
  children,
}: {
  current: boolean;
  disabled?: boolean;
  onClick: () => void;
  icon?: ReactNode;
  count?: number;
  nested?: boolean;
  children: ReactNode;
}) {
  return (
    <li>
      <button
        type="button"
        aria-current={current ? "page" : undefined}
        disabled={disabled}
        onClick={onClick}
        className={cx(
          "flex w-full items-center gap-2.5 rounded-lg border border-transparent px-2.5 py-[7px] text-left text-ink-soft",
          "hover:enabled:bg-gray-100 disabled:text-subtle",
          nested && "pl-[30px]",
          current && "border-line bg-canvas font-medium text-ink shadow-card hover:enabled:bg-canvas",
        )}
      >
        {icon}
        <span>{children}</span>
        {count !== undefined && <span className="ml-auto text-xs text-muted">{count}</span>}
      </button>
    </li>
  );
}

function NavGroup({ title, children }: { title: string; children: ReactNode }) {
  const id = useId();
  return (
    <section aria-labelledby={id}>
      <h2
        id={id}
        className="m-0 px-2 pt-3.5 pb-1.5 text-[11px] font-semibold tracking-wider text-muted uppercase"
      >
        {title}
      </h2>
      <ul className="m-0 flex list-none flex-col gap-0.5 p-0">{children}</ul>
    </section>
  );
}

export function Sidebar({ view, go, hasEpisode, done, findings }: Props) {
  const off = !hasEpisode;
  const icon = (I: typeof House) => <I size={16} aria-hidden />;
  return (
    <aside
      aria-label="Боковая панель"
      className="overflow-y-auto border-r border-line bg-sidebar px-3.5 py-5"
    >
      <p className="m-0 flex items-center gap-2.5 px-2 pb-5 text-lg font-bold">
        <span
          aria-hidden
          className="grid size-7 place-items-center rounded-full border-[3px] border-accent text-sm text-accent"
        >
          A
        </span>
        AuditDesk
      </p>
      <nav aria-label="Основная навигация">
        <NavGroup title="Расследование">
          <NavItem
            current={view.name === "overview"}
            disabled={off}
            onClick={() => go({ name: "overview" })}
            icon={icon(House)}
          >
            Обзор
          </NavItem>
          <li aria-hidden className="flex items-center gap-2.5 px-2.5 py-[7px] text-ink-soft">
            {icon(Layers)}
            <span>Записи</span>
          </li>
          {TABLES.map((t) => (
            <NavItem
              key={t}
              nested
              current={view.name === "records" && view.table === t}
              disabled={off}
              onClick={() => go({ name: "records", table: t })}
            >
              {TABLE_LABEL[t]}
            </NavItem>
          ))}
          <NavItem
            current={view.name === "findings"}
            disabled={off}
            onClick={() => go({ name: "findings" })}
            icon={icon(ClipboardCheck)}
            count={hasEpisode ? findings : undefined}
          >
            Выводы
          </NavItem>
          {done && (
            <NavItem
              current={view.name === "review"}
              onClick={() => go({ name: "review" })}
              icon={icon(FileSearch)}
            >
              Разбор
            </NavItem>
          )}
        </NavGroup>
        <NavGroup title="Инструменты">
          <NavItem
            current={view.name === "calculator"}
            disabled={off}
            onClick={() => go({ name: "calculator" })}
            icon={icon(Calculator)}
          >
            Калькулятор
          </NavItem>
          <NavItem
            current={view.name === "policy"}
            disabled={off}
            onClick={() => go({ name: "policy" })}
            icon={icon(BookOpen)}
          >
            Политика
          </NavItem>
        </NavGroup>
        <NavGroup title="Эпизоды">
          <NavItem
            current={view.name === "episodes"}
            onClick={() => go({ name: "episodes" })}
            icon={icon(FolderOpen)}
          >
            Сменить эпизод
          </NavItem>
        </NavGroup>
        <NavGroup title="Справка">
          <NavItem
            current={view.name === "help"}
            onClick={() => go({ name: "help" })}
            icon={icon(CircleHelp)}
          >
            Как играть
          </NavItem>
        </NavGroup>
      </nav>
    </aside>
  );
}
