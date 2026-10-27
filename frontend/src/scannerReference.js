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
      text: "Gold question marks indicate uncertain squares. Click one to see ranked alternatives and choose the piece in your photo, keep the current piece, or mark it empty. You can also use the palette and eraser to correct any square, even unflagged ones. Undo reverses edits; Restore Scan returns to the model's result. Every flagged square must be resolved, and you must check all 64 squares before continuing.",
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
      title: "Photos And Reviewed Labels",
      text: "Photos stay in your browser until Recognize Pieces sends the cropped image through Chass to its model service. Images are processed in memory, not stored in the game database or sent to a third-party AI provider. Starting a game saves the reviewed position and game details, not the photo. Save Prepared Photo and Export Reviewed Labels download files for accuracy testing; they do not automatically train the model.",
    },
  ],
};
