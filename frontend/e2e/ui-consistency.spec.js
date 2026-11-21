import { test, expect } from "@playwright/test";

test("room actions share a hierarchy and customizer navigation remains keyboard accessible", async ({ page }, testInfo) => {
  await page.goto("/");
  const cards = page.locator(".mode-choice-card");
  await expect(cards).toHaveCount(2);
  expect(await cards.nth(0).evaluate((el) => getComputedStyle(el).backgroundColor))
    .toBe(await cards.nth(1).evaluate((el) => getComputedStyle(el).backgroundColor));
  for (const label of ["Start local game", "Create online game"]) {
    await expect(page.getByRole("button", { name: label, exact: true })).toHaveClass(/ui-button--primary/);
  }
  for (const label of ["Play against a bot", "Enter invite code"]) {
    await expect(page.getByRole("button", { name: label, exact: true })).toHaveClass(/ui-button--secondary/);
  }
  await page.goto("/customize");
  const search = page.getByRole("combobox", { name: "Search customize sections and settings" });
  await search.fill("Catapult");
  await search.press("ArrowDown");
  await expect(search).toHaveAttribute("aria-activedescendant", /customize-jump-result-/);
  const result = page.locator(".customize-jump-options a.keyboard-active");
  await expect(result).toBeVisible();
  await expect(result).toHaveCSS("color", "rgb(26, 54, 93)");
  await testInfo.attach("customize-navigation", {
    body: await page.screenshot({ animations: "disabled" }), contentType: "image/png",
  });
  await search.press("Enter");
  await expect(page.locator(".customize-search-highlight")).toBeVisible();
  await expect(page.locator(".tuning-fieldset").first()).toHaveCSS("border-left-width", "0px");
  await expect(page.getByRole("button", { name: "Play against a bot", exact: true })).toHaveClass(/ui-button--secondary/);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
});
