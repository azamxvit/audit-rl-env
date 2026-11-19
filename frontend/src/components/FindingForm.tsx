import { PenLine, Plus, X } from "lucide-react";
import { useState } from "react";
import type { DraftApi } from "../hooks/useDraft";
import type { IssueType } from "../types";
import { ISSUE_TYPES, TYPE_LABEL } from "../lib/format";

function IdChips({ ids, onRemove }: { ids: string[]; onRemove: (id: string) => void }) {
  return (
    <div className="chips">
      {ids.map((id) => <span key={id} className="chip">{id}<button onClick={() => onRemove(id)} aria-label="убрать"><X size={12} /></button></span>)}
      {!ids.length && <span className="muted">пусто — добавляйте из таблиц кнопками «+»</span>}
    </div>
  );
}

function AddId({ onAdd }: { onAdd: (id: string) => void }) {
  const [v, setV] = useState("");
  return (
    <form className="row" onSubmit={(e) => { e.preventDefault(); if (v.trim()) { onAdd(v.trim()); setV(""); } }}>
      <input className="input mono" style={{ flex: 1 }} placeholder="ID вручную" value={v} onChange={(e) => setV(e.target.value)} />
      <button className="btn small" type="submit"><Plus size={14} /></button>
    </form>
  );
}

export function FindingForm({ draft }: { draft: DraftApi }) {
  const { form, setForm, addTo, saveForm } = draft;
  const [error, setError] = useState<string | null>(null);
  const drop = (kind: "affected" | "evidence") => (id: string) => setForm((f) => ({ ...f, [kind]: f[kind].filter((x) => x !== id) }));
  return (
    <div className="card">
      <div className="card-title"><PenLine size={18} />{form.editing === null ? "Новый вывод" : `Вывод #${form.editing + 1}`}</div>
      <div className="field">
        <label>Тип</label>
        <select value={form.type} onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as IssueType }))}>
          {ISSUE_TYPES.map((t) => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
        </select>
      </div>
      <div className="field"><label>Затронутые ID (affected_ids)</label><IdChips ids={form.affected} onRemove={drop("affected")} /><AddId onAdd={(id) => addTo("affected", id)} /></div>
      <div className="field"><label>Доказательства (evidence_ids, ≤ 10)</label><IdChips ids={form.evidence} onRemove={drop("evidence")} /><AddId onAdd={(id) => addTo("evidence", id)} /></div>
      <div className="row">
        <div className="field" style={{ flex: 2 }}>
          <label>Сумма искажения (в мажорных единицах)</label>
          <input className="input" inputMode="decimal" placeholder="1234.56" value={form.amount} onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))} />
        </div>
        <div className="field" style={{ flex: 1 }}>
          <label>Валюта</label>
          <input className="input" maxLength={3} value={form.currency} onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))} />
        </div>
      </div>
      <div className="field">
        <label>Пояснение ({form.explanation.length}/1000) — на награду не влияет</label>
        <textarea maxLength={1000} value={form.explanation} onChange={(e) => setForm((f) => ({ ...f, explanation: e.target.value }))} />
      </div>
      {error && <p className="error-text">{error}</p>}
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button className="btn primary" onClick={() => setError(saveForm())}>Сохранить</button>
      </div>
    </div>
  );
}
