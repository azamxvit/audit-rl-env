import { useCallback, useEffect, useState } from "react";
import type { Finding, IssueType } from "@/types";
import { parseMajor } from "@/lib";

export interface FormState {
  type: IssueType;
  affected: string[];
  evidence: string[];
  amount: string;
  currency: string;
  explanation: string;
  editing: number | null;
}

const blank = (currency: string): FormState => ({
  type: "duplicate_invoice",
  affected: [],
  evidence: [],
  amount: "",
  currency,
  explanation: "",
  editing: null,
});

function load(key: string): Finding[] {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as Finding[]) : [];
  } catch {
    return [];
  }
}

export function useDraft(storageKey: string, baseCurrency: string, exponent: (ccy: string) => number) {
  const [findings, setFindings] = useState<Finding[]>(() => load(storageKey));
  const [form, setForm] = useState<FormState>(() => blank(baseCurrency));

  useEffect(() => {
    setFindings(load(storageKey));
    setForm(blank(baseCurrency));
  }, [storageKey, baseCurrency]);
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(findings));
    } catch {
      /* storage unavailable */
    }
  }, [storageKey, findings]);

  const addTo = useCallback((kind: "affected" | "evidence", id: string) => {
    setForm((f) => (f[kind].includes(id) || f[kind].length >= 10 ? f : { ...f, [kind]: [...f[kind], id] }));
  }, []);

  /** Returns an error message, or null on success. */
  const saveForm = useCallback((): string | null => {
    const cur = form.currency.trim().toUpperCase();
    if (!form.affected.length) return "Добавьте хотя бы один affected ID";
    if (!/^[A-Z]{3}$/.test(cur)) return "Валюта — три буквы";
    const minor = parseMajor(form.amount, exponent(cur));
    if (minor === null) return "Сумма: неотрицательное число с допустимым числом знаков после запятой";
    const f: Finding = {
      type: form.type,
      affected_ids: form.affected,
      claimed_amount_minor: minor,
      currency: cur,
      evidence_ids: form.evidence,
      explanation: form.explanation.slice(0, 1000),
    };
    if (form.editing === null && findings.length >= 30) return "Не больше 30 выводов";
    setFindings((all) =>
      form.editing === null ? [...all, f] : all.map((x, i) => (i === form.editing ? f : x)),
    );
    setForm(blank(baseCurrency));
    return null;
  }, [form, findings.length, baseCurrency, exponent]);

  const remove = useCallback((i: number) => setFindings((all) => all.filter((_, k) => k !== i)), []);
  const edit = useCallback(
    (i: number) => {
      const f = findings[i];
      const e = exponent(f.currency);
      const major = e
        ? `${Math.floor(f.claimed_amount_minor / 10 ** e)}.${String(f.claimed_amount_minor % 10 ** e).padStart(e, "0")}`
        : String(f.claimed_amount_minor);
      setForm({
        type: f.type,
        affected: f.affected_ids,
        evidence: f.evidence_ids,
        amount: major,
        currency: f.currency,
        explanation: f.explanation,
        editing: i,
      });
    },
    [findings, exponent],
  );
  const clear = useCallback(() => {
    setFindings([]);
    setForm(blank(baseCurrency));
  }, [baseCurrency]);

  return { findings, form, setForm, addTo, saveForm, remove, edit, clear };
}

export type DraftApi = ReturnType<typeof useDraft>;
