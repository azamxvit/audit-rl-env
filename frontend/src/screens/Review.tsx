import { CircleCheck, CircleX, FolderOpen, RotateCcw, ShieldCheck } from "lucide-react";
import type { DraftApi, EpisodeApi } from "@/hooks";
import { formatMinor, TYPE_LABEL } from "@/lib";
import type { ReviewIssue } from "@/types";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  AttributeBar,
  Mono,
  Muted,
  Page,
  SectionTitle,
  DataTable,
} from "@/ui";

const TERMINATION: Record<string, string> = {
  submit: "отправка выводов",
  step_limit: "исчерпан бюджет шагов",
  time_limit: "превышено время",
};

export function Review({
  ep,
  draft,
  onAgain,
  onOther,
}: {
  ep: EpisodeApi;
  draft: DraftApi;
  onAgain: () => void;
  onOther: () => void;
}) {
  const r = ep.review;
  if (!r) return <EmptyState>Разбор загружается…</EmptyState>;
  const exps = ep.obs!.policy.currency_exponents;
  const m = r.metrics;
  return (
    <Page title="Разбор эпизода">
      <p className="m-0 mb-[22px] flex items-center gap-2.5">
        <span className="text-[22px] font-bold">
          <data value={m.reward}>{m.reward.toFixed(3)}</data>
          <span className="ml-1 text-sm font-medium text-muted">награда</span>
        </span>
        <Badge tone={m.f1 === 1 ? "success" : m.f1 > 0 ? "warn" : "danger"}>F1 {m.f1.toFixed(3)}</Badge>
        <Badge tone="success">TP {m.tp}</Badge>
        <Badge tone="danger">FP {m.fp}</Badge>
        <Badge tone="warn">FN {m.fn}</Badge>
        {!m.valid && <Badge tone="solid-danger">неверная структура ответа</Badge>}
      </p>
      <AttributeBar
        items={[
          ["Precision", m.precision.toFixed(3)],
          ["Recall", m.recall.toFixed(3)],
          ["Шагов исследования", String(m.inspection_steps)],
          ["Ошибок в эталоне", String(r.issues.length)],
          ["Выводов отправлено", String(draft.findings.length)],
          ["Завершение", TERMINATION[m.termination] ?? m.termination],
        ]}
      />
      <section aria-labelledby="truth-check">
        <SectionTitle id="truth-check">
          <ShieldCheck size={18} aria-hidden /> Проверка по эталону
        </SectionTitle>
        {!r.issues.length ? (
          <Card>Книги чистые: правильный ответ — пустой список выводов.</Card>
        ) : (
          <DataTable<ReviewIssue>
            caption="Ошибки эталона и ваши ответы"
            rows={r.issues}
            rowKey={(i) => `${i.type}:${i.affected_ids.join(",")}`}
            columns={[
              {
                key: "status",
                header: "Статус",
                cell: (i) =>
                  i.status === "found" ? (
                    <Badge tone="success">
                      <CircleCheck size={12} aria-hidden />
                      Найдено
                    </Badge>
                  ) : (
                    <Badge tone="danger">
                      <CircleX size={12} aria-hidden />
                      Пропущено
                    </Badge>
                  ),
              },
              { key: "type", header: "Тип", cell: (i) => TYPE_LABEL[i.type] },
              { key: "affected", header: "Affected", cell: (i) => <Mono>{i.affected_ids.join(", ")}</Mono> },
              {
                key: "expected",
                header: "Ожидалось",
                numeric: true,
                cell: (i) => formatMinor(i.expected_amount_minor, i.currency, exps),
              },
              {
                key: "mine",
                header: "Ваша сумма",
                numeric: true,
                cell: (i) => {
                  const f = i.matched_finding !== null ? draft.findings[i.matched_finding] : undefined;
                  return f ? formatMinor(f.claimed_amount_minor, f.currency, exps) : <Muted>—</Muted>;
                },
              },
              {
                key: "evidence",
                header: "Допустимые доказательства",
                wrap: true,
                cell: (i) => (
                  <Mono>
                    {i.evidence_sets
                      .slice(0, 2)
                      .map((s) => s.join(" + "))
                      .join("  или  ")}
                    {i.evidence_sets.length > 2 && ` (+${i.evidence_sets.length - 2})`}
                  </Mono>
                ),
              },
            ]}
          />
        )}
      </section>
      {r.false_positives.length > 0 && (
        <section aria-labelledby="false-positives">
          <SectionTitle id="false-positives">Ложные срабатывания</SectionTitle>
          <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
            {r.false_positives.map((idx) => {
              const f = draft.findings[idx];
              return (
                f && (
                  <li key={idx} className="rounded-lg border border-line bg-canvas px-3 py-2.5">
                    <p className="m-0 mb-1.5 flex items-center gap-2">
                      <Badge tone="danger">FP</Badge>
                      <span>
                        #{idx + 1} {TYPE_LABEL[f.type]}
                      </span>
                      <span className="ml-auto">{formatMinor(f.claimed_amount_minor, f.currency, exps)}</span>
                    </p>
                    <Mono>{f.affected_ids.join(", ")}</Mono>
                  </li>
                )
              );
            })}
          </ul>
        </section>
      )}
      <p className="mt-6 flex gap-2">
        <Button variant="primary" onClick={onAgain}>
          <RotateCcw size={14} aria-hidden />
          Сыграть ещё раз
        </Button>
        <Button onClick={onOther}>
          <FolderOpen size={14} aria-hidden />
          Другой эпизод
        </Button>
      </p>
    </Page>
  );
}
