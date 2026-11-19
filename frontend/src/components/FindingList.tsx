import { ClipboardCheck, Pencil, Trash2 } from "lucide-react";
import type { DraftApi } from "../hooks/useDraft";
import { formatMinor, TYPE_LABEL } from "../lib/format";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, EmptyState } from "../ui/Card";
import { Mono, Muted } from "../ui/Page";

export function FindingList({
  draft,
  exps,
  readOnly,
}: {
  draft: DraftApi;
  exps: Record<string, number>;
  readOnly?: boolean;
}) {
  return (
    <Card
      title={
        <>
          Выводы <Muted>({draft.findings.length})</Muted>
        </>
      }
      icon={<ClipboardCheck size={18} aria-hidden />}
    >
      {!draft.findings.length ? (
        <EmptyState>Черновик пуст. Молчание на чистых книгах — тоже ответ.</EmptyState>
      ) : (
        <ol className="m-0 flex max-h-[420px] list-none flex-col gap-2.5 overflow-y-auto p-0">
          {draft.findings.map((f, i) => (
            <li key={i}>
              <article
                aria-label={`Вывод ${i + 1}: ${TYPE_LABEL[f.type]}`}
                className="rounded-lg border border-line bg-canvas px-3 py-2.5"
              >
                <header className="mb-1.5 flex items-center gap-2">
                  <Badge tone="info">{TYPE_LABEL[f.type]}</Badge>
                  <Muted>#{i + 1}</Muted>
                  <data value={f.claimed_amount_minor} className="ml-auto font-semibold">
                    {formatMinor(f.claimed_amount_minor, f.currency, exps)}
                  </data>
                  {!readOnly && (
                    <>
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label={`Редактировать вывод ${i + 1}`}
                        onClick={() => draft.edit(i)}
                      >
                        <Pencil size={14} aria-hidden />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label={`Удалить вывод ${i + 1}`}
                        onClick={() => draft.remove(i)}
                      >
                        <Trash2 size={14} aria-hidden />
                      </Button>
                    </>
                  )}
                </header>
                <p className="m-0">
                  <Mono>{f.affected_ids.join(", ")}</Mono>
                </p>
                <p className="m-0 mt-1 text-muted">
                  доказательства: <Mono>{f.evidence_ids.join(", ") || "—"}</Mono>
                </p>
              </article>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
