import { ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/api";
import { periodLabel } from "@/lib";
import type { EpisodeInfo } from "@/types";
import { Badge, Button, EmptyState, Mono, Page, SectionTitle } from "@/ui";

const SPLITS = [
  { split: "train", title: "Обучающие (train)" },
  { split: "dev", title: "Проверочные (dev)" },
] as const;

export function EpisodePicker({
  onStart,
  notify,
}: {
  onStart: (key: string) => Promise<void>;
  notify: (m: string) => void;
}) {
  const [episodes, setEpisodes] = useState<EpisodeInfo[] | null>(null);
  useEffect(() => {
    api
      .episodes()
      .then(setEpisodes)
      .catch(() => notify("Не удалось загрузить список эпизодов"));
  }, [notify]);
  return (
    <Page
      title="Выберите эпизод"
      lead="Одна вымышленная компания × один отчётный период. Ошибок может не быть вовсе."
    >
      {!episodes ? (
        <EmptyState>Загрузка…</EmptyState>
      ) : (
        SPLITS.map(({ split, title }) => (
          <section key={split} aria-labelledby={`split-${split}`}>
            <SectionTitle id={`split-${split}`}>{title}</SectionTitle>
            <ul className="m-0 grid list-none grid-cols-3 gap-4 p-0">
              {episodes
                .filter((e) => e.split === split)
                .map((e) => (
                  <li key={e.key}>
                    <article
                      aria-labelledby={`ep-${e.key}`}
                      className="flex flex-col gap-2.5 rounded-[10px] border border-line bg-canvas p-[18px] shadow-card"
                    >
                      <p className="m-0 flex items-center gap-2">
                        <Badge tone="neutral">{e.key}</Badge>
                        <Mono className="text-muted">{e.episode_id}</Mono>
                      </p>
                      <h3 id={`ep-${e.key}`} className="m-0 text-sm font-semibold">
                        {e.company_name}
                      </h3>
                      <p className="m-0 text-muted">
                        {periodLabel(e.period_start, e.period_end)} · {e.base_currency} · UTC{e.timezone}
                      </p>
                      <p className="m-0 text-muted">
                        {e.counts.ledger_rows} проводок · {e.counts.documents} документов
                      </p>
                      <Button size="sm" aria-label={`Начать эпизод ${e.key}`} onClick={() => onStart(e.key)}>
                        Начать <ArrowRight size={14} aria-hidden />
                      </Button>
                    </article>
                  </li>
                ))}
            </ul>
          </section>
        ))
      )}
    </Page>
  );
}
