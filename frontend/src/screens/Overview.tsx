import { ArrowLeft, Copy, Landmark, MessageSquareText, Repeat, Scale } from "lucide-react";
import { FindingForm, FindingList } from "@/components";
import type { DraftApi, EpisodeApi } from "@/hooks";
import { periodLabel } from "@/lib";
import { Badge, Button, Card, AttributeBar, DescriptionList, Page, SectionTitle } from "@/ui";

export function Overview({
  ep,
  draft,
  notify,
  onBack,
}: {
  ep: EpisodeApi;
  draft: DraftApi;
  notify: (m: string) => void;
  onBack: () => void;
}) {
  const obs = ep.obs!;
  const m = obs.manifest;
  const p = obs.policy;
  const period = periodLabel(m.period_start, m.period_end);
  return (
    <Page
      title={m.company_name}
      before={
        <nav aria-label="Назад" className="mb-[18px]">
          <Button variant="ghost" size="sm" className="-ml-2.5" onClick={onBack}>
            <ArrowLeft size={16} aria-hidden />
            Эпизоды
          </Button>
        </nav>
      }
    >
      <p className="m-0 mb-[22px] flex items-center gap-2.5">
        <span className="text-[22px] font-bold">
          {period}
          <span className="ml-1 text-sm font-medium text-muted">{m.base_currency}</span>
        </span>
        <Badge tone={ep.stepsRemaining < 20 ? "solid-danger" : "warn"}>
          осталось {ep.stepsRemaining} шагов
        </Badge>
        <button
          type="button"
          title="Скопировать ID эпизода"
          onClick={() => {
            navigator.clipboard?.writeText(m.episode_id);
            notify("ID эпизода скопирован");
          }}
          className="inline-flex h-6 items-center gap-1.5 rounded-md border border-line bg-canvas px-2 font-mono text-xs"
        >
          <Copy size={12} aria-hidden />
          {m.episode_id}
        </button>
      </p>
      <AttributeBar
        items={[
          ["Период", period],
          ["Часовой пояс", `UTC${m.timezone}`],
          ["Функц. валюта", m.base_currency],
          ["Округление", m.rounding.mode],
          ["Проводок", String(m.counts.ledger_rows)],
          ["Документов", String(m.counts.documents)],
        ]}
      />
      <figure className="m-0 max-w-[760px] rounded-md border border-line bg-surface-muted px-3.5 py-3">
        <figcaption className="mb-2 flex items-center gap-2 font-semibold">
          <MessageSquareText size={16} className="text-accent" aria-hidden />
          Задание:
        </figcaption>
        <blockquote className="m-0 border-l-2 border-accent pl-2.5 leading-relaxed text-ink-soft italic">
          “{obs.task}”
        </blockquote>
      </figure>
      <section aria-labelledby="policy-summary">
        <SectionTitle id="policy-summary">Сводка политики</SectionTitle>
        <div className="grid grid-cols-3 gap-4">
          <Card title="Признание выручки" icon={<Landmark size={18} aria-hidden />}>
            <DescriptionList
              items={[
                ["Период", periodLabel(p.period.start, p.period.end)],
                ["Пояс", `UTC${p.period.timezone}`],
                ["Принадлежность", "локальная дата в поясе компании"],
                ["Проводка", "Dr 1100 / Cr 4000"],
              ]}
            />
          </Card>
          <Card title="Курсы FX" icon={<Repeat size={18} aria-hidden />}>
            <DescriptionList
              items={[
                ["Дата курса", "дата документа (локальная)"],
                ["Выходные", "последний рабочий день"],
                ["Округление", `${p.rounding.mode}, один раз`],
                ["Счёт разниц", "7900"],
              ]}
            />
          </Card>
          <Card title="Оплаты и 2200" icon={<Scale size={18} aria-hidden />}>
            <DescriptionList
              items={[
                ["Применение", "по invoice_refs"],
                ["Без ссылок", "→ 2200"],
                ["Переплата", "→ 2200 (корректно)"],
                ["Возврат", "Dr 2200 / Cr 1000"],
              ]}
            />
          </Card>
        </div>
      </section>
      <div className="mt-4 grid grid-cols-2 gap-4">
        <FindingList draft={draft} exps={p.currency_exponents} readOnly={ep.done} />
        {!ep.done && <FindingForm draft={draft} />}
      </div>
    </Page>
  );
}
