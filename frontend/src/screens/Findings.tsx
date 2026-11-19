import { FindingForm, FindingList } from "@/components";
import type { DraftApi, EpisodeApi } from "@/hooks";
import { Page } from "@/ui";

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
