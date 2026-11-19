import { useCallback, useState } from "react";

export interface Toast {
  id: number;
  text: string;
}

export function useToasts(timeoutMs = 4000) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const notify = useCallback(
    (text: string) => {
      const id = Date.now() + Math.random();
      setToasts((t) => [...t, { id, text }]);
      window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), timeoutMs);
    },
    [timeoutMs],
  );
  return { toasts, notify };
}

/** Live region: screen readers announce new messages politely. */
export function Toasts({ toasts }: { toasts: Toast[] }) {
  return (
    <div role="status" aria-live="polite" aria-label="Уведомления" className="fixed right-6 bottom-6 z-40">
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {toasts.map((t) => (
          <li
            key={t.id}
            className="max-w-[380px] rounded-lg bg-ink px-3.5 py-2.5 text-[13px] text-white shadow-float"
          >
            {t.text}
          </li>
        ))}
      </ul>
    </div>
  );
}
