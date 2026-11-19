import { Copy } from "lucide-react";
import { useState } from "react";
import { SearchBox } from "@/ui";

interface Props {
  enabled: boolean;
  stepsRemaining: number;
  maxSteps: number;
  episodeId?: string;
  onSearch: (id: string) => void;
  notify: (m: string) => void;
}

function BudgetRing({ value, max }: { value: number; max: number }) {
  const r = 11;
  const c = 2 * Math.PI * r;
  const frac = max ? value / max : 0;
  const stroke = value < 20 ? "var(--color-danger)" : "var(--color-accent)";
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden>
      <circle cx="14" cy="14" r={r} fill="none" stroke="var(--color-line)" strokeWidth="3" />
      <circle
        cx="14"
        cy="14"
        r={r}
        fill="none"
        stroke={stroke}
        strokeWidth="3"
        strokeDasharray={`${c * frac} ${c}`}
        strokeLinecap="round"
        transform="rotate(-90 14 14)"
      />
    </svg>
  );
}

export function TopBar({ enabled, stepsRemaining, maxSteps, episodeId, onSearch, notify }: Props) {
  const [q, setQ] = useState("");
  return (
    <header className="flex h-16 flex-none items-center gap-4 border-b border-line px-8">
      <form
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) {
            onSearch(q.trim());
            setQ("");
          }
        }}
      >
        <SearchBox
          label="Найти запись по ID (1 шаг)"
          className="w-[380px]"
          placeholder={enabled ? "Найти запись по ID · 1 шаг" : "Выберите эпизод"}
          value={q}
          disabled={!enabled}
          onChange={(e) => setQ(e.target.value)}
        />
      </form>
      {enabled && episodeId && (
        <div className="ml-auto flex items-center gap-3.5">
          <p className="m-0 flex items-center gap-2 font-medium">
            <BudgetRing value={stepsRemaining} max={maxSteps} />
            <meter
              className="sr-only"
              min={0}
              max={maxSteps}
              value={stepsRemaining}
              aria-label="Бюджет шагов"
            />
            <span>
              {stepsRemaining}/{maxSteps} шагов
            </span>
          </p>
          <button
            type="button"
            title="Скопировать ID эпизода"
            onClick={() => {
              navigator.clipboard?.writeText(episodeId);
              notify("ID эпизода скопирован");
            }}
            className="inline-flex h-6 items-center gap-1.5 rounded-md border border-line bg-canvas px-2 font-mono text-xs"
          >
            <Copy size={12} aria-hidden />
            {episodeId}
          </button>
        </div>
      )}
    </header>
  );
}
