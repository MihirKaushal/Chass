export const SCANNER_REFERENCE = {
  title: "AI Board Scanner",
  description:
    "Scan a standard 8 x 8 board, review the result, and continue locally or online. Recognition is experimental; human opponents only.",
  entries: [
    {
      title: "Prepare Your Photo",
      text: "Take a top-down photo in even lighting with all four corners visible. Upload JPG, PNG, or WebP (up to 10 MB), rotate White's home rank to the bottom, and crop to the 64-square grid.",
    },
    {
      title: "Review Every Square",
      text: "Select a square to compare it with the photo. Gold markers flag uncertainty; choose a suggestion, use the piece palette, or erase. Check empty squares too. Undo reverses edits; Restore Scan returns to the original result. Scan Details shows models, corrections, and timing.",
    },
    {
      title: "Confirm The Position",
      text: "Choose whose turn it is. Defaults: White, no castling or en passant, halfmove clock 0, move number 1. Only enable castling for an unmoved King and Rook; en passant requires the opponent's immediately previous two-square Pawn move. Halfmoves count turns since a Pawn move or capture. A photo cannot recover earlier history.",
    },
    {
      title: "Continue Your Game",
      text: "Chass validates the position before you start. The side to move may be in check; the other King may not. Finished games cannot be imported. Play on one device or create an online room as White and invite Black. Tracking starts at import; restarting restores the imported position.",
    },
  ],
  performance: {
    method: "An SSDLite detector locates pieces, duplicate suppression removes competing boxes, and a fine-tuned ResNet18 classifies each crop by type and color. Box centers assign pieces to squares on the prepared board.",
    trainingData: {
      description: "Training photos mainly show black and white chess pieces on green and white boards. Similar piece styles, board colors, and top-down views are expected to give the best results. Other setups may need more manual correction; always check all 64 squares.",
      sourceLabel: "Chess V2 by Public Wspace",
      sourceUrl: "https://universe.roboflow.com/public-wspace/chess-v2-qqtmk",
      license: "CC BY 4.0",
      licenseUrl: "https://creativecommons.org/licenses/by/4.0/",
      preparation: "Chass uses a curated version with duplicate photos removed and labels and orientation corrected.",
    },
    evaluation: "Predictions are matched to annotated boxes without using piece labels, with at least 50% overlap (intersection over union, or IoU). Type and color are then checked on matched pieces. The curated ChessV2 test collection has been reused during development, so these are regression results, not a fresh test of unseen chess sets.",
    uncertainty: "Review flags use default model-score thresholds: below 70% for type or 50% for detection. Boundary crossings, oversized boxes, and competing pieces also trigger review. Scores rank suggestions; they are not calibrated probabilities. Review complete means you confirmed the board, not that AI verified it.",
    timing: "Scan Details separates connection/startup wait, model setup, and recognition. Cold starts can delay the first scan; device and server timings are not directly comparable. If recognition is offline, photo preparation still works and Retry Connection checks again.",
    privacy: "Server recognition processes the prepared photo in memory without storing it or sending it to a third-party AI provider. On-device recognition downloads models; if it fails, the photo is sent to the server as disclosed by the toggle. A game saves the reviewed position, not the photo. Optional local exports contain predictions, corrections, model identifiers, and review time; nothing is automatically uploaded for training. Recheck exported labels before benchmark use.",
  },
};
