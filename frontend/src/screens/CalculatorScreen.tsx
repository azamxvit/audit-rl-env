import { Calculator } from "lucide-react";
import { useState } from "react";
import type { EpisodeApi } from "../hooks/useEpisode";

export function CalculatorScreen({ ep }: { ep: EpisodeApi }) {
  const [expr, setExpr] = useState("");
  return (
    <div className="page" style={{ maxWidth: 760 }}>
      <h1>Калькулятор</h1>
      <p className="muted">Только арифметика над десятичными числами (Decimal). Каждое вычисление — 1 шаг.</p>
      <form className="card row" onSubmit={(e) => { e.preventDefault(); if (expr.trim()) { ep.calculate(expr.trim()); setExpr(""); } }}>
        <Calculator size={18} />
        <input className="input mono" style={{ flex: 1 }} placeholder="12500.00 * 1.084512" value={expr} onChange={(e) => setExpr(e.target.value)} disabled={ep.done} />
        <button className="btn primary" type="submit" disabled={ep.done || ep.busy}>Вычислить <span className="cost" style={{ color: "#cbd5e1" }}>· 1 шаг</span></button>
      </form>
      <div className="list" style={{ marginTop: 16, maxHeight: "none" }}>
        {ep.calc.map((c, i) => (
          <div key={i} className="list-item row">
            <span className="mono" style={{ flex: 1 }}>{c.expr}</span>
            {c.error ? <span className="error-text">{c.error}</span> : <span className="mono" style={{ fontWeight: 600 }}>= {c.value}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
