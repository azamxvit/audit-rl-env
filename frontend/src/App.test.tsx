import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import App from "./App";
import { installFakeApi } from "./test/fakeApi";

async function startEpisode() {
  render(<App />);
  await userEvent.click(await screen.findByRole("button", { name: "Начать эпизод dev/00" }));
  await screen.findByRole("heading", { name: "Testa Logistics LLC", level: 1 });
}

describe("App (integration with a fake API)", () => {
  let api: ReturnType<typeof installFakeApi>;
  beforeEach(() => {
    api = installFakeApi(2);
  });

  it("has the page landmarks and lists episodes", async () => {
    render(<App />);
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Боковая панель" })).toBeInTheDocument();
    expect(screen.getByRole("search")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Выберите эпизод", level: 1 })).toBeInTheDocument();
    const card = await screen.findByRole("article", { name: "Testa Logistics LLC" });
    expect(within(card).getByText(/3 проводок/)).toBeInTheDocument();
  });

  it("shows the overview and the full step budget after starting", async () => {
    await startEpisode();
    expect(screen.getByText("100/100 шагов")).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: "Бюджет шагов" })).toHaveAttribute("value", "100");
    expect(screen.getByRole("heading", { name: "Сводка политики" })).toBeInTheDocument();
    expect(screen.getByRole("figure")).toHaveTextContent("Audit the books.");
  });

  it("charges one step per loaded page and keeps filtering free", async () => {
    await startEpisode();
    await userEvent.click(screen.getByRole("button", { name: "Главная книга" }));
    await userEvent.click(screen.getByRole("button", { name: /Загрузить первые 50/ }));
    await screen.findByRole("table", { name: /Главная книга: загружено 2 из 3/ });
    expect(screen.getByText("99/100 шагов")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Загрузить ещё 50/ }));
    await screen.findByRole("table", { name: /загружено 3 из 3/ });
    expect(screen.getByRole("button", { name: /Загрузить ещё 50/ })).toBeDisabled();
    await userEvent.type(screen.getByRole("searchbox", { name: /Фильтр/ }), "2200");
    expect(screen.getAllByRole("row")).toHaveLength(2); // header + one match
    expect(screen.getByText("98/100 шагов")).toBeInTheDocument();
  });

  it("opens a record, collects ids into the draft and submits to the review", async () => {
    await startEpisode();
    await userEvent.click(screen.getByRole("button", { name: "Платежи" }));
    await userEvent.click(screen.getByRole("button", { name: /Загрузить первые 50/ }));
    await userEvent.click(await screen.findByRole("button", { name: "DOC-PAY00001" }));
    const drawer = screen.getByRole("complementary", { name: "Запись PAY-00000001" });
    await userEvent.click(within(drawer).getByRole("button", { name: /в affected/ }));
    await userEvent.click(within(drawer).getByRole("button", { name: /в доказательства/ }));
    // linked invoice is not loaded yet -> costs a step
    await userEvent.click(within(drawer).getByRole("button", { name: /INV-00000001/ }));
    const invoiceDrawer = await screen.findByRole("complementary", { name: "Запись INV-00000001" });
    await userEvent.click(within(invoiceDrawer).getByRole("button", { name: /в affected/ }));
    expect(screen.getByText("98/100 шагов")).toBeInTheDocument();
    await userEvent.click(within(invoiceDrawer).getByRole("button", { name: "Закрыть" }));

    await userEvent.click(screen.getByRole("button", { name: /^Выводы/ }));
    const form = screen.getByRole("form", { name: "Новый вывод" });
    await userEvent.selectOptions(within(form).getByRole("combobox", { name: "Тип" }), "payment_allocation");
    await userEvent.type(
      within(form).getByRole("textbox", { name: /Добавить ID: Доказательства/ }),
      "LR-AAAA0002{Enter}",
    );
    await userEvent.type(within(form).getByRole("textbox", { name: /Сумма искажения/ }), "500");
    await userEvent.click(within(form).getByRole("button", { name: "Сохранить" }));
    expect(screen.getByRole("article", { name: "Вывод 1: Распределение платежа" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Отправить выводы/ }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Отправить" }));
    await screen.findByRole("heading", { name: "Разбор эпизода", level: 1 });
    expect(api.submissions).toEqual([
      {
        episode_id: "EP-TEST0001",
        findings: [
          {
            type: "payment_allocation",
            affected_ids: ["PAY-00000001", "INV-00000001"],
            claimed_amount_minor: 50000,
            currency: "USD",
            evidence_ids: ["DOC-PAY00001", "LR-AAAA0002"],
            explanation: "",
          },
        ],
      },
    ]);
    const table = screen.getByRole("table", { name: "Ошибки эталона и ваши ответы" });
    expect(within(table).getByText("Найдено")).toBeInTheDocument();
    expect(screen.queryByRole("toolbar", { name: "Действия с выводами" })).not.toBeInTheDocument();
  });

  it("searches by id from the top bar and reports environment errors", async () => {
    await startEpisode();
    await userEvent.type(
      screen.getByRole("searchbox", { name: /Найти запись по ID/ }),
      "DOC-INV00001{Enter}",
    );
    expect(await screen.findByRole("complementary", { name: "Запись INV-00000001" })).toBeInTheDocument();
    await userEvent.type(screen.getByRole("searchbox", { name: /Найти запись по ID/ }), "LR-NOPE{Enter}");
    await waitFor(() =>
      expect(screen.getByRole("status", { name: "Уведомления" })).toHaveTextContent("unknown_id"),
    );
    await userEvent.type(screen.getByRole("searchbox", { name: /Найти запись по ID/ }), "CUS-1{Enter}");
    await waitFor(() =>
      expect(screen.getByRole("status", { name: "Уведомления" })).toHaveTextContent("шаг не потрачен"),
    );
    expect(screen.getByText("98/100 шагов")).toBeInTheDocument();
  });

  it("shows calculator results as output and errors as alerts", async () => {
    await startEpisode();
    await userEvent.click(screen.getByRole("button", { name: "Калькулятор" }));
    const input = screen.getByRole("textbox", { name: "Выражение" });
    await userEvent.type(input, "1+2{Enter}");
    expect((await screen.findByText("= 3")).tagName).toBe("OUTPUT");
    await userEvent.type(input, "1/0{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("not computable");
  });
});
