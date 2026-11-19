import { useCallback, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { Toasts, useToasts } from "./components/Toasts";
import { useEpisode, type Opened } from "./hooks/useEpisode";
import { useDraft } from "./hooks/useDraft";
import { EpisodePicker } from "./screens/EpisodePicker";
import { Help } from "./screens/Help";
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
  void opened; // rendered by RecordDrawer (Task 6)

  let screen;
  switch (view.name) {
    case "episodes": screen = <EpisodePicker onStart={start} notify={notify} />; break;
    default: screen = <Help />;
  }

  return (
    <div className="app">
      <Sidebar view={view} go={go} hasEpisode={!!ep.obs} done={ep.done} findings={draft.findings.length} />
      <div className="main">
        <TopBar enabled={!!ep.obs && !ep.done} stepsRemaining={ep.stepsRemaining} maxSteps={ep.maxSteps}
                episodeId={ep.obs?.manifest.episode_id} onSearch={openId} notify={notify} />
        <main className="content">{screen}</main>
      </div>
      <Toasts toasts={toasts} />
    </div>
  );
}
