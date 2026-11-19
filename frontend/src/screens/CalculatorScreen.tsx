import { Calculator } from "lucide-react";
import { useState } from "react";
import type { EpisodeApi } from "@/hooks";
import { Button, Cost, TextInput, Mono, Page } from "@/ui";

export function CalculatorScreen({ ep }: { ep: EpisodeApi }) {
  const [expr, setExpr] = useState("");
  return (
    <Page
      title="Калькулятор"
      lead="Только арифметика над десятичными числами (Decimal). Каждое вычисление — 1 шаг."
    >
      <form
        aria-label="Калькулятор"
        className="flex max-w-[760px] items-center gap-2 rounded-[10px] border border-line bg-canvas p-[18px] shadow-card"
        onSubmit={(e) => {
          e.preventDefault();
          if (expr.trim()) {
            ep.calculate(expr.trim());
            setExpr("");
          }
        }}
      >
        <Calculator size={18} aria-hidden />
        <label htmlFor="calc-expression" className="sr-only">
          Выражение
        </label>
        <TextInput
          id="calc-expression"
          mono
          placeholder="12500.00 * 1.084512"
          value={expr}
          onChange={(e) => setExpr(e.target.value)}
          disabled={ep.done}
        />
        <Button type="submit" variant="primary" disabled={ep.done || ep.busy}>
          Вычислить <Cost />
        </Button>
      </form>
      <section aria-label="История вычислений" className="mt-4 max-w-[760px]">
        <ol className="m-0 flex list-none flex-col gap-2.5 p-0">
          {ep.calc.map((c, i) => (
            <li
              key={i}
              className="flex items-center gap-2 rounded-lg border border-line bg-canvas px-3 py-2.5"
            >
              <Mono className="flex-1">{c.expr}</Mono>
              {c.error ? (
                <span role="alert" className="text-[13px] text-danger">
                  {c.error}
                </span>
              ) : (
                <output className="font-mono text-[12.5px] font-semibold">= {c.value}</output>
              )}
            </li>
          ))}
        </ol>
      </section>
    </Page>
  );
}
