import { PenLine, Plus } from "lucide-react";
import { useId, useState } from "react";
import type { DraftApi } from "../hooks/useDraft";
import { ISSUE_TYPES, TYPE_LABEL } from "../lib/format";
import type { IssueType } from "../types";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Field, IdChip, Select, TextArea, TextInput } from "../ui/Form";

type IdKind = "affected" | "evidence";

function IdListField({
  legend,
  ids,
  onAdd,
  onRemove,
}: {
  legend: string;
  ids: string[];
  onAdd: (id: string) => void;
  onRemove: (id: string) => void;
}) {
  const [value, setValue] = useState("");
  const inputId = useId();
  return (
    <fieldset className="m-0 mb-3 flex flex-col gap-1.5 border-0 p-0">
      <legend className="mb-1.5 p-0 text-xs text-muted">{legend}</legend>
      <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0">
        {ids.map((id) => (
          <li key={id}>
            <IdChip id={id} onRemove={() => onRemove(id)} />
          </li>
        ))}
        {!ids.length && <li className="text-[13px] text-muted">пусто — добавляйте из таблиц кнопками «+»</li>}
      </ul>
      <div className="flex items-center gap-2">
        <label htmlFor={inputId} className="sr-only">
          {`Добавить ID: ${legend}`}
        </label>
        <TextInput
          id={inputId}
          mono
          placeholder="ID вручную"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              if (value.trim()) {
                onAdd(value.trim());
                setValue("");
              }
            }
          }}
        />
        <Button
          size="sm"
          aria-label={`Добавить в «${legend}»`}
          onClick={() => {
            if (value.trim()) {
              onAdd(value.trim());
              setValue("");
            }
          }}
        >
          <Plus size={14} aria-hidden />
        </Button>
      </div>
    </fieldset>
  );
}

export function FindingForm({ draft }: { draft: DraftApi }) {
  const { form, setForm, addTo, saveForm } = draft;
  const [error, setError] = useState<string | null>(null);
  const ids = { type: useId(), amount: useId(), currency: useId(), explanation: useId(), error: useId() };
  const drop = (kind: IdKind) => (id: string) =>
    setForm((f) => ({ ...f, [kind]: f[kind].filter((x) => x !== id) }));
  const title = form.editing === null ? "Новый вывод" : `Вывод #${form.editing + 1}`;
  return (
    <Card title={title} icon={<PenLine size={18} aria-hidden />}>
      <form
        aria-label={title}
        aria-describedby={error ? ids.error : undefined}
        onSubmit={(e) => {
          e.preventDefault();
          setError(saveForm());
        }}
      >
        <Field label="Тип" htmlFor={ids.type}>
          <Select
            id={ids.type}
            value={form.type}
            onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as IssueType }))}
          >
            {ISSUE_TYPES.map((t) => (
              <option key={t} value={t}>
                {TYPE_LABEL[t]}
              </option>
            ))}
          </Select>
        </Field>
        <IdListField
          legend="Затронутые ID (affected_ids)"
          ids={form.affected}
          onAdd={(id) => addTo("affected", id)}
          onRemove={drop("affected")}
        />
        <IdListField
          legend="Доказательства (evidence_ids, ≤ 10)"
          ids={form.evidence}
          onAdd={(id) => addTo("evidence", id)}
          onRemove={drop("evidence")}
        />
        <div className="flex gap-2">
          <Field label="Сумма искажения (в мажорных единицах)" htmlFor={ids.amount} className="flex-[2]">
            <TextInput
              id={ids.amount}
              inputMode="decimal"
              placeholder="1234.56"
              value={form.amount}
              onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
            />
          </Field>
          <Field label="Валюта" htmlFor={ids.currency} className="flex-1">
            <TextInput
              id={ids.currency}
              maxLength={3}
              value={form.currency}
              onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))}
            />
          </Field>
        </div>
        <Field
          label={`Пояснение (${form.explanation.length}/1000) — на награду не влияет`}
          htmlFor={ids.explanation}
        >
          <TextArea
            id={ids.explanation}
            maxLength={1000}
            value={form.explanation}
            onChange={(e) => setForm((f) => ({ ...f, explanation: e.target.value }))}
          />
        </Field>
        {error && (
          <p id={ids.error} role="alert" className="text-[13px] text-danger">
            {error}
          </p>
        )}
        <div className="flex justify-end">
          <Button type="submit" variant="primary">
            Сохранить
          </Button>
        </div>
      </form>
    </Card>
  );
}
