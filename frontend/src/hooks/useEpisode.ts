import { useCallback, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { Finding, Rec, ResetObservation, Review, StepResponse, TableName } from "../types";
import { OWN_KEYS, lookupTarget } from "../lib/format";

export interface Opened {
  table: TableName;
  record: Rec;
}
export interface TableState {
  rows: Rec[];
  next: string | null;
  started: boolean;
}
export interface CalcEntry {
  expr: string;
  value: string | null;
  error: string | null;
}

const emptyTables = (): Record<TableName, TableState> => ({
  ledger: { rows: [], next: null, started: false },
  invoices: { rows: [], next: null, started: false },
  payments: { rows: [], next: null, started: false },
  fx: { rows: [], next: null, started: false },
});

export function useEpisode(notify: (msg: string) => void) {
  const [session, setSession] = useState<string | null>(null);
  const [obs, setObs] = useState<ResetObservation | null>(null);
  const [stepsRemaining, setSteps] = useState(0);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [tables, setTables] = useState(emptyTables);
  const [cache, setCache] = useState<Record<string, Opened>>({});
  const [calc, setCalc] = useState<CalcEntry[]>([]);
  const [review, setReview] = useState<Review | null>(null);
  const sessionRef = useRef<string | null>(null);
  const doneRef = useRef(false);
  const tablesRef = useRef(tables);
  tablesRef.current = tables;
  const cacheRef = useRef(cache);
  cacheRef.current = cache;

  const remember = useCallback((table: TableName, recs: Rec[]) => {
    setCache((c) => {
      const next = { ...c };
      for (const r of recs)
        for (const k of OWN_KEYS[table]) if (typeof r[k] === "string") next[r[k]] = { table, record: r };
      return next;
    });
  }, []);

  const step = useCallback(
    async (action: unknown): Promise<StepResponse | null> => {
      const s = sessionRef.current;
      if (!s || doneRef.current) return null;
      setBusy(true);
      try {
        const r = await api.step(s, action);
        setSteps(r.observation.steps_remaining);
        if (!r.observation.ok && r.observation.error)
          notify(`${r.observation.error.code}: ${r.observation.error.message}`);
        if (r.terminated || r.truncated) {
          doneRef.current = true;
          setDone(true);
          setReview(await api.review(s));
        }
        return r;
      } catch (e) {
        notify(e instanceof ApiError ? `Сервер: ${e.code}` : "Сервер недоступен");
        return null;
      } finally {
        setBusy(false);
      }
    },
    [notify],
  );

  const start = useCallback(async (key: string) => {
    const r = await api.reset(key);
    sessionRef.current = r.session;
    doneRef.current = false;
    setSession(r.session);
    setObs(r.observation);
    setSteps(r.observation.steps_remaining);
    setDone(false);
    setTables(emptyTables());
    setCache({});
    setCalc([]);
    setReview(null);
  }, []);

  const leave = useCallback(() => {
    sessionRef.current = null;
    setSession(null);
    setObs(null);
    setReview(null);
  }, []);

  const loadMore = useCallback(
    async (table: TableName) => {
      const t = tablesRef.current[table];
      if (t.started && !t.next) return;
      const args: Record<string, unknown> = { table, limit: 50 };
      if (t.next) args.cursor = t.next;
      const r = await step({ tool: "list_records", args });
      if (!r || !r.observation.ok) return;
      const res = r.observation.result as { records: Rec[]; next_cursor: string | null };
      setTables((all) => ({
        ...all,
        [table]: { rows: [...all[table].rows, ...res.records], next: res.next_cursor, started: true },
      }));
      remember(table, res.records);
    },
    [step, remember],
  );

  const open = useCallback(
    async (id: string): Promise<Opened | null> => {
      const key = id.trim();
      if (cacheRef.current[key]) return cacheRef.current[key];
      const target = lookupTarget(key);
      if (!target) {
        notify("Неизвестный формат ID — шаг не потрачен");
        return null;
      }
      const r =
        target.kind === "document"
          ? await step({ tool: "get_document", args: { doc_id: key } })
          : await step({ tool: "get_record", args: { table: target.table, id: key } });
      if (!r || !r.observation.ok) return null;
      let opened: Opened;
      if (target.kind === "document") {
        const res = r.observation.result as { doc_type: string; document: Rec };
        opened = { table: res.doc_type === "invoice" ? "invoices" : "payments", record: res.document };
      } else {
        opened = { table: target.table, record: r.observation.result as Rec };
      }
      remember(opened.table, [opened.record]);
      return opened;
    },
    [step, remember, notify],
  );

  const calculate = useCallback(
    async (expr: string) => {
      const r = await step({ tool: "calculator", args: { expression: expr } });
      if (!r) return;
      const o = r.observation;
      setCalc((c) => [
        {
          expr,
          value: o.ok ? String(o.result.value) : null,
          error: o.ok ? null : (o.error?.message ?? "error"),
        },
        ...c,
      ]);
    },
    [step],
  );

  const submit = useCallback(
    async (findings: Finding[]) => {
      if (!obs) return;
      await step({ tool: "submit", args: { episode_id: obs.manifest.episode_id, findings } });
    },
    [step, obs],
  );

  return {
    session,
    obs,
    stepsRemaining,
    maxSteps: obs?.max_steps ?? 100,
    done,
    busy,
    tables,
    cache,
    calc,
    review,
    start,
    leave,
    loadMore,
    open,
    calculate,
    submit,
  };
}

export type EpisodeApi = ReturnType<typeof useEpisode>;
