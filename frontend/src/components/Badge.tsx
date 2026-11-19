import type { ReactNode } from "react";

export type Tone = "red" | "danger" | "warn" | "success" | "info" | "neutral";

export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
