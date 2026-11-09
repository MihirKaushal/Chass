const UNIT_CORNERS = [
  { x: 0, y: 0 },
  { x: 1, y: 0 },
  { x: 1, y: 1 },
  { x: 0, y: 1 },
];
export const MAX_SCANNER_PHOTO_EDGE = 2048;

export function clampScannerAngle(value) {
  const number = Number(value);
  return Number.isFinite(number)
    ? Math.round(Math.max(-180, Math.min(180, number)) * 10) / 10
    : 0;
}

export function scannerRotationGeometry(width, height, angle) {
  if (
    !Number.isFinite(width) ||
    !Number.isFinite(height) ||
    !(width > 0) ||
    !(height > 0)
  )
    throw new Error("The photo dimensions are invalid.");
  const degrees = clampScannerAngle(angle);
  const radians = (degrees * Math.PI) / 180;
  const cosine = Math.abs(Math.cos(radians)) < 1e-12 ? 0 : Math.cos(radians);
  const sine = Math.abs(Math.sin(radians)) < 1e-12 ? 0 : Math.sin(radians);
  return {
    sourceWidth: width,
    sourceHeight: height,
    width: Math.abs(width * cosine) + Math.abs(height * sine),
    height: Math.abs(width * sine) + Math.abs(height * cosine),
    cosine,
    sine,
    angle: degrees,
  };
}

export function reframeScannerCrop(corners, previous, next) {
  // Rotation changes the image's bounding box, not the frame's pixel dimensions.
  return corners.map((point) => ({
    x: 0.5 + ((point.x - 0.5) * previous.width) / next.width,
    y: 0.5 + ((point.y - 0.5) * previous.height) / next.height,
  }));
}

export function rotateScannerEdits(edits, width, height, value) {
  const rotation = clampScannerAngle(value);
  if (rotation === edits.rotation) return edits;
  return {
    ...edits,
    rotation,
    corners: edits.corners
      ? reframeScannerCrop(
          edits.corners,
          scannerRotationGeometry(width, height, edits.rotation),
          scannerRotationGeometry(width, height, rotation),
        )
      : null,
  };
}

export function defaultScannerCrop(geometry) {
  const edge =
    (0.92 * Math.min(geometry.sourceWidth, geometry.sourceHeight)) /
    (Math.abs(geometry.cosine) + Math.abs(geometry.sine));
  return UNIT_CORNERS.map(({ x, y }) => ({
    x: 0.5 + ((x - 0.5) * edge) / geometry.width,
    y: 0.5 + ((y - 0.5) * edge) / geometry.height,
  }));
}

export function scannerCropToSource(point, geometry) {
  const dx = (point.x - 0.5) * geometry.width;
  const dy = (point.y - 0.5) * geometry.height;
  return {
    x: 0.5 + (geometry.cosine * dx + geometry.sine * dy) / geometry.sourceWidth,
    y:
      0.5 +
      (-geometry.sine * dx + geometry.cosine * dy) / geometry.sourceHeight,
  };
}

export function scannerCropIssue(corners, geometry) {
  if (
    !corners ||
    corners.length !== 4 ||
    corners.some(
      (point) => !Number.isFinite(point.x) || !Number.isFinite(point.y),
    )
  ) {
    return "Select the four corners of the board.";
  }
  let area = 0;
  for (let index = 0; index < 4; index += 1) {
    const a = corners[index];
    const b = corners[(index + 1) % 4];
    const c = corners[(index + 2) % 4];
    const turn = (b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x);
    if (turn <= 1e-8)
      return "Keep the four corners in clockwise order without crossing the crop edges.";
    area += a.x * b.y - b.x * a.y;
  }
  if (area / 2 < 0.0001)
    return "The crop is too small. Include the full board.";
  if (
    corners.some((point) => {
      const source = scannerCropToSource(point, geometry);
      return (
        source.x < -1e-6 ||
        source.x > 1 + 1e-6 ||
        source.y < -1e-6 ||
        source.y > 1 + 1e-6
      );
    })
  )
    return "Move all four crop corners inside the photo, onto the board.";
  return null;
}

export function scannerPerspectiveMatrix(corners) {
  const [a, b, c, d] = corners;
  const dx1 = b.x - c.x;
  const dx2 = d.x - c.x;
  const dx3 = a.x - b.x + c.x - d.x;
  const dy1 = b.y - c.y;
  const dy2 = d.y - c.y;
  const dy3 = a.y - b.y + c.y - d.y;
  let g = 0;
  let h = 0;
  if (Math.abs(dx3) + Math.abs(dy3) > 1e-12) {
    const denominator = dx1 * dy2 - dx2 * dy1;
    if (Math.abs(denominator) < 1e-12)
      throw new Error("The crop corners are too close together.");
    g = (dx3 * dy2 - dx2 * dy3) / denominator;
    h = (dx1 * dy3 - dx3 * dy1) / denominator;
  }
  return [
    b.x - a.x + g * b.x,
    d.x - a.x + h * d.x,
    a.x,
    b.y - a.y + g * b.y,
    d.y - a.y + h * d.y,
    a.y,
    g,
    h,
  ];
}

export function projectScannerPoint(matrix, x, y) {
  const denominator = matrix[6] * x + matrix[7] * y + 1;
  return {
    x: (matrix[0] * x + matrix[1] * y + matrix[2]) / denominator,
    y: (matrix[3] * x + matrix[4] * y + matrix[5]) / denominator,
  };
}

export function scannerPreviewFit(geometry, bounds) {
  // Match SVG's xMidYMid meet sizing without allowing its intrinsic ratio to resize the stage.
  const scale = Math.min(
    bounds.width / geometry.width,
    bounds.height / geometry.height,
  );
  if (!(scale > 0) || !Number.isFinite(scale)) return null;
  const width = geometry.width * scale;
  const height = geometry.height * scale;
  return {
    scale,
    width,
    height,
    left: (bounds.width - width) / 2,
    top: (bounds.height - height) / 2,
  };
}

export function scannerPointerPosition(clientX, clientY, bounds, geometry) {
  const fit = scannerPreviewFit(geometry, bounds);
  if (!fit) return null;
  return {
    x: Math.max(0, Math.min(1, (clientX - bounds.left - fit.left) / fit.width)),
    y: Math.max(0, Math.min(1, (clientY - bounds.top - fit.top) / fit.height)),
  };
}

export function translateScannerCrop(corners, dx, dy) {
  const boundedX = Math.max(
    -Math.min(...corners.map((point) => point.x)),
    Math.min(1 - Math.max(...corners.map((point) => point.x)), dx),
  );
  const boundedY = Math.max(
    -Math.min(...corners.map((point) => point.y)),
    Math.min(1 - Math.max(...corners.map((point) => point.y)), dy),
  );
  return corners.map((point) => ({
    x: point.x + boundedX,
    y: point.y + boundedY,
  }));
}

export function scannerCropResolution(corners, geometry) {
  const source = corners.map((point) => scannerCropToSource(point, geometry));
  const edge = (a, b) =>
    Math.hypot(
      (a.x - b.x) * geometry.sourceWidth,
      (a.y - b.y) * geometry.sourceHeight,
    );
  return Math.max(
    1,
    Math.round(
      Math.max(
        (edge(source[0], source[1]) + edge(source[3], source[2])) / 2,
        (edge(source[0], source[3]) + edge(source[1], source[2])) / 2,
      ),
    ),
  );
}

export function warpScannerPixels(source, corners, size) {
  if (!Number.isInteger(size) || size < 1 || size > MAX_SCANNER_PHOTO_EDGE)
    throw new Error("The output image size is invalid.");
  const matrix = scannerPerspectiveMatrix(corners);
  const output = new Uint8ClampedArray(size * size * 4);
  const maxX = source.width - 1;
  const maxY = source.height - 1;
  // Inverse mapping samples the original once, avoiding holes and repeated rotation blur.
  for (let row = 0; row < size; row += 1) {
    const v = size > 1 ? row / (size - 1) : 0.5;
    for (let col = 0; col < size; col += 1) {
      const u = size > 1 ? col / (size - 1) : 0.5;
      const denominator = matrix[6] * u + matrix[7] * v + 1;
      const x = Math.max(
        0,
        Math.min(
          maxX,
          ((matrix[0] * u + matrix[1] * v + matrix[2]) / denominator) * maxX,
        ),
      );
      const y = Math.max(
        0,
        Math.min(
          maxY,
          ((matrix[3] * u + matrix[4] * v + matrix[5]) / denominator) * maxY,
        ),
      );
      const x0 = Math.floor(x);
      const y0 = Math.floor(y);
      const x1 = Math.min(maxX, x0 + 1);
      const y1 = Math.min(maxY, y0 + 1);
      const fx = x - x0;
      const fy = y - y0;
      const topLeft = (y0 * source.width + x0) * 4;
      const topRight = (y0 * source.width + x1) * 4;
      const bottomLeft = (y1 * source.width + x0) * 4;
      const bottomRight = (y1 * source.width + x1) * 4;
      const destination = (row * size + col) * 4;
      for (let channel = 0; channel < 4; channel += 1) {
        output[destination + channel] =
          (source.data[topLeft + channel] * (1 - fx) +
            source.data[topRight + channel] * fx) *
            (1 - fy) +
          (source.data[bottomLeft + channel] * (1 - fx) +
            source.data[bottomRight + channel] * fx) *
            fy;
      }
    }
  }
  return output;
}

export async function prepareScannerPhoto(image, sourceFile, edits) {
  const geometry = scannerRotationGeometry(
    image.naturalWidth,
    image.naturalHeight,
    edits.rotation,
  );
  const issue = scannerCropIssue(edits.corners, geometry);
  if (issue) throw new Error(issue);
  const canvas = document.createElement("canvas");
  const scale = Math.min(
    1,
    4096 / Math.max(image.naturalWidth, image.naturalHeight),
  );
  canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
  canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context)
    throw new Error(
      "This browser could not prepare the photo. Try a different browser.",
    );
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
  const sourceCorners = edits.corners.map((point) =>
    scannerCropToSource(point, geometry),
  );
  const size = Math.min(
    MAX_SCANNER_PHOTO_EDGE,
    scannerCropResolution(edits.corners, geometry),
  );
  const output = warpScannerPixels(pixels, sourceCorners, size);
  canvas.width = size;
  canvas.height = size;
  const prepared = context.createImageData(size, size);
  prepared.data.set(output);
  context.putImageData(prepared, 0, 0);
  const blob = await new Promise((resolve, reject) =>
    canvas.toBlob(
      (value) =>
        value
          ? resolve(value)
          : reject(
              new Error("The edited photo could not be saved. Try again."),
            ),
      "image/jpeg",
      0.95,
    ),
  );
  return new File(
    [blob],
    `${sourceFile.name.replace(/\.[^.]+$/, "")}-prepared.jpg`,
    { type: "image/jpeg" },
  );
}
