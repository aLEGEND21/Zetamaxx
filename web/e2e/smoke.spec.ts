import { clerk } from "@clerk/testing/playwright";
import { expect, test, type Browser, type Page } from "@playwright/test";
import { SOCIAL } from "../lib/features";
import { E2E_USERS } from "./global-setup";

type Player = { page: Page; username: string };

async function signIn(browser: Browser, emailAddress: string): Promise<Player> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("/");
  await clerk.signIn({ page, emailAddress });
  await page.reload();
  await expect(page.getByRole("link", { name: "Profile" })).toBeVisible();
  const me = await page.evaluate(async () => (await fetch("/api/me")).json());
  return { page, username: me.username };
}

/** Plays one full ranked game, answering every `paceMs` through the game's test hook. */
async function playRankedGame(page: Page, paceMs: number): Promise<number> {
  await page.goto("/"); // opening the page starts a game
  await expect(page.getByTestId("problem")).not.toBeEmpty();
  const finalScore = page.getByTestId("final-score");
  while (!(await finalScore.isVisible())) {
    await page.waitForTimeout(paceMs);
    const answer = await page.evaluate(() => (window as unknown as { __zetamaxx: { answer(): string | null } }).__zetamaxx.answer());
    if (answer !== null && (await page.getByTestId("answer").isVisible())) await page.keyboard.type(answer);
  }
  // A first game on a fresh database is always a personal best, and the badge only shows once it is saved.
  await expect(page.getByTestId("pb-badge")).toBeVisible();
  return Number(await finalScore.textContent());
}

test("sign in, play, see the game on the profile, and (when groups are on) compare in a group", async ({ browser }) => {
  const one = await signIn(browser, E2E_USERS[0]);
  const two = await signIn(browser, E2E_USERS[1]);

  // Both play at the same time, at different speeds, so the test takes two minutes rather than four.
  const [scoreOne, scoreTwo] = await Promise.all([playRankedGame(one.page, 800), playRankedGame(two.page, 1500)]);
  expect(scoreOne).toBeGreaterThan(scoreTwo);
  expect(scoreTwo).toBeGreaterThan(20);

  // Enter on the results starts the next game with the answer box focused. (It is abandoned below.)
  await two.page.keyboard.press("Enter");
  await expect(two.page.getByTestId("problem")).not.toBeEmpty();
  await expect(two.page.getByTestId("answer")).toBeFocused();
  await expect(two.page.getByTestId("score")).toHaveText("Score 0");

  // The game shows up on the player's profile.
  await one.page.goto(`/u/${one.username}`);
  const pbTile = one.page.locator("div", { has: one.page.getByText("Personal best", { exact: true }) }).last();
  await expect(pbTile).toContainText(String(scoreOne));
  const history = one.page.locator("section", { hasText: "Recent games" });
  await expect(history.getByRole("link").first()).toContainText(String(scoreOne));

  if (!SOCIAL) {
    // Friends and groups are switched off: no nav links, and their pages do not exist.
    await expect(one.page.getByRole("link", { name: "Groups" })).toHaveCount(0);
    await expect(one.page.getByRole("link", { name: "Friends" })).toHaveCount(0);
    expect((await one.page.goto("/groups"))?.status()).toBe(404);
    return;
  }

  // Player one creates a group and copies its invite link.
  await one.page.goto("/groups");
  await one.page.getByLabel("Name").fill(`E2E ${Date.now()}`);
  await one.page.getByRole("button", { name: "Create group" }).click();
  await one.page.waitForURL(/\/groups\/[0-9a-f-]{20,}/);
  const inviteLink = await one.page.getByLabel("Invite link").inputValue();
  expect(inviteLink).toContain("/join/");

  // Player two joins through the link.
  await two.page.goto(inviteLink);
  await two.page.getByRole("button", { name: "Join group" }).click();
  await two.page.waitForURL(/\/groups\/[0-9a-f-]{20,}/);

  // Both are on the leaderboard, ranked by their scores.
  await one.page.reload();
  const rows = one.page.locator("section", { hasText: "Leaderboard" }).locator("tbody tr");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText(one.username);
  await expect(rows.nth(0)).toContainText(String(scoreOne));
  await expect(rows.nth(1)).toContainText(two.username);
  await expect(rows.nth(1)).toContainText(String(scoreTwo));
});
