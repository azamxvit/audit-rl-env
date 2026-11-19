import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import { api } from "../api";
import type { EpisodeInfo } from "../types";
import { periodLabel } from "../lib/format";
import { Badge } from "../components/Badge";

export function EpisodePicker({ onStart, notify }: { onStart: (key: string) => Promise<void>; notify: (m: string) => void }) {
  const [episodes, setEpisodes] = useState<EpisodeInfo[] | null>(null);
  useEffect(() => { api.episodes().then(setEpisodes).catch(() => notify("Не удалось загрузить список эпизодов")); }, [notify]);
  return (
    <div className="page">
      <h1>Выберите эпизод</h1>
      <p className="muted">Одна вымышленная компания × один отчётный период. Ошибок может не быть вовсе.</p>
      {!episodes ? <div className="empty">Загрузка…</div> : (["train", "dev"] as const).map((split) => (
        <section key={split}>
          <h2>{split === "train" ? "Обучающие (train)" : "Проверочные (dev)"}</h2>
          <div className="episode-grid">
            {episodes.filter((e) => e.split === split).map((e) => (
              <div key={e.key} className="card episode-card">
                <div className="row"><Badge tone="neutral">{e.key}</Badge><span className="mono muted">{e.episode_id}</span></div>
                <div style={{ fontWeight: 600 }}>{e.company_name}</div>
                <div className="muted">{periodLabel(e.period_start, e.period_end)} · {e.base_currency} · UTC{e.timezone}</div>
                <div className="muted">{e.counts.ledger_rows} проводок · {e.counts.documents} документов</div>
                <button className="btn small" onClick={() => onStart(e.key)}>Начать <ArrowRight size={14} /></button>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
