import type { EpisodeApi } from "../hooks/useEpisode";

function Section({ title, data }: { title: string; data: Record<string, unknown> }) {
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-title">{title}</div>
      <dl className="kv" style={{ gridTemplateColumns: "180px 1fr" }}>
        {Object.entries(data).map(([k, v]) => [<dt key={`${k}-k`} className="mono">{k}</dt>,
          <dd key={`${k}-v`} style={{ fontWeight: 400, lineHeight: 1.5 }}>{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>])}
      </dl>
    </div>
  );
}

export function PolicyScreen({ ep }: { ep: EpisodeApi }) {
  const p = ep.obs!.policy;
  return (
    <div className="page" style={{ maxWidth: 900 }}>
      <h1>Политика учёта</h1>
      <p className="muted">policy.json приходит в первом наблюдении — просмотр бесплатный.</p>
      <Section title="Период" data={p.period} />
      <Section title="Признание выручки" data={{ rule: p.revenue_recognition, ledger: p.ledger_currency }} />
      <Section title="Курсы FX" data={p.fx} />
      <Section title="Оплаты" data={p.payments} />
      <Section title="Округление" data={p.rounding} />
      <Section title="План счетов" data={p.accounts} />
      <Section title="Разрядность валют" data={p.currency_exponents} />
    </div>
  );
}
