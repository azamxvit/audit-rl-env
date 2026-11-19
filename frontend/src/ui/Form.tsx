import {
  forwardRef,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { X } from "lucide-react";
import { cx } from "./cx";

const control =
  "w-full rounded-lg border border-line bg-canvas px-2.5 py-2 text-sm text-ink outline-none " +
  "focus:border-accent disabled:bg-gray-50 disabled:text-subtle";

export const TextInput = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement> & { mono?: boolean }
>(function TextInput({ className, mono, ...rest }, ref) {
  return <input ref={ref} className={cx(control, mono && "font-mono text-[13px]", className)} {...rest} />;
});

export function Select({ className, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cx(control, className)} {...rest} />;
}

export function TextArea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cx(control, "min-h-20 resize-y", className)} {...rest} />;
}

/** Label + control wrapper. Pass the control's id as htmlFor. */
export function Field({
  label,
  htmlFor,
  className,
  children,
}: {
  label: ReactNode;
  htmlFor: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cx("mb-3 flex flex-col gap-1.5", className)}>
      <label htmlFor={htmlFor} className="text-xs text-muted">
        {label}
      </label>
      {children}
    </div>
  );
}

/** Monospace ID tag, optionally removable. */
export function IdChip({ id, onRemove }: { id: string; onRemove?: () => void }) {
  return (
    <span className="inline-flex h-6 items-center gap-1.5 rounded-md border border-line bg-canvas px-2 font-mono text-xs">
      {id}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Убрать ${id}`}
          className="flex border-0 bg-transparent p-0 text-muted hover:text-ink"
        >
          <X size={12} aria-hidden />
        </button>
      )}
    </span>
  );
}

export function SearchBox({
  label,
  className,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label
      className={cx(
        "flex h-[38px] items-center gap-2 rounded-lg border border-line px-3 text-muted",
        className,
      )}
    >
      <span className="sr-only">{label}</span>
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        aria-hidden
      >
        <circle cx="11" cy="11" r="8" />
        <path d="m21 21-4.3-4.3" />
      </svg>
      <input
        type="search"
        className="min-w-0 flex-1 border-0 bg-transparent text-ink outline-none"
        {...rest}
      />
    </label>
  );
}
