export const SCANNER_REFERENCE = {
  title: "AI Board Scanner",
  description:
    "Scan a standard 8 x 8 board, review every square, then continue with another person locally or online. Recognition is experimental; bot imports are coming later.",
  entries: [
    {
      title: "Prepare Your Photo",
      text: "Upload a JPG, PNG, or WebP image up to 10 MB, or take a photo with your camera. Shoot directly above the board in even lighting, with all four corners visible and pieces centered in their squares. Rotate White's home rank to the bottom and crop to the 64-square playing grid before recognition.",
    },
    {
      title: "Review Every Square",
      text: "Select any square to highlight its location in the photo and inspect an enlarged crop. Gold markers need review; choose a suggestion, keep the current piece, or mark it empty. Use the palette and eraser for other corrections. Undo reverses edits; Restore Scan returns to recognition. Check all 64 squares, including empty ones, before continuing.",
    },
    {
      title: "Confirm The Position",
      text: "Defaults are White to move, no castling rights, no en passant target, halfmove clock 0, and move number 1. Change them only when known. Castling requires the original unmoved King and Rook on their home squares. En passant requires the opponent's immediately previous two-square Pawn move. Halfmove clock counts moves by either player since a Pawn move or capture. Earlier moves, captures, and repetition history cannot be recovered from a photo.",
    },
    {
      title: "How Recognition Works",
      text: "An SSDLite detector locates pieces, duplicate suppression merges competing detections, and a ResNet18 classifier examines detailed piece crops to identify type and color. Placement currently uses box centers on your cropped board. Tilted or tall pieces can map to a neighboring square, and unfamiliar chess sets can be misidentified.",
    },
    {
      title: "Understanding Uncertainty",
      text: "The default review thresholds are a piece-type model score below 70% or detection score below 50%. Boundary crossings, oversized detections, and competing pieces on one square are also flagged. Suggestions are ranked model scores, not calibrated probabilities of being correct. A square contains only your chosen piece; the other suggestions are alternatives, never extra pieces. Empty squares can contain missed pieces, so review them too.",
    },
    {
      title: "Continue Your Game",
      text: "After review, the server checks King counts, Pawn ranks, material limits, castling, en passant and legal turn order. The side to move may already be in check, but the side that just moved may not. Finished positions cannot be continued. Start Local Game shares one device; Create Online Game gives you White and an invite link/code for Black. Only classic chess and human opponents are supported. History, captured scores and repetition tracking start at import; a restart restores the imported position and its confirmed rights.",
    },
    {
      title: "Recognition Availability",
      text: "The page checks the recognition service through the Chass game API. If it is offline or not configured, photo preparation still works; Retry Connection checks again. A cold model host may take longer for its first scan. Recognition uses a separate model service and must be configured by the site operator for public use.",
    },
    {
      title: "Scan Details",
      text: "The summary counts detected pieces, unresolved flags, and squares changed from the original result. Review complete means you confirmed the board, not that AI verified it. Expand Scan Details for model versions, detected outlines, corrections, and separate connection, setup, and recognition timings. Active review time excludes hidden-tab and confirmed-board time.",
    },
    {
      title: "Performance & Limitations",
      text: "The benchmark below tracks piece-recognition progress, missed pieces, and false detections. Whole-board accuracy, occupancy, review effort, and unfamiliar-set performance need independently checked 64-square labels. Model scores are not calibrated probabilities.",
    },
    {
      title: "Photos And Reviewed Labels",
      text: "Server recognition sends the prepared photo through Chass and processes it in memory, without storing it or sending it to a third-party AI provider. On-device recognition downloads public models and processes locally; if it fails, it falls back to the server as described by the toggle. Starting a game saves the reviewed position, not the photo. Optional local exports include original predictions, corrections, model identifiers, and review time. Nothing is automatically uploaded for training. Exported labels must be checked again before benchmark use.",
    },
  ],
};
