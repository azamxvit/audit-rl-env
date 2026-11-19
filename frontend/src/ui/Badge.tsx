import type { ReactNode } from "react";

export type Tone = "solid-danger" | "danger" | "warn" | "success" | "info" | "neutral";

const tones: Record<Tone, string> = {
  "solid-danger": "bg-danger text-white",
  danger: "bg-danger-soft text-danger",
  warn: "bg-warn-soft text-warn",
  success: "bg-success-soft text-success",
  info: "bg-info-soft text-info",
  neutral: "bg-gray-100 text-ink-soft",
};

export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex h-[22px] items-center gap-1 rounded-md px-2 text-xs font-medium whitespace-nowrap ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
