import { expect, test } from "@playwright/test";
import { budget, expectNoSeriousA11yViolations, openById, startEpisode, truthFor } from "./helpers";

const KEY = "dev/04";

test.describe("AuditDesk end to end", () => {
  test("episode list is accessible and hides the answers", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Выберите эпизод", level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Начать эпизод / })).toHaveCount(20);
    await expect(page.getByRole("navigation", { name: "Основная навигация" })).toBeVisible();
    await expect(page.getByRole("main")).not.toContainText("ISS-");
    await expectNoSeriousA11yViolations(page);
  });

  test("table pages cost one step each; filtering is free", async ({ page }) => {
    await startEpisode(page, KEY);
    expect(await budget(page)).toBe(100);
    await page.getByRole("button", { name: "Главная книга" }).click();
    await page.getByRole("button", { name: /Загрузить первые 50/ }).click();
    await expect(page.getByRole("table", { name: /загружено 50 из/ })).toBeVisible();
    await page.getByRole("button", { name: /Загрузить ещё 50/ }).click();
    await expect(page.getByRole("table", { name: /загружено 100 из/ })).toBeVisible();
    expect(await budget(page)).toBe(98);
    await page.getByRole("searchbox", { name: /Фильтр/ }).fill("2200");
    expect(await budget(page)).toBe(98);
    await expectNoSeriousA11yViolations(page);
  });

  test("an auditor can find an issue, submit it and see it matched in the review", async ({ page }) => {
    const { issues } = truthFor(KEY);
    const issue = issues.find((i) => i.type === "payment_allocation")!;
    const [docId, rowId] = issue.evidence_sets[0];
    const paymentId = issue.affected_ids.find((x) => x.startsWith("PAY-"))!;
    const invoiceId = issue.affected_ids.find((x) => x.startsWith("INV-"))!;

    await startEpisode(page, KEY);
    let drawer = await openById(page, docId);
    await expect(drawer).toHaveAccessibleName(`Запись ${paymentId}`);
    await drawer.getByRole("button", { name: /в affected/ }).click();
    await drawer.getByRole("button", { name: /в доказательства/ }).click();
    await drawer.getByRole("button", { name: new RegExp(invoiceId) }).click(); // linked ref, 1 step
    drawer = page.getByRole("complementary", { name: `Запись ${invoiceId}` });
    await drawer.getByRole("button", { name: /в affected/ }).click();
    drawer = await openById(page, rowId);
    await expect(drawer).toHaveAccessibleName(`Запись ${rowId}`);
    await drawer.getByRole("button", { name: /в доказательства/ }).click();
    await drawer.getByRole("button", { name: "Закрыть" }).click();
    expect(await budget(page)).toBe(97);

    await page.getByRole("button", { name: /^Выводы/ }).click();
    const form = page.getByRole("form", { name: "Новый вывод" });
    await form.getByRole("combobox", { name: "Тип" }).selectOption("payment_allocation");
    const major = (issue.expected_amount_minor / 100).toFixed(2);
    await form.getByRole("textbox", { name: /Сумма искажения/ }).fill(major);
    await form.getByRole("button", { name: "Сохранить" }).click();
    await expect(page.getByRole("article", { name: "Вывод 1: Распределение платежа" })).toBeVisible();
    await expectNoSeriousA11yViolations(page);

    await page.getByRole("button", { name: /Отправить выводы/ }).click();
    const dialog = page.getByRole("dialog", { name: /Отправить 1 вывод/ });
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Отправить" }).click();

    await expect(page.getByRole("heading", { name: "Разбор эпизода", level: 1 })).toBeVisible();
    const table = page.getByRole("table", { name: "Ошибки эталона и ваши ответы" });
    await expect(table.getByRole("row")).toHaveCount(issues.length + 1);
    const matched = table.getByRole("row").filter({ hasText: paymentId }).filter({ hasText: invoiceId });
    await expect(matched).toContainText("Найдено");
    await expect(page.getByText("TP 1")).toBeVisible();
    // reward = 2*F1 - 1 - 0.002*3 with one of N issues found
    const f1 = 2 / (issues.length + 1);
    await expect(page.getByText((2 * f1 - 1 - 0.006).toFixed(3), { exact: true })).toBeVisible();
    await expect(page.getByRole("toolbar", { name: "Действия с выводами" })).toHaveCount(0);
    await expectNoSeriousA11yViolations(page);
  });

  test("keyboard only: search a record and close it", async ({ page }) => {
    await startEpisode(page, KEY);
    await page.getByRole("searchbox", { name: /Найти запись по ID/ }).focus();
    await page.keyboard.type("LR-DOES0NOT");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("status", { name: "Уведомления" })).toContainText("unknown_id");
    expect(await budget(page)).toBe(99);
    await page.getByRole("button", { name: "Калькулятор" }).focus();
    await page.keyboard.press("Enter");
    await page.getByRole("textbox", { name: "Выражение" }).fill("100.00 * 1.084512");
    await page.keyboard.press("Enter");
    await expect(page.locator("output")).toHaveText("= 108.4512");
  });
});
