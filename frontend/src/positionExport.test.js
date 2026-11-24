import assert from "node:assert/strict";
import test from "node:test";

import { lichessAnalysisUrl } from "./positionExport.js";

test("lichess links keep FEN ranks as path segments with underscores for spaces", () => {
  assert.equal(
    lichessAnalysisUrl("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"),
    "https://lichess.org/analysis/standard/rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR_b_KQkq_e3_0_1"
  );
  assert.equal(lichessAnalysisUrl(null), null);
  assert.equal(lichessAnalysisUrl(""), null);
});
