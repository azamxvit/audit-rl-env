import { useEffect, useId, useRef, type ReactNode } from "react";

/** Modal dialog: role=dialog + aria-modal, labelled by its title, closes on Escape, focuses first button. */
export function Dialog({
  title,
  description,
  onClose,
  children,
}: {
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const titleId = useId();
  const descId = useId();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-gray-900/35" onClick={onClose}>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        className="w-[420px] rounded-xl bg-canvas p-[22px] shadow-float"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id={titleId} className="m-0 mb-2 text-[17px] font-semibold">
          {title}
        </h2>
        {description && (
          <p id={descId} className="mt-0 text-muted">
            {description}
          </p>
        )}
        {children}
      </div>
    </div>
  );
}

/** Side panel with record details. A labelled complementary landmark. */
export function Drawer({
  label,
  header,
  footer,
  children,
}: {
  label: string;
  header: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}) {
  return (
    <aside
      aria-label={label}
      className="fixed top-0 right-0 z-30 flex h-screen w-[460px] flex-col border-l border-line bg-canvas shadow-float"
    >
      <header className="flex items-center gap-2.5 border-b border-line px-5 py-[18px]">{header}</header>
      <div className="flex-1 overflow-y-auto px-5 py-[18px]">{children}</div>
      {footer && <footer className="flex gap-2 border-t border-line px-5 py-3.5">{footer}</footer>}
    </aside>
  );
}
