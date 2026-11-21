import { test, expect } from "@playwright/test";

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
