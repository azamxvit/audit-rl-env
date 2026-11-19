import { useCallback, useState } from "react";
import { ActionBar } from "./components/ActionBar";
import { RecordDrawer } from "./components/RecordDrawer";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { Toasts, useToasts } from "./components/Toasts";
import { useEpisode, type Opened } from "./hooks/useEpisode";
import { useDraft } from "./hooks/useDraft";
import { EpisodePicker } from "./screens/EpisodePicker";
import { Findings } from "./screens/Findings";
import { Help } from "./screens/Help";
import { Overview } from "./screens/Overview";
import { CalculatorScreen } from "./screens/CalculatorScreen";
import { PolicyScreen } from "./screens/PolicyScreen";
import { Records } from "./screens/Records";
import { ID_FIELD } from "./lib/format";
import type { TableName } from "./types";

export type View =
  | { name: "episodes" } | { name: "overview" } | { name: "records"; table: TableName } | { name: "findings" }
  | { name: "calculator" } | { name: "policy" } | { name: "help" } | { name: "review" };

export default function App() {
  const { toasts, notify } = useToasts();
  const ep = useEpisode(notify);
  const [view, setView] = useState<View>({ name: "episodes" });
  const [opened, setOpened] = useState<Opened | null>(null);
  const exps = ep.obs?.policy.currency_exponents;
  const exponent = useCallback((c: string) => exps?.[c] ?? 2, [exps]);
  const draft = useDraft(`auditdesk:draft:${ep.session ?? "none"}`, ep.obs?.manifest.base_currency ?? "USD", exponent);

  const start = useCallback(async (key: string) => {
    try { await ep.start(key); setOpened(null); setView({ name: "overview" }); } catch { notify("Не удалось начать эпизод"); }
  }, [ep, notify]);
  const openId = useCallback(async (id: string) => { const o = await ep.open(id); if (o) setOpened(o); }, [ep]);
  const go = useCallback((v: View) => { setOpened(null); setView(v); }, []);

  const exportDraft = useCallback(() => {
    const blob = new Blob([JSON.stringify({ episode_id: ep.obs?.manifest.episode_id, findings: draft.findings }, null, 2)],
                          { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `findings-${ep.obs?.manifest.episode_id ?? "draft"}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }, [ep.obs, draft.findings]);

  let screen;
  switch (view.name) {
    case "episodes": screen = <EpisodePicker onStart={start} notify={notify} />; break;
    case "overview": screen = ep.obs ? <Overview ep={ep} draft={draft} notify={notify} onBack={() => go({ name: "episodes" })} /> : null; break;
    case "findings": screen = ep.obs ? <Findings ep={ep} draft={draft} /> : null; break;
    case "records": screen = ep.obs ? <Records table={view.table} ep={ep} onSelect={setOpened}
        selected={opened && opened.table === view.table ? String(opened.record[ID_FIELD[view.table]]) : undefined} /> : null; break;
    case "calculator": screen = ep.obs ? <CalculatorScreen ep={ep} /> : null; break;
    case "policy": screen = ep.obs ? <PolicyScreen ep={ep} /> : null; break;
    default: screen = <Help />;
  }

  return (
    <div className="app">
      <Sidebar view={view} go={go} hasEpisode={!!ep.obs} done={ep.done} findings={draft.findings.length} />
      <div className="main">
        <TopBar enabled={!!ep.obs && !ep.done} stepsRemaining={ep.stepsRemaining} maxSteps={ep.maxSteps}
                episodeId={ep.obs?.manifest.episode_id} onSearch={openId} notify={notify} />
        <main className="content">{screen}</main>
        {ep.obs && !ep.done && view.name !== "episodes" && view.name !== "help" && (
          <ActionBar count={draft.findings.length} disabled={ep.busy} onClear={draft.clear} onExport={exportDraft}
                     onSubmit={async () => { await ep.submit(draft.findings); setView({ name: "review" }); }} />
        )}
      </div>
      <Toasts toasts={toasts} />
      {opened && ep.obs && (
        <RecordDrawer opened={opened} exps={ep.obs.policy.currency_exponents} accounts={ep.obs.policy.accounts}
                      readOnly={ep.done} cached={(id) => !!ep.cache[id]} onOpen={openId}
                      onAdd={(kind, id) => { draft.addTo(kind, id); notify(`${id} → ${kind === "affected" ? "affected" : "доказательства"}`); }}
                      onClose={() => setOpened(null)} />
      )}
    </div>
  );
}
