import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";

const photo = fileURLToPath(new URL("../../backend/tests/fixtures/board.png", import.meta.url));
const square = (page, row, col) => page.locator(`.board-grid [data-row="${row}"][data-col="${col}"]`);

async function preparePhoto(page) {
  await page.goto("/scanner");
  await expect(page.getByText("Scanner ready", { exact: true })).toBeVisible();
  await page.getByLabel("Upload a board photo").setInputFiles(photo);
  await page.getByRole("button", { name: "Apply photo edits" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
}

async function reviewScan(page) {
  await preparePhoto(page);
  await page.getByRole("button", { name: "Recognize pieces" }).click();
  await expect(page.getByRole("heading", { name: "Review pieces", exact: true })).toBeVisible();
  await page.getByRole("button", { name: /White bishop.*90%/i }).click();
  await expect(square(page, 7, 5)).toHaveAttribute("aria-label", /white Bishop/);
}

test("local game moves and navigation confirmation", async ({ page }, testInfo) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Start local game", exact: true }).click();
  await square(page, 6, 4).click();
  await square(page, 4, 4).click();
  await expect(square(page, 4, 4)).toHaveAttribute("aria-label", /white Pawn/);
  await expect(page.locator(".turn-banner")).toContainText("Black");
  // The suite emulates prefers-reduced-motion, so decorative motion must be off.
  const boardAnimation = await page.locator(".board-wrap").evaluate(
    (element) => parseFloat(getComputedStyle(element).animationDuration)
  );
  expect(boardAnimation).toBeLessThan(0.001);
  await page.getByRole("link", { name: "Home", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Leave this game?");
  await page.getByRole("button", { name: "Stay in game" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await testInfo.attach("layout-play", {
    body: await page.screenshot({ fullPage: true, animations: "disabled" }), contentType: "image/png",
  });
});

test("a checked King is marked and the tab names the side to move", async ({ page }, testInfo) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Start local game", exact: true }).click();
  await expect(page).toHaveTitle("White to move | Chass!");
  // 1. e4 f5 2. Qh5+
  for (const [from, to, next] of [[[6, 4], [4, 4], "Black"], [[1, 5], [3, 5], "White"], [[7, 3], [3, 7], "Black"]]) {
    await square(page, ...from).click();
    await square(page, ...to).click();
    await expect(page.locator(".turn-banner")).toContainText(`${next} to move`);
  }
  const blackKing = square(page, 0, 4);
  await expect(blackKing).toHaveClass(/in-check/);
  await expect(blackKing).toHaveAttribute("aria-label", /black King, in check/);
  await expect(page.locator(".square.in-check")).toHaveCount(1);
  await expect(page).toHaveTitle("Black to move | Chass!");
  await testInfo.attach("king-in-check", {
    body: await page.locator(".board-wrap").screenshot({ animations: "disabled" }), contentType: "image/png",
  });
});

test("a same-device player can resign from the game menu", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Start local game", exact: true }).click();
  await expect(page.locator(".board-grid")).toBeVisible();
  await page.getByRole("button", { name: "Game settings" }).click();
  await page.getByRole("menuitem", { name: "Resign" }).click();
  const confirm = page.getByRole("dialog", { name: "Who is resigning?" });
  await confirm.getByRole("button", { name: "Keep playing" }).click();
  await expect(confirm).toHaveCount(0);

  await page.getByRole("button", { name: "Game settings" }).click();
  await page.getByRole("menuitem", { name: "Resign" }).click();
  await page.getByRole("button", { name: "White resigns" }).click();
  const result = page.getByRole("dialog", { name: "Match finished" });
  await expect(result).toContainText("Black won! White resigned.");
  await result.getByRole("button", { name: "Review board" }).click();
  await page.getByRole("button", { name: "Game settings" }).click();
  await expect(page.getByRole("menuitem", { name: "Resign" })).toHaveCount(0);
  await expect(page).toHaveTitle("Game over | Chass!");
});

test("home offers a way back into unfinished games", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Continue a game" })).toHaveCount(0);
  await page.getByRole("button", { name: "Start local game", exact: true }).click();
  await square(page, 6, 4).click();
  await square(page, 4, 4).click();
  await expect(page.locator(".turn-banner")).toContainText("Black to move");
  await page.getByRole("link", { name: "Home", exact: true }).click();
  await page.getByRole("button", { name: "Leave and go home" }).click();

  const resume = page.getByRole("link", { name: /Game on this device/ });
  await expect(resume).toContainText("Played just now");
  await expect(resume).toContainText("8 x 8 | Black to move");
  await expect(resume).toContainText("White Pawn e2-e4");
  await expect(resume.locator("time")).toHaveAttribute("datetime", /\d{4}-\d{2}-\d{2}T/);
  await testInfo.attach("home-resume", {
    body: await page.screenshot({ animations: "disabled" }), contentType: "image/png",
  });
  await resume.click();
  await expect(square(page, 4, 4)).toHaveAttribute("aria-label", /white Pawn/);

  await page.getByRole("button", { name: "Game settings" }).click();
  await page.getByRole("menuitem", { name: "Resign" }).click();
  await page.getByRole("button", { name: "Black resigns" }).click();
  await page.getByRole("dialog", { name: "Match finished" }).getByRole("button", { name: "Home" }).click();
  await expect(page.getByRole("heading", { name: "Chass!", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Continue a game" })).toHaveCount(0);
});

test("online seats survive refresh and moves synchronize across browsers", async ({ page, browser }) => {
  await page.goto("/");
  const created = page.waitForResponse((response) => response.url().endsWith("/game/create") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Create online game", exact: true }).click();
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
    await expect(page).toHaveTitle("Your move | Chass!");
    await expect(friend).toHaveTitle("Waiting for White | Chass!");
    // Neither online player sees engine evaluations while the game is live.
    for (const player of [page, friend]) {
      await expect(player.locator(".match-predictor .predictor-evaluation")).toHaveText("Hidden");
    }
    await page.getByRole("button", { name: "Game settings" }).click();
    await page.getByRole("menuitem", { name: "Offer a draw" }).click();
    await expect(page.locator(".draw-offer")).toContainText("Waiting for your opponent to answer.");
    await expect(friend.locator(".draw-offer")).toContainText("White offers a draw.");
    await friend.getByRole("button", { name: "Accept draw" }).click();
    for (const player of [page, friend]) {
      await expect(player.getByRole("dialog", { name: "Match finished" })).toContainText("drawn by agreement");
    }
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  } finally { await context.close(); }
});

for (const mode of ["local", "online"]) {
  test(`scanner upload, correction, confirmation and ${mode} import`, async ({ page }) => {
    await reviewScan(page);
    await page.getByRole("checkbox", { name: /I checked all 64 squares/ }).check();
    const launch = page.getByRole("button", { name: mode === "local" ? "Start local game" : "Create online game", exact: true });
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
  await expect(page.getByRole("button", { name: "Start local game", exact: true })).toBeDisabled();
  await expect(page.locator(".scanner-import-feedback")).toContainText(/King/);
});

test("scanner palette pieces toggle off without painting the next inspected square", async ({ page }) => {
  await reviewScan(page);
  const whiteQueen = page.getByRole("button", { name: "Place white queen" });
  const blackQueen = page.getByRole("button", { name: "Place black queen" });
  await whiteQueen.click();
  await expect(whiteQueen).toHaveAttribute("aria-pressed", "true");
  await blackQueen.click();
  await expect(whiteQueen).toHaveAttribute("aria-pressed", "false");
  await expect(blackQueen).toHaveAttribute("aria-pressed", "true");
  await blackQueen.click();
  await expect(blackQueen).toHaveAttribute("aria-pressed", "false");
  await square(page, 3, 3).click();
  await expect(square(page, 3, 3)).toHaveAttribute("aria-label", "d5");
});

test("scanner review advances after corrections or confirmation and supports undo", async ({ page }, testInfo) => {
  await preparePhoto(page);
  await page.route("**/scanner/scan", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.reviewSquares.push(
      { row: 5, col: 0, label: "a3", reasons: ["Check empty square"] },
      { row: 6, col: 2, label: "c2", reasons: ["Check piece"] },
    );
    await route.fulfill({ response, json: data });
  });
  await page.getByRole("button", { name: "Recognize pieces" }).click();
  const heading = page.locator(".scanner-alternatives h3");
  const confirmation = page.getByRole("checkbox", { name: /I checked all 64 squares/ });
  await expect(heading).toHaveText("Review a3");
  await page.getByRole("button", { name: "This square is empty (Current)", exact: true }).click();
  await expect(heading).toHaveText("Review c2");
  await expect(page.getByRole("button", { name: /White pawn.*Current piece/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Mark c2 Correct", exact: true })).toHaveCount(1);
  await testInfo.attach("scanner-current-piece", { body: await page.locator(".scanner-alternatives").screenshot(), contentType: "image/png" });
  await page.getByRole("button", { name: "Mark c2 Correct", exact: true }).click();
  await expect(heading).toHaveText("Review f1");
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(heading).toHaveText("Review c2");
  await page.getByRole("button", { name: "Mark c2 Correct", exact: true }).click();
  await page.getByRole("button", { name: /White bishop.*90%/i }).click();
  await expect(page.locator(".scanner-review-status")).toContainText("No more squares to review");
  await expect(page.locator(".scanner-review-status")).toContainText("missing pieces, wrong pieces, and incorrect colors");
  await expect(confirmation).toBeEnabled();
  await expect(confirmation).not.toBeChecked();
  await confirmation.check();
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(heading).toHaveText("Review f1");
  await expect(confirmation).toBeDisabled();
  await expect(confirmation).not.toBeChecked();
  const bishopTool = page.getByRole("button", { name: "Place white bishop" });
  await bishopTool.click();
  await square(page, 7, 5).click();
  await expect(bishopTool).toHaveAttribute("aria-pressed", "false");
  await expect(page.locator(".scanner-review-status")).toContainText("No more squares to review");
  await page.getByRole("button", { name: "Restore scan", exact: true }).click();
  await expect(heading).toHaveText("Review a3");
  await expect(page.locator(".scanner-review-status")).toContainText("3 squares to review");
  await page.getByRole("button", { name: "Place white queen", exact: true }).click();
  await page.getByRole("button", { name: "Mark all pieces reviewed", exact: true }).click();
  await expect(page.locator(".scanner-review-status")).toContainText("No more squares to review");
  await expect(page.getByRole("button", { name: "Mark all pieces reviewed", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Place white queen", exact: true })).toHaveAttribute("aria-pressed", "false");
  await expect(confirmation).toBeEnabled();
  await expect(confirmation).not.toBeChecked();
  await expect(square(page, 7, 5)).toHaveAttribute("aria-label", /white Pawn/);
  await confirmation.check();
  // Bulk review does not bypass the independent imported-position validator.
  await expect(page.getByRole("button", { name: "Start local game", exact: true })).toBeDisabled();
  await expect(page.locator(".scanner-import-feedback")).toContainText(/first or last rank/i);
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.locator(".scanner-review-status")).toContainText("3 squares to review");
  await expect(heading).toHaveText("Review a3");
  await expect(confirmation).not.toBeChecked();
  await expect(confirmation).toBeDisabled();
});

test("bad uploads and malformed scan responses remain recoverable", async ({ page }) => {
  await page.goto("/scanner");
  await page.getByLabel("Upload a board photo").setInputFiles({ name: "board.txt", mimeType: "text/plain", buffer: Buffer.from("no photo") });
  await expect(page.getByText("Choose a JPG, PNG, or WebP image.", { exact: true })).toBeVisible();
  await preparePhoto(page);
  await page.route("**/scanner/scan", (route) => route.fulfill({ json: { board: [], reviewSquares: [] } }));
  await page.getByRole("button", { name: "Recognize pieces" }).click();
  await expect(page.getByText(/scanner returned an invalid board/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Recognize pieces" })).toBeEnabled();
});

test("camera permission failure offers recovery without blocking upload", async ({ page }) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => { throw new DOMException("Denied", "NotAllowedError"); };
  });
  await page.goto("/scanner");
  await page.getByRole("button", { name: "Take a photo" }).click();
  await expect(page.getByRole("dialog")).toContainText(/permission|access/i);
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("button", { name: "Upload photo" })).toBeEnabled();
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
  await page.getByRole("button", { name: "Take a photo" }).click();
  await page.getByRole("button", { name: "Capture photo", exact: true }).click();
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

test("an unusable invite explains itself without a pointless retry", async ({ page }) => {
  await page.goto("/join/ZZZZ2222");
  await expect(page.getByRole("heading", { name: "Unable to join" })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("Invite link is invalid");
  await expect(page.getByText("Ask the host for a new invite link or code.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" })).toHaveCount(0);
  await expect(page.locator(".site-footer")).toBeVisible();
  await page.getByRole("button", { name: "Back home" }).click();
  const sections = page.getByRole("navigation", { name: "Chass sections" });
  for (const [name, href] of [["Home", "/"], ["Customize", "/customize"], ["Scanner", "/scanner"], ["Rulebook", "/rulebook"]]) {
    await expect(sections.getByRole("link", { name, exact: true })).toHaveAttribute("href", href);
  }
});

test("a move can be played from the keyboard with one tab stop on the board", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Start local game", exact: true }).click();
  const squares = page.locator(".board-grid button.square");
  await expect(squares).toHaveCount(64);
  await expect(page.locator('.board-grid button.square[tabindex="0"]')).toHaveCount(1);

  await page.locator('.board-grid button.square[tabindex="0"]').focus();
  for (let step = 0; step < 6; step += 1) await page.keyboard.press("ArrowDown");
  for (let step = 0; step < 4; step += 1) await page.keyboard.press("ArrowRight");
  await expect(square(page, 6, 4)).toBeFocused();
  await page.keyboard.press("Enter");
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("ArrowUp");
  await expect(square(page, 4, 4)).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(square(page, 4, 4)).toHaveAttribute("aria-label", /white Pawn/);
  await expect(page.locator(".turn-banner")).toContainText("Black to move");
});

test("same-device players can decline and then agree a draw", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Start local game", exact: true }).click();
  await expect(page.locator(".board-grid")).toBeVisible();
  const offer = async () => {
    await page.getByRole("button", { name: "Game settings" }).click();
    await page.getByRole("menuitem", { name: "Offer a draw" }).click();
  };
  await offer();
  await expect(page.locator(".draw-offer")).toContainText("White offers a draw.");
  await page.getByRole("button", { name: "Black declines" }).click();
  await expect(page.locator(".draw-offer")).toHaveCount(0);
  await offer();
  await page.getByRole("button", { name: "Black accepts" }).click();
  await expect(page.getByRole("dialog", { name: "Match finished" })).toContainText("The game is drawn by agreement.");
});

test("same-device players can take back a move", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Start local game", exact: true }).click();
  await page.getByRole("button", { name: "Game settings" }).click();
  await expect(page.getByRole("menuitem", { name: "Take back move" })).toHaveCount(0);
  await page.keyboard.press("Escape");

  await square(page, 6, 4).click();
  await square(page, 4, 4).click();
  await expect(page.locator(".turn-banner")).toContainText("Black to move");
  await page.getByRole("button", { name: "Game settings" }).click();
  await page.getByRole("menuitem", { name: "Take back move" }).click();
  await expect(page.locator(".turn-banner")).toContainText("White to move");
  await expect(square(page, 6, 4)).toHaveAttribute("aria-label", /white Pawn/);
  await expect(square(page, 4, 4)).not.toHaveAttribute("aria-label", /Pawn/);
  // Auto flip turns the board back toward White after the takeback.
  const firstRow = await page.locator(".board-grid button.square").first().getAttribute("data-row");
  expect(firstRow).toBe("0");
});

test("standard local positions can be copied as FEN or opened on Lichess", async ({ page, context }, testInfo) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  await page.getByRole("button", { name: "Start local game", exact: true }).click();
  await square(page, 6, 4).click();
  await square(page, 4, 4).click();
  await expect(page.locator(".turn-banner")).toContainText("Black to move");
  await page.getByRole("button", { name: "Game settings" }).click();
  const lichess = page.getByRole("menuitem", { name: "Analyze on Lichess" });
  await expect(lichess).toHaveAttribute(
    "href",
    /lichess\.org\/analysis\/standard\/rnbqkbnr\/pppppppp\/8\/8\/4P3\/8\/PPPP1PPP\/RNBQKBNR_b_KQkq_/
  );
  await expect(lichess).toHaveAttribute("target", "_blank");
  await testInfo.attach("game-settings-menu", {
    body: await page.screenshot({ animations: "disabled" }), contentType: "image/png",
  });
  await page.getByRole("menuitem", { name: "Copy FEN" }).click();
  await expect(page.locator(".sync-message")).toHaveText("Position copied as FEN.");
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toMatch(/^rnbqkbnr\/pppppppp\/8\/8\/4P3\/8\/PPPP1PPP\/RNBQKBNR b KQkq/);
});

test("resuming restores Black's auto-flipped view and remembered settings", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Start local game", exact: true }).click();
  await square(page, 6, 4).click();
  await square(page, 4, 4).click();
  await expect(page.locator(".turn-banner")).toContainText("Black to move");
  const firstSquare = page.locator(".board-grid [data-row]").first();
  await expect(firstSquare).toHaveAttribute("data-row", "7");
  await page.reload();
  await expect(firstSquare).toHaveAttribute("data-row", "7");
  const settings = page.getByRole("button", { name: "Game settings" });
  await settings.click();
  await page.getByRole("menuitemcheckbox", { name: "Auto flip: On" }).click();
  await settings.click();
  await page.getByRole("menuitem", { name: "Flip board", exact: true }).click();
  await expect(firstSquare).toHaveAttribute("data-row", "0");
  await settings.click();
  await page.getByRole("menuitemcheckbox", { name: "Match Analysis: Enabled" }).click();
  await settings.click();
  await page.getByRole("menuitemcheckbox", { name: "Mute game sounds" }).click();
  await page.reload();
  await expect(firstSquare).toHaveAttribute("data-row", "0");
  await settings.click();
  await expect(page.getByRole("menuitemcheckbox", { name: "Auto flip: Off" })).toBeVisible();
  await expect(page.getByRole("menuitemcheckbox", { name: "Match Analysis: Disabled" })).toBeVisible();
  await expect(page.getByRole("menuitemcheckbox", { name: "Unmute game sounds" })).toBeVisible();
  await page.getByRole("menuitemcheckbox", { name: "Auto flip: Off" }).click();
  await expect(firstSquare).toHaveAttribute("data-row", "7");
});

test("recent-game cards use the right column for moves when space allows", async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.setItem("chass:recent-games", JSON.stringify(
    [1, 2, 3].map((id) => ({ gameId: `sample-${id}`, mode: "local", updatedAt: Date.now(),
      summary: "8 x 8 | Black to move", recentMoves: ["1. White Pawn e2-e4", "2. Black Pawn e7-e5", "3. White Knight g1-f3"],
    }))
  )));
  await page.goto("/");
  const card = page.locator(".resume-game-link").first();
  await expect(card).toBeVisible();
  if (testInfo.project.name === "desktop") {
    const details = await card.locator(".resume-game-details").boundingBox();
    const moves = await card.locator(".resume-game-moves").boundingBox();
    expect(moves.x).toBeGreaterThan(details.x + details.width);
  }
  await testInfo.attach("recent-game-columns", { body: await page.screenshot(), contentType: "image/png" });
});
