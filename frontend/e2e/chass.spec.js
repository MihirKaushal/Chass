import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";

const photo = fileURLToPath(new URL("../../backend/tests/fixtures/board.png", import.meta.url));
const square = (page, row, col) => page.locator(`.board-grid [data-row="${row}"][data-col="${col}"]`);

async function preparePhoto(page) {
  await page.goto("/scanner");
  await expect(page.getByText("Scanner Ready", { exact: true })).toBeVisible();
  await page.getByLabel("Upload a board photo").setInputFiles(photo);
  await page.getByRole("button", { name: "Apply Photo Edits" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
}

async function reviewScan(page) {
  await preparePhoto(page);
  await page.getByRole("button", { name: "Recognize Pieces" }).click();
  await expect(page.getByRole("heading", { name: "Review Pieces", exact: true })).toBeVisible();
  await page.getByRole("button", { name: /White bishop.*90%/i }).click();
  await expect(square(page, 7, 5)).toHaveAttribute("aria-label", /white Bishop/);
}

test("local game moves and navigation confirmation", async ({ page }, testInfo) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Start Local Game", exact: true }).click();
  await square(page, 6, 4).click();
  await square(page, 4, 4).click();
  await expect(square(page, 4, 4)).toHaveAttribute("aria-label", /white Pawn/);
  await expect(page.locator(".turn-banner")).toContainText("Black");
  await page.getByRole("button", { name: "Home", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Leave This Game?");
  await page.getByRole("button", { name: "Stay In Game" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await testInfo.attach("layout-play", {
    body: await page.screenshot({ fullPage: true, animations: "disabled" }), contentType: "image/png",
  });
});

test("online seats survive refresh and moves synchronize across browsers", async ({ page, browser }) => {
  await page.goto("/");
  const created = page.waitForResponse((response) => response.url().endsWith("/game/create") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Create Online Game", exact: true }).click();
  const session = await (await created).json();
  const context = await browser.newContext();
  try {
    const friend = await context.newPage();
    await friend.goto(`http://127.0.0.1:14173/join/${session.inviteToken}`);
    await expect(friend.locator(".online-player-summary")).toContainText("Black");
    await page.reload();
    await expect(page.locator(".online-player-summary")).toContainText("You are playing as White");
    await square(page, 6, 4).click();
    await square(page, 4, 4).click();
    await expect(square(friend, 4, 4)).toHaveAttribute("aria-label", /white Pawn/);
    await square(friend, 1, 4).click();
    await square(friend, 3, 4).click();
    await expect(square(page, 3, 4)).toHaveAttribute("aria-label", /black Pawn/);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  } finally { await context.close(); }
});

for (const mode of ["local", "online"]) {
  test(`scanner upload, correction, confirmation and ${mode} import`, async ({ page }) => {
    await reviewScan(page);
    await page.getByRole("checkbox", { name: /I checked all 64 squares/ }).check();
    const launch = page.getByRole("button", { name: mode === "local" ? "Start Local Game" : "Create Online Game", exact: true });
    await expect(launch).toBeEnabled();
    await launch.click();
    await expect(page).toHaveURL(/\/game\//);
    await expect(square(page, 7, 5)).toHaveAttribute("aria-label", /white Bishop/);
  });
}

test("scanner keyboard editor navigates without painting until Enter and supports undo", async ({ page }) => {
  await reviewScan(page);
  await page.getByRole("button", { name: "Place white queen" }).click();
  await square(page, 3, 3).focus();
  await page.keyboard.press("ArrowRight");
  await expect(square(page, 3, 4)).toBeFocused();
  await expect(square(page, 3, 4)).toHaveAttribute("aria-label", "e5");
  await page.keyboard.press("Enter");
  await expect(square(page, 3, 4)).toHaveAttribute("aria-label", /white Queen/);
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(square(page, 3, 4)).toHaveAttribute("aria-label", "e5");
  await page.getByRole("button", { name: "Eraser", exact: true }).click();
  await square(page, 7, 4).click();
  await page.getByRole("checkbox", { name: /I checked all 64 squares/ }).check();
  await expect(page.getByRole("button", { name: "Start Local Game", exact: true })).toBeDisabled();
  await expect(page.locator(".scanner-import-feedback")).toContainText(/King/);
});

test("bad uploads and malformed scan responses remain recoverable", async ({ page }) => {
  await page.goto("/scanner");
  await page.getByLabel("Upload a board photo").setInputFiles({ name: "board.txt", mimeType: "text/plain", buffer: Buffer.from("no photo") });
  await expect(page.getByText("Choose a JPG, PNG, or WebP image.", { exact: true })).toBeVisible();
  await preparePhoto(page);
  await page.route("**/scanner/scan", (route) => route.fulfill({ json: { board: [], reviewSquares: [] } }));
  await page.getByRole("button", { name: "Recognize Pieces" }).click();
  await expect(page.getByText(/scanner returned an invalid board/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Recognize Pieces" })).toBeEnabled();
});

test("camera permission failure offers recovery without blocking upload", async ({ page }) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => { throw new DOMException("Denied", "NotAllowedError"); };
  });
  await page.goto("/scanner");
  await page.getByRole("button", { name: "Take A Photo" }).click();
  await expect(page.getByRole("dialog")).toContainText(/permission|access/i);
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("button", { name: "Upload Photo" })).toBeEnabled();
});

test("fake camera capture stops the media track and opens the editor", async ({ page }) => {
  await page.addInitScript(() => {
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async (...args) => {
      const stream = await original(...args);
      window.testCameraTracks = stream.getTracks();
      return stream;
    };
  });
  await page.goto("/scanner");
  await page.getByRole("button", { name: "Take A Photo" }).click();
  await page.getByRole("button", { name: "Capture Photo", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Crop & Rotate");
  expect(await page.evaluate(() => window.testCameraTracks.every((track) => track.readyState === "ended"))).toBe(true);
});

test("page layouts keep shared navigation and footer inside the viewport", async ({ page }, testInfo) => {
  for (const path of ["/", "/customize", "/scanner", "/rulebook"]) {
    await page.goto(path);
    await expect(page.locator(".site-footer")).toContainText("Developed by Mihir Kaushal");
    await expect(page.getByRole("navigation", { name: "Chass sections" })).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    if (path === "/" && testInfo.project.name === "desktop") {
      const footer = await page.locator(".site-footer").boundingBox();
      expect(footer.y + footer.height).toBeLessThanOrEqual(page.viewportSize().height + 1);
    }
    await testInfo.attach(`layout-${path.slice(1) || "home"}`, { body: await page.screenshot({ fullPage: true, animations: "disabled" }), contentType: "image/png" });
  }
});
