import { ClipboardCheck, Pencil, Trash2 } from "lucide-react";
import type { DraftApi } from "../hooks/useDraft";
import { formatMinor, TYPE_LABEL } from "../lib/format";
import { Badge } from "./Badge";

export function FindingList({ draft, exps, readOnly }: { draft: DraftApi; exps: Record<string, number>; readOnly?: boolean }) {
  return (
    <div className="card">
      <div className="card-title"><ClipboardCheck size={18} />Выводы <span className="muted">({draft.findings.length})</span></div>
      <div className="list">
        {!draft.findings.length && <div className="empty">Черновик пуст. Молчание на чистых книгах — тоже ответ.</div>}
        {draft.findings.map((f, i) => (
          <div key={i} className="list-item">
            <div className="list-item-head">
              <Badge tone="info">{TYPE_LABEL[f.type]}</Badge>
              <span className="muted">#{i + 1}</span>
              <span style={{ marginLeft: "auto", fontWeight: 600 }}>{formatMinor(f.claimed_amount_minor, f.currency, exps)}</span>
              {!readOnly && <>
                <button className="btn ghost small" onClick={() => draft.edit(i)} aria-label="редактировать"><Pencil size={14} /></button>
                <button className="btn ghost small" onClick={() => draft.remove(i)} aria-label="удалить"><Trash2 size={14} /></button>
              </>}
            </div>
            <div className="mono">{f.affected_ids.join(", ")}</div>
            <div className="muted mono" style={{ marginTop: 4 }}>доказательства: {f.evidence_ids.join(", ") || "—"}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
