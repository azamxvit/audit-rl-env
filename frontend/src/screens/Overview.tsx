import { ArrowLeft, Copy, Landmark, MessageSquareText, Repeat, Scale } from "lucide-react";
import type { EpisodeApi } from "../hooks/useEpisode";
import type { DraftApi } from "../hooks/useDraft";
import { Badge } from "../components/Badge";
import { KeyValueCard } from "../components/KeyValueCard";
import { FindingForm } from "../components/FindingForm";
import { FindingList } from "../components/FindingList";
import { periodLabel } from "../lib/format";

export function Overview({ ep, draft, notify, onBack }: { ep: EpisodeApi; draft: DraftApi; notify: (m: string) => void; onBack: () => void }) {
  const obs = ep.obs!;
  const m = obs.manifest, p = obs.policy;
  return (
    <div className="page">
      <button className="back" onClick={onBack}><ArrowLeft size={16} />Эпизоды</button>
      <h1>{m.company_name}</h1>
      <div className="headline">
        <span className="headline-big">{periodLabel(m.period_start, m.period_end)}<small>{m.base_currency}</small></span>
        {ep.stepsRemaining < 20 ? <Badge tone="red">осталось {ep.stepsRemaining} шагов</Badge>
                                : <Badge tone="warn">осталось {ep.stepsRemaining} шагов</Badge>}
        <button className="chip" onClick={() => { navigator.clipboard?.writeText(m.episode_id); notify("ID эпизода скопирован"); }}>
          <Copy size={12} />{m.episode_id}
        </button>
      </div>
      <div className="attrs">
        {([["Период", periodLabel(m.period_start, m.period_end)], ["Часовой пояс", `UTC${m.timezone}`],
           ["Функц. валюта", m.base_currency], ["Округление", m.rounding.mode],
           ["Проводок", String(m.counts.ledger_rows)], ["Документов", String(m.counts.documents)]] as const).map(([k, v]) => (
          <div key={k}><div className="attr-label">{k}</div><div className="attr-value">{v}</div></div>
        ))}
      </div>
      <div className="note">
        <div className="note-title"><MessageSquareText size={16} color="var(--accent)" />Задание:</div>
        <div className="note-body">“{obs.task}”</div>
      </div>
      <h2>Сводка политики</h2>
      <div className="cards">
        <KeyValueCard icon={<Landmark size={18} />} title="Признание выручки" rows={[
          ["Период", `${periodLabel(p.period.start, p.period.end)}`], ["Пояс", `UTC${p.period.timezone}`],
          ["Принадлежность", "локальная дата в поясе компании"], ["Проводка", "Dr 1100 / Cr 4000"]]} />
        <KeyValueCard icon={<Repeat size={18} />} title="Курсы FX" rows={[
          ["Дата курса", "дата документа (локальная)"], ["Выходные", "последний рабочий день"],
          ["Округление", `${p.rounding.mode}, один раз`], ["Счёт разниц", "7900"]]} />
        <KeyValueCard icon={<Scale size={18} />} title="Оплаты и 2200" rows={[
          ["Применение", "по invoice_refs"], ["Без ссылок", "→ 2200"], ["Переплата", "→ 2200 (корректно)"],
          ["Возврат", "Dr 2200 / Cr 1000"]]} />
      </div>
      <div className="two-col">
        <FindingList draft={draft} exps={p.currency_exponents} readOnly={ep.done} />
        {!ep.done && <FindingForm draft={draft} />}
      </div>
    </div>
  );
}
