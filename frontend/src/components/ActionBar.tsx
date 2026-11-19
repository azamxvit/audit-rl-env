import { ArrowRightToLine, Check, ChevronDown, Download, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button, Dialog } from "@/ui";

interface Props {
  count: number;
  disabled: boolean;
  onSubmit: () => void;
  onClear: () => void;
  onExport: () => void;
}

export function ActionBar({ count, disabled, onSubmit, onClear, onExport }: Props) {
  const [menu, setMenu] = useState(false);
  const [confirm, setConfirm] = useState(false);
  return (
    <>
      <div
        role="toolbar"
        aria-label="Действия с выводами"
        className="fixed bottom-6 left-[calc(248px+(100vw-248px)/2)] z-20 flex -translate-x-1/2 items-center gap-2 rounded-xl border border-line bg-canvas p-2 shadow-float"
      >
        <Button disabled>
          Черновик · {count} <Check size={14} aria-hidden />
        </Button>
        <Button disabled={disabled} onClick={() => setConfirm(true)}>
          Отправить выводы <ArrowRightToLine size={14} aria-hidden />
        </Button>
        <span aria-hidden className="h-6 w-px bg-line" />
        <div className="relative">
          <Button
            variant="ghost"
            aria-haspopup="menu"
            aria-expanded={menu}
            onClick={() => setMenu((m) => !m)}
          >
            Ещё <ChevronDown size={14} aria-hidden />
          </Button>
          {menu && (
            <ul
              role="menu"
              aria-label="Ещё"
              className="absolute right-0 bottom-12 m-0 min-w-[240px] list-none rounded-[10px] border border-line bg-canvas p-1.5 shadow-float"
            >
              {[
                { label: "Экспорт черновика (JSON)", icon: Download, action: onExport, off: false },
                { label: "Очистить черновик", icon: Trash2, action: onClear, off: disabled },
              ].map(({ label, icon: Icon, action, off }) => (
                <li key={label} role="none">
                  <button
                    type="button"
                    role="menuitem"
                    disabled={off}
                    onClick={() => {
                      setMenu(false);
                      action();
                    }}
                    className="flex w-full items-center gap-2 rounded-md border-0 bg-transparent px-2.5 py-2 text-left hover:enabled:bg-gray-100 disabled:text-subtle"
                  >
                    <Icon size={14} aria-hidden />
                    {label}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      {confirm && (
        <Dialog
          title={`Отправить ${count} вывод(ов)?`}
          description="Эпизод завершится, отправка стоит 1 шаг. Повторно отправить нельзя."
          onClose={() => setConfirm(false)}
        >
          <div className="flex justify-end gap-2">
            <Button onClick={() => setConfirm(false)}>Отмена</Button>
            <Button
              variant="primary"
              onClick={() => {
                setConfirm(false);
                onSubmit();
              }}
            >
              Отправить
            </Button>
          </div>
        </Dialog>
      )}
    </>
  );
}
