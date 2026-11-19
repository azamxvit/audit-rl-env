import { useCallback, useEffect, useState } from "react";
import { ActionBar } from "./components/ActionBar";
import { RecordDrawer } from "./components/RecordDrawer";
import { Sidebar } from "./components/Sidebar";
import { Toasts, useToasts } from "./components/Toasts";
import { TopBar } from "./components/TopBar";
import { useDraft } from "./hooks/useDraft";
import { useEpisode, type Opened } from "./hooks/useEpisode";
import { ID_FIELD } from "./lib/format";
import { CalculatorScreen } from "./screens/CalculatorScreen";
import { EpisodePicker } from "./screens/EpisodePicker";
import { Findings } from "./screens/Findings";
import { Help } from "./screens/Help";
import { Overview } from "./screens/Overview";
import { PolicyScreen } from "./screens/PolicyScreen";
import { Records } from "./screens/Records";
import { Review } from "./screens/Review";
import type { TableName } from "./types";

export type View =
  | { name: "episodes" }
  | { name: "overview" }
  | { name: "records"; table: TableName }
  | { name: "findings" }
  | { name: "calculator" }
  | { name: "policy" }
  | { name: "help" }
  | { name: "review" };

function downloadJson(filename: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function App() {
  const { toasts, notify } = useToasts();
  const ep = useEpisode(notify);
  const [view, setView] = useState<View>({ name: "episodes" });
  const [opened, setOpened] = useState<Opened | null>(null);
  const [episodeKey, setEpisodeKey] = useState<string | null>(null);
  const exps = ep.obs?.policy.currency_exponents;
  const exponent = useCallback((c: string) => exps?.[c] ?? 2, [exps]);
  const draft = useDraft(
    `auditdesk:draft:${ep.session ?? "none"}`,
    ep.obs?.manifest.base_currency ?? "USD",
    exponent,
  );

  const start = useCallback(
    async (key: string) => {
      try {
        await ep.start(key);
        setEpisodeKey(key);
        setOpened(null);
        setView({ name: "overview" });
      } catch {
        notify("Не удалось начать эпизод");
      }
    },
    [ep, notify],
  );
  const openId = useCallback(
    async (id: string) => {
      const o = await ep.open(id);
      if (o) setOpened(o);
    },
    [ep],
  );
  const go = useCallback((v: View) => {
    setOpened(null);
    setView(v);
  }, []);
  useEffect(() => {
    if (ep.done && ep.review) setView({ name: "review" });
  }, [ep.done, ep.review]);

  const episodeId = ep.obs?.manifest.episode_id;
  let screen = null;
  if (view.name === "episodes") screen = <EpisodePicker onStart={start} notify={notify} />;
  else if (view.name === "help" || !ep.obs) screen = <Help />;
  else if (view.name === "overview")
    screen = <Overview ep={ep} draft={draft} notify={notify} onBack={() => go({ name: "episodes" })} />;
  else if (view.name === "findings") screen = <Findings ep={ep} draft={draft} />;
  else if (view.name === "records")
    screen = (
      <Records
        table={view.table}
        ep={ep}
        onSelect={setOpened}
        selected={opened?.table === view.table ? String(opened.record[ID_FIELD[view.table]]) : undefined}
      />
    );
  else if (view.name === "calculator") screen = <CalculatorScreen ep={ep} />;
  else if (view.name === "policy") screen = <PolicyScreen ep={ep} />;
  else if (view.name === "review")
    screen = (
      <Review
        ep={ep}
        draft={draft}
        onAgain={() => episodeKey && start(episodeKey)}
        onOther={() => go({ name: "episodes" })}
      />
    );

  return (
    <div className="grid h-screen grid-cols-[248px_minmax(0,1fr)]">
      <Sidebar view={view} go={go} hasEpisode={!!ep.obs} done={ep.done} findings={draft.findings.length} />
      <div className="flex min-w-0 flex-col">
        <TopBar
          enabled={!!ep.obs && !ep.done}
          stepsRemaining={ep.stepsRemaining}
          maxSteps={ep.maxSteps}
          episodeId={episodeId}
          onSearch={openId}
          notify={notify}
        />
        <main id="content" className="flex-1 overflow-y-auto px-8 pt-6 pb-[120px]">
          {screen}
        </main>
        {ep.obs && !ep.done && view.name !== "episodes" && view.name !== "help" && (
          <ActionBar
            count={draft.findings.length}
            disabled={ep.busy}
            onClear={draft.clear}
            onExport={() =>
              downloadJson(`findings-${episodeId ?? "draft"}.json`, {
                episode_id: episodeId,
                findings: draft.findings,
              })
            }
            onSubmit={() => ep.submit(draft.findings)}
          />
        )}
      </div>
      <Toasts toasts={toasts} />
      {opened && ep.obs && (
        <RecordDrawer
          opened={opened}
          exps={ep.obs.policy.currency_exponents}
          accounts={ep.obs.policy.accounts}
          readOnly={ep.done}
          cached={(id) => !!ep.cache[id]}
          onOpen={openId}
          onAdd={(kind, id) => {
            draft.addTo(kind, id);
            notify(`${id} → ${kind === "affected" ? "affected" : "доказательства"}`);
          }}
          onClose={() => setOpened(null)}
        />
      )}
    </div>
  );
}
