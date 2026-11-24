import { test, expect } from "@playwright/test";

test("scanner benchmarks open by default and can still be collapsed", async ({ page }) => {
  await page.goto("/rulebook#rulebook-scanner");
  const panel = page.locator(".scanner-performance");
  await expect(panel).toHaveAttribute("open", "");
  await expect(panel.getByText("Finding is not the same as identifying.", { exact: true })).toBeVisible();
  const toggle = panel.locator(":scope > summary");
  await toggle.click();
  await expect(panel).not.toHaveAttribute("open");
  await toggle.click();
  await expect(panel).toHaveAttribute("open", "");
  await expect(panel.locator(".scanner-benchmark-chart > li")).toHaveCount(4);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
});

test("page headings share a clear hierarchy without redundant labels", async ({ page }, testInfo) => {
  let titleSize;
  for (const [path, title] of [["/", "Chass!"], ["/customize", "Game Customizer"], ["/scanner", "AI Board Scanner"], ["/rulebook", "The Chass Rulebook"]]) {
    await page.goto(path);
    const heading = page.getByRole("heading", { level: 1, name: title, exact: true });
    await expect(heading).toBeVisible();
    await expect(page.locator("h1")).toHaveCount(1);
    await expect(page.locator(".page-heading-description")).toBeVisible();
    if (path === "/") {
      const tagline = page.locator(".page-heading-tagline");
      await expect(tagline).toHaveText("Build the rules. Play the board.");
      expect((await tagline.boundingBox()).y).toBeGreaterThan((await heading.boundingBox()).y);
      await expect(page.getByText("Classic chess when you want it.", { exact: false })).toHaveCount(0);
    } else {
      const size = await heading.evaluate((element) => getComputedStyle(element).fontSize);
      titleSize ??= size;
      expect(size).toBe(titleSize);
    }
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await testInfo.attach(`header-${path.slice(1) || "home"}`, {
      body: await page.screenshot({ animations: "disabled" }), contentType: "image/png",
    });
  }
});
