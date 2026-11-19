import { FindingForm } from "../components/FindingForm";
import { FindingList } from "../components/FindingList";
import type { DraftApi } from "../hooks/useDraft";
import type { EpisodeApi } from "../hooks/useEpisode";
import { Page } from "../ui/Page";

export function Findings({ ep, draft }: { ep: EpisodeApi; draft: DraftApi }) {
  return (
    <Page title="Выводы" lead="Черновик бесплатен. Шагом станет только отправка.">
      <div className="grid grid-cols-2 gap-4">
        <FindingList draft={draft} exps={ep.obs!.policy.currency_exponents} readOnly={ep.done} />
        {!ep.done && <FindingForm draft={draft} />}
      </div>
    </Page>
  );
}
