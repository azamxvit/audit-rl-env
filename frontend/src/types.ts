export type TableName = "ledger" | "invoices" | "payments" | "fx";
export type Rec = Record<string, any>;
export type IssueType = "duplicate_invoice" | "payment_allocation" | "fx_error" | "period_cutoff";

export interface EpisodeInfo {
  key: string;
  split: string;
  episode_id: string;
  company_name: string;
  period_start: string;
  period_end: string;
  base_currency: string;
  timezone: string;
  counts: Record<string, number>;
}
export interface Manifest {
  schema_version: string;
  env_version: string;
  episode_id: string;
  company_name: string;
  base_currency: string;
  period_start: string;
  period_end: string;
  timezone: string;
  counts: Record<string, number>;
  rounding: { mode: string; scope: string };
}
export interface Policy {
  functional_currency: string;
  ledger_currency: string;
  period: { start: string; end: string; timezone: string; membership: string };
  revenue_recognition: string;
  fx: { direction: string; rate_date: string; fallback: string; conversion: string };
  rounding: { mode: string; scope: string };
  payments: { application: string; carrying_amount: string; fx_difference: string; refunds: string };
  accounts: Record<string, string>;
  currency_exponents: Record<string, number>;
}
export interface ResetObservation {
  task: string;
  manifest: Manifest;
  policy: Policy;
  tables: Record<TableName, { id_field: string; count: number }>;
  tools: unknown[];
  max_steps: number;
  steps_remaining: number;
}
export interface StepObservation {
  tool: string | null;
  ok: boolean;
  result: any;
  error: { code: string; message: string } | null;
  steps_remaining: number;
}
export interface StepResponse {
  observation: StepObservation;
  reward: number;
  terminated: boolean;
  truncated: boolean;
  info: Record<string, unknown>;
}
export interface Finding {
  type: IssueType;
  affected_ids: string[];
  claimed_amount_minor: number;
  currency: string;
  evidence_ids: string[];
  explanation: string;
}
export interface ReviewIssue {
  type: IssueType;
  affected_ids: string[];
  expected_amount_minor: number;
  currency: string;
  evidence_sets: string[][];
  status: "found" | "missed";
  matched_finding: number | null;
}
export interface Review {
  metrics: {
    tp: number;
    fp: number;
    fn: number;
    precision: number;
    recall: number;
    f1: number;
    reward: number;
    inspection_steps: number;
    valid: boolean;
    termination: string;
  };
  issues: ReviewIssue[];
  false_positives: number[];
}

/** Which screen the app shows. */
export type View =
  | { name: "episodes" }
  | { name: "overview" }
  | { name: "records"; table: TableName }
  | { name: "findings" }
  | { name: "calculator" }
  | { name: "policy" }
  | { name: "help" }
  | { name: "review" };
