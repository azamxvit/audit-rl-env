import type { EpisodeApi } from "@/hooks";
import { Card, DescriptionList, Page } from "@/ui";

function PolicySection({ title, data }: { title: string; data: Record<string, unknown> }) {
  return (
    <Card title={title} level={2} className="mb-4">
      <DescriptionList
        monoKeys
        keyWidth="180px"
        items={Object.entries(data).map(
          ([k, v]) =>
            [
              k,
              <span className="leading-relaxed font-normal">
                {typeof v === "object" ? JSON.stringify(v) : String(v)}
              </span>,
            ] as const,
        )}
      />
    </Card>
  );
}

export function PolicyScreen({ ep }: { ep: EpisodeApi }) {
  const p = ep.obs!.policy;
  return (
    <Page title="Политика учёта" lead="policy.json приходит в первом наблюдении — просмотр бесплатный.">
      <div className="max-w-[900px]">
        <PolicySection title="Период" data={p.period} />
        <PolicySection
          title="Признание выручки"
          data={{ rule: p.revenue_recognition, ledger: p.ledger_currency }}
        />
        <PolicySection title="Курсы FX" data={p.fx} />
        <PolicySection title="Оплаты" data={p.payments} />
        <PolicySection title="Округление" data={p.rounding} />
        <PolicySection title="План счетов" data={p.accounts} />
        <PolicySection title="Разрядность валют" data={p.currency_exponents} />
      </div>
    </Page>
  );
}
