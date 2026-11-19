import { ArrowRightToLine, Check, ChevronDown, Download, Trash2 } from "lucide-react";
import { useState } from "react";

interface Props { count: number; disabled: boolean; onSubmit: () => void; onClear: () => void; onExport: () => void }

export function ActionBar({ count, disabled, onSubmit, onClear, onExport }: Props) {
  const [menu, setMenu] = useState(false);
  const [confirm, setConfirm] = useState(false);
  return (
    <>
      <div className="action-bar">
        <button className="btn" disabled>Черновик · {count} <Check size={14} /></button>
        <button className="btn" disabled={disabled} onClick={() => setConfirm(true)}>Отправить выводы <ArrowRightToLine size={14} /></button>
        <span className="divider" />
        <button className="btn ghost" onClick={() => setMenu((m) => !m)}>Ещё <ChevronDown size={14} /></button>
        {menu && (
          <div className="menu" onMouseLeave={() => setMenu(false)}>
            <button onClick={() => { setMenu(false); onExport(); }}><Download size={14} />Экспорт черновика (JSON)</button>
            <button onClick={() => { setMenu(false); onClear(); }} disabled={disabled}><Trash2 size={14} />Очистить черновик</button>
          </div>
        )}
      </div>
      {confirm && (
        <div className="modal-backdrop" onClick={() => setConfirm(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2 style={{ marginTop: 0 }}>Отправить {count} вывод(ов)?</h2>
            <p className="muted">Эпизод завершится, отправка стоит 1 шаг. Повторно отправить нельзя.</p>
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="btn" onClick={() => setConfirm(false)}>Отмена</button>
              <button className="btn primary" onClick={() => { setConfirm(false); onSubmit(); }}>Отправить</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
