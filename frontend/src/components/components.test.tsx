import { render, renderHook, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { useDraft } from "@/hooks";
import { DataTable } from "@/ui";
import { ActionBar, FindingForm, FindingList, Sidebar } from "@/components";

const exponent = () => 2;

describe("Sidebar", () => {
  it("is a labelled navigation landmark with the current page marked", () => {
    render(<Sidebar view={{ name: "overview" }} go={vi.fn()} hasEpisode done={false} findings={2} />);
    const nav = screen.getByRole("navigation", { name: "Основная навигация" });
    expect(within(nav).getByRole("button", { name: "Обзор" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("heading", { name: "Расследование", level: 2 })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: /Выводы/ })).toHaveTextContent("2");
  });

  it("disables episode tools until an episode is started", async () => {
    const go = vi.fn();
    render(<Sidebar view={{ name: "episodes" }} go={go} hasEpisode={false} done={false} findings={0} />);
    expect(screen.getByRole("button", { name: "Главная книга" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Калькулятор" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Как играть" }));
    expect(go).toHaveBeenCalledWith({ name: "help" });
  });
});

describe("FindingForm", () => {
  it("uses labelled controls and reports validation errors as an alert", async () => {
    const { result } = renderHook(() => useDraft("k1", "USD", exponent));
    const { rerender } = render(<FindingForm draft={result.current} />);
    expect(screen.getByRole("form", { name: "Новый вывод" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Тип" })).toHaveValue("duplicate_invoice");
    expect(screen.getByRole("group", { name: "Затронутые ID (affected_ids)" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    rerender(<FindingForm draft={result.current} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/affected/);
  });

  it("adds ids typed by hand and removes them via the chip button", async () => {
    const { result } = renderHook(() => useDraft("k2", "USD", exponent));
    const view = render(<FindingForm draft={result.current} />);
    await userEvent.type(screen.getByRole("textbox", { name: /Добавить ID: Затронутые/ }), "INV-42{Enter}");
    view.rerender(<FindingForm draft={result.current} />);
    expect(result.current.form.affected).toEqual(["INV-42"]);
    await userEvent.click(screen.getByRole("button", { name: "Убрать INV-42" }));
    view.rerender(<FindingForm draft={result.current} />);
    expect(result.current.form.affected).toEqual([]);
  });
});

describe("FindingList", () => {
  it("renders an ordered list of findings with amounts", () => {
    const { result } = renderHook(() => useDraft("k3", "USD", exponent));
    result.current.findings.push({
      type: "fx_error",
      affected_ids: ["INV-1"],
      claimed_amount_minor: 1234,
      currency: "USD",
      evidence_ids: ["DOC-1"],
      explanation: "",
    });
    render(<FindingList draft={result.current} exps={{ USD: 2 }} />);
    const item = screen.getByRole("article", { name: "Вывод 1: Ошибка курса" });
    expect(within(item).getByText("12,34 USD")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Удалить вывод 1" })).toBeInTheDocument();
  });
});

describe("ActionBar", () => {
  it("asks for confirmation in a modal dialog before submitting", async () => {
    const onSubmit = vi.fn();
    render(<ActionBar count={2} disabled={false} onSubmit={onSubmit} onClear={vi.fn()} onExport={vi.fn()} />);
    expect(screen.getByRole("toolbar", { name: "Действия с выводами" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Отправить выводы/ }));
    const dialog = screen.getByRole("dialog", { name: "Отправить 2 вывод(ов)?" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    await userEvent.click(within(dialog).getByRole("button", { name: "Отмена" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /Отправить выводы/ }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Отправить" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("closes the dialog with Escape and exposes the extra actions as a menu", async () => {
    const onExport = vi.fn();
    render(<ActionBar count={0} disabled={false} onSubmit={vi.fn()} onClear={vi.fn()} onExport={onExport} />);
    await userEvent.click(screen.getByRole("button", { name: /Отправить выводы/ }));
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    const more = screen.getByRole("button", { name: /Ещё/ });
    expect(more).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(more);
    await userEvent.click(screen.getByRole("menuitem", { name: /Экспорт/ }));
    expect(onExport).toHaveBeenCalled();
  });
});

describe("DataTable", () => {
  it("renders a captioned table with column headers", () => {
    render(
      <DataTable
        caption="Платежи"
        rows={[{ id: "A", amount: 1 }]}
        rowKey={(r) => r.id}
        columns={[
          { key: "id", header: "ID", cell: (r) => r.id },
          { key: "amount", header: "Сумма", cell: (r) => r.amount, numeric: true },
        ]}
      />,
    );
    const table = screen.getByRole("table", { name: "Платежи" });
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((h) => h.textContent),
    ).toEqual(["ID", "Сумма"]);
    expect(within(table).getByRole("cell", { name: "A" })).toBeInTheDocument();
  });
});
