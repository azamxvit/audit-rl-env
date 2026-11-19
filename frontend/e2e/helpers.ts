import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const EPISODES = join(__dirname, "..", "..", "backend", "episodes");

export interface TruthIssue {
  type: string;
  affected_ids: string[];
  expected_amount_minor: number;
  currency: string;
  evidence_sets: string[][];
}

/** Grader-side helper: the open dev episodes ship their truth, the tests use it to know what to find. */
export function truthFor(key: string): { issues: TruthIssue[]; episodeId: string } {
  const index = JSON.parse(readFileSync(join(EPISODES, "index.json"), "utf8"));
  const [split, n] = key.split("/");
  const entry = index.episodes.filter((e: { split: string }) => e.split === split)[Number(n)];
  const truth = JSON.parse(readFileSync(join(EPISODES, entry.path, "private", "truth.json"), "utf8"));
  return { issues: truth.issues, episodeId: entry.episode_id };
}

export async function startEpisode(page: Page, key: string) {
  await page.goto("/");
  await page.getByRole("button", { name: `Начать эпизод ${key}` }).click();
  await expect(page.getByRole("heading", { level: 1 })).not.toHaveText("Выберите эпизод");
}

export async function budget(page: Page): Promise<number> {
  const text = await page
    .getByRole("banner")
    .getByText(/\d+\/100 шагов/)
    .textContent();
  return Number(text!.split("/")[0]);
}

/** Search by id in the top bar (1 step unless cached) and wait for the record drawer. */
export async function openById(page: Page, id: string) {
  const search = page.getByRole("searchbox", { name: /Найти запись по ID/ });
  await search.fill(id);
  await search.press("Enter");
  return page.getByRole("complementary", { name: /^Запись / });
}

export async function expectNoSeriousA11yViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`)).toEqual([]);
}
