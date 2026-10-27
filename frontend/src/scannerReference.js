export const SCANNER_REFERENCE = {
  title: "AI Board Scanner",
  description:
    "Turn a photo of a standard 8 x 8 board into an editable position. Recognition is experimental; continuing the position as a game is not available yet.",
  entries: [
    {
      title: "Prepare Your Photo",
      text: "Upload a JPG, PNG, or WebP image up to 10 MB, or take a photo with your camera. Shoot directly above the board in even lighting, with all four corners visible and pieces centered in their squares. Rotate White's home rank to the bottom and crop to the 64-square playing grid before recognition.",
    },
    {
      title: "Review Every Square",
      text: "Gold markers indicate uncertain placements, not every possible error. Check piece types, colors, and empty squares too. Choose a piece or the eraser, then click the board to correct it. Undo reverses edits; Restore Scan returns to the model's original result.",
    },
    {
      title: "Confirm The Position",
      text: "A photo cannot reveal whose turn it is, castling rights (whether a King or Rook previously moved), or whether en passant is available. The game-details controls let you review those facts, but game import is still in development. Only classic pieces on an 8 x 8 board are supported, not Chass custom pieces or abilities.",
    },
    {
      title: "How Recognition Works",
      text: "An SSDLite detector locates pieces, duplicate suppression merges competing detections, and a ResNet18 classifier examines detailed piece crops to identify type and color. Placement currently uses box centers on your cropped board. Tilted or tall pieces can map to a neighboring square, and unfamiliar chess sets can be misidentified.",
    },
    {
      title: "Recognition Availability",
      text: "The page shows whether its recognition service is connected. If recognition is offline or not configured on this deployment, you can still upload, rotate, and crop a photo, but cannot recognize pieces. Local testing uses the separate scanner service; public hosting is not enabled automatically.",
    },
    {
      title: "Photos And Reviewed Labels",
      text: "Photos stay in your browser until you click Recognize Pieces, which sends the cropped image to the configured scanner service. The current service does not save uploads or send them to a third-party AI provider. Save Prepared Photo and Export Reviewed Labels download files to your device for accuracy testing; they do not automatically train the model. Check all 64 squares and resolve gold markers before exporting labels.",
    },
  ],
};
