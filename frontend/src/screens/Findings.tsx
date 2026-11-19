import type { EpisodeApi } from "../hooks/useEpisode";
import type { DraftApi } from "../hooks/useDraft";
import { FindingForm } from "../components/FindingForm";
import { FindingList } from "../components/FindingList";

export function Findings({ ep, draft }: { ep: EpisodeApi; draft: DraftApi }) {
  return (
    <div className="page">
      <h1>Выводы</h1>
      <p className="muted">Черновик бесплатен. Шагом станет только отправка.</p>
      <div className="two-col">
        <FindingList draft={draft} exps={ep.obs!.policy.currency_exponents} readOnly={ep.done} />
        {!ep.done && <FindingForm draft={draft} />}
      </div>
    </div>
  );
}
