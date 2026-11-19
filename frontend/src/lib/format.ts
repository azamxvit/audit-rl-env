import type { IssueType, TableName } from "../types";

export const ISSUE_TYPES: IssueType[] = ["duplicate_invoice", "payment_allocation", "fx_error", "period_cutoff"];
export const TYPE_LABEL: Record<IssueType, string> = {
  duplicate_invoice: "Дубль счёта",
  payment_allocation: "Распределение платежа",
  fx_error: "Ошибка курса",
  period_cutoff: "Отнесение к периоду",
};
export const TABLE_LABEL: Record<TableName, string> = {
  ledger: "Главная книга", invoices: "Счета", payments: "Платежи", fx: "Курсы FX",
};
export const ID_FIELD: Record<TableName, string> = {
  ledger: "row_id", invoices: "invoice_id", payments: "payment_id", fx: "rate_id",
};
export const OWN_KEYS: Record<TableName, string[]> = {
  ledger: ["row_id"], invoices: ["invoice_id", "doc_id"], payments: ["payment_id", "doc_id"], fx: ["rate_id"],
};
const PREFIX: Record<string, TableName> = { LR: "ledger", INV: "invoices", PAY: "payments", FXR: "fx" };

export function lookupTarget(id: string): { kind: "record"; table: TableName } | { kind: "document" } | null {
  const prefix = id.trim().split("-")[0].toUpperCase();
  if (prefix === "DOC") return { kind: "document" };
  const table = PREFIX[prefix];
  return table ? { kind: "record", table } : null;
}

export function formatMinor(minor: number, currency: string, exps: Record<string, number>): string {
  const e = exps[currency] ?? 2;
  const a = Math.abs(minor);
  const major = Math.floor(a / 10 ** e).toLocaleString("ru-RU");
  const frac = e ? "," + String(a % 10 ** e).padStart(e, "0") : "";
  return `${minor < 0 ? "−" : ""}${major}${frac} ${currency}`;
}

/** "1 234,56" | "1234.56" -> minor units; null if not a valid non-negative amount for this exponent. */
export function parseMajor(text: string, exp: number): number | null {
  const t = text.replace(/\s/g, "").replace(",", ".");
  if (!/^\d+(\.\d+)?$/.test(t)) return null;
  const [int, frac = ""] = t.split(".");
  if (frac.length > exp) return null;
  const minor = Number(int) * 10 ** exp + Number(frac.padEnd(exp, "0") || "0");
  return Number.isSafeInteger(minor) ? minor : null;
}

export function formatDate(iso: string): string {
  const [d] = iso.split("T");
  const [y, m, day] = d.split("-");
  return `${day}.${m}.${y}`;
}

export function formatTimestamp(iso: string): string {
  const [d, rest = ""] = iso.split("T");
  return `${formatDate(d)} ${rest.slice(0, 5)} (${rest.slice(8) || "+00:00"})`;
}

export function periodLabel(start: string, end: string): string {
  return `${formatDate(start)} – ${formatDate(end)}`;
}
