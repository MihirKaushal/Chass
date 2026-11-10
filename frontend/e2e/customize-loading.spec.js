import { test, expect } from "@playwright/test";

test("customizer renders and edits before a sleeping server responds", async ({ page }, testInfo) => {
  let catalogRequests = 0;
  await page.route("**/game/catalog", (route) => { catalogRequests += 1; return route.abort(); });
  let release;
  const held = new Promise((resolve) => { release = resolve; });
  await page.route("**/game/validate", async (route) => {
    await held;
    await route.abort().catch(() => {});
  });
  try {
    const start = Date.now();
    await page.goto("/customize");
    await expect(page.locator(".studio-board")).toBeVisible();
    await expect(page.locator(".skeleton-customize-body")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Start Local Game", exact: true })).toBeDisabled();
    await page.getByLabel("Rows", { exact: true }).fill("10");
    await expect(page.locator(".studio-square")).toHaveCount(80);
    await page.getByText("Enable Special Abilities", { exact: true }).click();
    await expect(page.getByLabel("Enable Special Abilities", { exact: false })).toBeChecked();
    await expect(page.getByText("Necromancy", { exact: true }).first()).toBeVisible();
    expect(catalogRequests).toBe(0);
    await testInfo.attach("customizer-before-server-response", {
      body: JSON.stringify({ editable_ms: Date.now() - start, catalog_requests: catalogRequests }),
      contentType: "application/json",
    });
  } finally { release(); }
});

test("failed validation can retry without losing edits or bypassing checks", async ({ page }) => {
  await page.route("**/game/validate", (route) => route.abort());
  await page.goto("/customize");
  await page.getByLabel("Rows", { exact: true }).fill("10");
  await expect(page.getByText("Server Unavailable", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start Local Game", exact: true })).toBeDisabled();
  await page.unroute("**/game/validate");
  await page.getByRole("button", { name: "Retry Check" }).click();
  await expect(page.getByRole("button", { name: "Start Local Game", exact: true })).toBeEnabled();
  await expect(page.getByLabel("Rows", { exact: true })).toHaveValue("10");
  await page.getByRole("button", { name: "Start Local Game", exact: true }).click();
  await expect(page).toHaveURL(/\/game\//);
  await expect(page.locator(".board-grid [data-row]")).toHaveCount(80);
});

test("a stalled validation times out without blocking the editor", async ({ page }) => {
  let release;
  const held = new Promise((resolve) => { release = resolve; });
  await page.route("**/game/validate", async (route) => {
    await held;
    await route.abort().catch(() => {});
  });
  try {
    await page.clock.install();
    const started = page.waitForRequest("**/game/validate");
    await page.goto("/customize");
    await page.clock.fastForward(300);
    await started;
    await page.clock.fastForward(66000);
    await expect(page.getByText("Server Unavailable", { exact: true })).toBeVisible();
    await expect(page.getByText("The game server is taking longer than expected. Please retry the check.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Start Local Game", exact: true })).toBeDisabled();
    await page.getByLabel("Rows", { exact: true }).fill("10");
    await expect(page.locator(".studio-square")).toHaveCount(80);
    await expect(page.getByText("Checking Setup", { exact: true })).toBeVisible();
  } finally { release(); }
});

test("customizer restores edits across the Rulebook and imports settings under StrictMode", async ({ page }) => {
  await page.addInitScript(() => {
    if (!sessionStorage.getItem("test-import-seeded")) {
      sessionStorage.setItem("test-import-seeded", "true");
      sessionStorage.setItem("chass-customize-draft", JSON.stringify({ boardRows: 10, boardCols: 12, configuration: {} }));
    }
  });
  await page.goto("/customize");
  await expect(page.locator(".studio-square")).toHaveCount(120);
  await page.getByLabel("Rows", { exact: true }).fill("12");
  await page.getByRole("link", { name: "Open Rulebook", exact: true }).click();
  await expect(page).toHaveURL(/\/rulebook/);
  await page.getByRole("navigation", { name: "Chass sections" }).getByRole("button", { name: "Customize", exact: true }).click();
  await expect(page.getByLabel("Rows", { exact: true })).toHaveValue("12");
  await expect(page.locator(".studio-square")).toHaveCount(144);
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
