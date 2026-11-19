import { CircleCheck, CircleX, RotateCcw, FolderOpen, ShieldCheck } from "lucide-react";
import type { EpisodeApi } from "../hooks/useEpisode";
import type { DraftApi } from "../hooks/useDraft";
import { Badge } from "../components/Badge";
import { formatMinor, TYPE_LABEL } from "../lib/format";

const TERMINATION: Record<string, string> = { submit: "отправка выводов", step_limit: "исчерпан бюджет шагов", time_limit: "превышено время" };

export function Review({ ep, draft, onAgain, onOther }: { ep: EpisodeApi; draft: DraftApi; onAgain: () => void; onOther: () => void }) {
  const r = ep.review;
  if (!r) return <div className="empty">Разбор загружается…</div>;
  const exps = ep.obs!.policy.currency_exponents;
  const m = r.metrics;
  return (
    <div className="page">
      <h1>Разбор эпизода</h1>
      <div className="headline">
        <span className="headline-big">{m.reward.toFixed(3)}<small>награда</small></span>
        <Badge tone={m.f1 === 1 ? "success" : m.f1 > 0 ? "warn" : "danger"}>F1 {m.f1.toFixed(3)}</Badge>
        <Badge tone="success">TP {m.tp}</Badge><Badge tone="danger">FP {m.fp}</Badge><Badge tone="warn">FN {m.fn}</Badge>
        {!m.valid && <Badge tone="red">неверная структура ответа</Badge>}
      </div>
      <div className="attrs">
        {([["Precision", m.precision.toFixed(3)], ["Recall", m.recall.toFixed(3)], ["Шагов исследования", String(m.inspection_steps)],
           ["Ошибок в эталоне", String(r.issues.length)], ["Выводов отправлено", String(draft.findings.length)],
           ["Завершение", TERMINATION[m.termination] ?? m.termination]] as const).map(([k, v]) => (
          <div key={k}><div className="attr-label">{k}</div><div className="attr-value">{v}</div></div>
        ))}
      </div>
      <h2><ShieldCheck size={18} style={{ verticalAlign: "-3px" }} /> Проверка по эталону</h2>
      {!r.issues.length ? <div className="card">Книги чистые: правильный ответ — пустой список выводов.</div> : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Статус</th><th>Тип</th><th>Affected</th><th className="num">Ожидалось</th><th className="num">Ваша сумма</th><th>Допустимые доказательства</th></tr></thead>
            <tbody>
              {r.issues.map((i, k) => {
                const mine = i.matched_finding !== null ? draft.findings[i.matched_finding] : undefined;
                return (
                  <tr key={k} style={{ cursor: "default" }}>
                    <td>{i.status === "found" ? <Badge tone="success"><CircleCheck size={12} />Найдено</Badge> : <Badge tone="danger"><CircleX size={12} />Пропущено</Badge>}</td>
                    <td>{TYPE_LABEL[i.type]}</td>
                    <td className="mono">{i.affected_ids.join(", ")}</td>
                    <td className="num">{formatMinor(i.expected_amount_minor, i.currency, exps)}</td>
                    <td className="num">{mine ? formatMinor(mine.claimed_amount_minor, mine.currency, exps) : <span className="muted">—</span>}</td>
                    <td className="mono" style={{ whiteSpace: "normal", minWidth: 280 }}>{i.evidence_sets.slice(0, 2).map((s) => s.join(" + ")).join("  или  ")}{i.evidence_sets.length > 2 && ` (+${i.evidence_sets.length - 2})`}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {r.false_positives.length > 0 && (
        <>
          <h2>Ложные срабатывания</h2>
          <div className="list" style={{ maxHeight: "none" }}>
            {r.false_positives.map((idx) => { const f = draft.findings[idx]; return f && (
              <div key={idx} className="list-item">
                <div className="list-item-head"><Badge tone="danger">FP</Badge><span>#{idx + 1} {TYPE_LABEL[f.type]}</span>
                  <span style={{ marginLeft: "auto" }}>{formatMinor(f.claimed_amount_minor, f.currency, exps)}</span></div>
                <div className="mono">{f.affected_ids.join(", ")}</div>
              </div>); })}
          </div>
        </>
      )}
      <div className="row" style={{ marginTop: 24 }}>
        <button className="btn primary" onClick={onAgain}><RotateCcw size={14} />Сыграть ещё раз</button>
        <button className="btn" onClick={onOther}><FolderOpen size={14} />Другой эпизод</button>
      </div>
    </div>
  );
}
