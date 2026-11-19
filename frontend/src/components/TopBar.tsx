import { Copy, Search } from "lucide-react";
import { useState } from "react";

interface Props {
  enabled: boolean; stepsRemaining: number; maxSteps: number; episodeId?: string;
  onSearch: (id: string) => void; notify: (m: string) => void;
}

function Ring({ value, max }: { value: number; max: number }) {
  const r = 11, c = 2 * Math.PI * r, frac = max ? value / max : 0;
  const color = value < 20 ? "var(--danger)" : "var(--accent)";
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden>
      <circle cx="14" cy="14" r={r} fill="none" stroke="var(--border)" strokeWidth="3" />
      <circle cx="14" cy="14" r={r} fill="none" stroke={color} strokeWidth="3" strokeDasharray={`${c * frac} ${c}`}
              strokeLinecap="round" transform="rotate(-90 14 14)" />
    </svg>
  );
}

export function TopBar({ enabled, stepsRemaining, maxSteps, episodeId, onSearch, notify }: Props) {
  const [q, setQ] = useState("");
  return (
    <header className="topbar">
      <form className="search" onSubmit={(e) => { e.preventDefault(); if (q.trim()) { onSearch(q.trim()); setQ(""); } }}>
        <Search size={16} />
        <input placeholder={enabled ? "Найти запись по ID · 1 шаг" : "Выберите эпизод"} value={q}
               disabled={!enabled} onChange={(e) => setQ(e.target.value)} />
      </form>
      {enabled && episodeId && (
        <div className="topbar-right">
          <div className="budget" title="Оставшийся бюджет шагов">
            <Ring value={stepsRemaining} max={maxSteps} />
            <span>{stepsRemaining}/{maxSteps} шагов</span>
          </div>
          <button className="chip" onClick={() => { navigator.clipboard?.writeText(episodeId); notify("ID эпизода скопирован"); }}>
            <Copy size={12} />{episodeId}
          </button>
        </div>
      )}
    </header>
  );
}
