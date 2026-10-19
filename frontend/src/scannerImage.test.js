import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_SCANNER_PHOTO_EDGE,
  clampScannerAngle,
  defaultScannerCrop,
  prepareScannerPhoto,
  projectScannerPoint,
  reframeScannerCrop,
  rotateScannerEdits,
  scannerCropIssue,
  scannerCropResolution,
  scannerCropToSource,
  scannerPerspectiveMatrix,
  scannerPointerPosition,
  scannerPreviewFit,
  scannerRotationGeometry,
  translateScannerCrop,
  warpScannerPixels,
} from "./scannerImage.js";

const FULL_CROP = [
  { x: 0, y: 0 },
  { x: 1, y: 0 },
  { x: 1, y: 1 },
  { x: 0, y: 1 },
];

function near(actual, expected) {
  assert.ok(Math.abs(actual - expected) < 1e-8, `${actual} != ${expected}`);
}

function nearPoint(actual, expected) {
  near(actual.x, expected.x);
  near(actual.y, expected.y);
}

test("photo rotation accepts fine angles and clamps invalid values", () => {
  assert.equal(clampScannerAngle("12.36"), 12.4);
  assert.equal(clampScannerAngle(-27.1), -27.1);
  assert.equal(clampScannerAngle(181), 180);
  assert.equal(clampScannerAngle(-500), -180);
  assert.equal(clampScannerAngle(NaN), 0);
  assert.equal(clampScannerAngle(Infinity), 0);
});

test("rotation geometry encloses the entire image at arbitrary angles", () => {
  const upright = scannerRotationGeometry(800, 600, 0);
  near(upright.width, 800);
  near(upright.height, 600);
  const sideways = scannerRotationGeometry(800, 600, 90);
  near(sideways.width, 600);
  near(sideways.height, 800);
  const diagonal = scannerRotationGeometry(800, 600, 45);
  near(diagonal.width, 1400 / Math.sqrt(2));
  near(diagonal.height, 1400 / Math.sqrt(2));
  assert.throws(() => scannerRotationGeometry(0, 600, 0), /dimensions/);
  assert.throws(() => scannerRotationGeometry(Infinity, 600, 0), /dimensions/);
});

test("rotation preserves the crop frame's pixel dimensions and is reversible", () => {
  const original = scannerRotationGeometry(1200, 800, 0);
  const rotated = scannerRotationGeometry(1200, 800, 3.7);
  const corners = defaultScannerCrop(original);
  const reframed = reframeScannerCrop(corners, original, rotated);
  assert.equal(scannerCropIssue(reframed, rotated), null);
  near(
    (reframed[1].x - reframed[0].x) * rotated.width,
    (corners[1].x - corners[0].x) * original.width,
  );
  near(
    (reframed[3].y - reframed[0].y) * rotated.height,
    (corners[3].y - corners[0].y) * original.height,
  );
  reframeScannerCrop(reframed, rotated, original).forEach((point, index) =>
    nearPoint(point, corners[index]),
  );
});

test("rapid rotation updates keep the angle and crop together without accumulating drift", () => {
  const original = {
    rotation: 0,
    corners: defaultScannerCrop(scannerRotationGeometry(1600, 900, 0)),
  };
  const snapshot = structuredClone(original);
  let edits = original;
  for (let step = -1800; step <= 1800; step += 1) {
    edits = rotateScannerEdits(edits, 1600, 900, step / 10);
  }
  edits = rotateScannerEdits(edits, 1600, 900, 3.7);
  const direct = rotateScannerEdits(original, 1600, 900, 3.7);
  assert.equal(edits.rotation, 3.7);
  edits.corners.forEach((point, index) =>
    nearPoint(point, direct.corners[index]),
  );
  edits = rotateScannerEdits(edits, 1600, 900, 0);
  edits.corners.forEach((point, index) =>
    nearPoint(point, original.corners[index]),
  );
  assert.deepEqual(original, snapshot);
  assert.equal(rotateScannerEdits(edits, 1600, 900, 0), edits);
  assert.deepEqual(
    rotateScannerEdits({ rotation: 0, corners: null }, 1600, 900, 90),
    { rotation: 90, corners: null },
  );
});

test("wide photos rotated 90 degrees fit against the viewport height without clipping", () => {
  const bounds = { width: 640, height: 360 };
  const fit = scannerPreviewFit(scannerRotationGeometry(2400, 600, 90), bounds);
  near(fit.height, bounds.height);
  near(fit.width, 90);
  near(fit.left, 275);
  near(fit.top, 0);
  assert.equal(
    scannerPreviewFit(scannerRotationGeometry(2400, 600, 90), {
      width: 0,
      height: 360,
    }),
    null,
  );
});

test("the full rotated photo remains centered and edge-fitted at every fine angle", () => {
  for (const [width, height] of [
    [2400, 600],
    [600, 2400],
    [800, 800],
  ]) {
    for (const bounds of [
      { width: 720, height: 360 },
      { width: 300, height: 600 },
    ]) {
      for (let step = -1800; step <= 1800; step += 1) {
        const geometry = scannerRotationGeometry(width, height, step / 10);
        const fit = scannerPreviewFit(geometry, bounds);
        near(fit.left * 2 + fit.width, bounds.width);
        near(fit.top * 2 + fit.height, bounds.height);
        assert.ok(fit.left >= -1e-8 && fit.top >= -1e-8);
        assert.ok(Math.abs(fit.left) < 1e-8 || Math.abs(fit.top) < 1e-8);
        for (const corner of FULL_CROP) {
          const dx = (corner.x - 0.5) * width;
          const dy = (corner.y - 0.5) * height;
          const x =
            fit.left +
            (geometry.width / 2 + geometry.cosine * dx - geometry.sine * dy) *
              fit.scale;
          const y =
            fit.top +
            (geometry.height / 2 + geometry.sine * dx + geometry.cosine * dy) *
              fit.scale;
          assert.ok(
            x >= -1e-8 && x <= bounds.width + 1e-8,
            `clipped x at ${step / 10}`,
          );
          assert.ok(
            y >= -1e-8 && y <= bounds.height + 1e-8,
            `clipped y at ${step / 10}`,
          );
        }
      }
    }
  }
});

test("edge-fitting stays continuous when the limiting axis changes during rotation", () => {
  const bounds = { width: 720, height: 360 };
  let previous;
  for (let step = -1800; step <= 1800; step += 1) {
    const fit = scannerPreviewFit(
      scannerRotationGeometry(2400, 600, step / 10),
      bounds,
    );
    if (previous) {
      for (const field of ["left", "top", "width", "height"]) {
        assert.ok(
          Math.abs(fit[field] - previous[field]) < 5,
          `${field} jumped at ${step / 10}`,
        );
      }
    }
    previous = fit;
  }
});

test("default crops stay inside portrait, landscape, and square photos at every angle", () => {
  for (const [width, height] of [
    [800, 600],
    [600, 800],
    [800, 800],
  ]) {
    for (let rotation = -180; rotation <= 180; rotation += 0.5) {
      const geometry = scannerRotationGeometry(width, height, rotation);
      const corners = defaultScannerCrop(geometry);
      assert.equal(
        scannerCropIssue(corners, geometry),
        null,
        `${width}x${height} @ ${rotation}`,
      );
      near(
        (corners[1].x - corners[0].x) * geometry.width,
        (corners[3].y - corners[0].y) * geometry.height,
      );
    }
  }
});

test("inverse rotation maps selected corners to their correct original pixels", () => {
  const geometry = scannerRotationGeometry(400, 400, 90);
  const expected = [FULL_CROP[3], FULL_CROP[0], FULL_CROP[1], FULL_CROP[2]];
  FULL_CROP.forEach((point, index) =>
    nearPoint(scannerCropToSource(point, geometry), expected[index]),
  );
  const angled = scannerRotationGeometry(1200, 800, 17.3);
  nearPoint(scannerCropToSource({ x: 0.5, y: 0.5 }, angled), {
    x: 0.5,
    y: 0.5,
  });
});

test("perspective transform maps all four corners for square, trapezoid, and skew crops", () => {
  for (const corners of [
    FULL_CROP,
    [
      { x: 0.2, y: 0.1 },
      { x: 0.8, y: 0.2 },
      { x: 0.95, y: 0.9 },
      { x: 0.1, y: 0.8 },
    ],
    [
      { x: 0.4, y: 0.1 },
      { x: 0.6, y: 0.1 },
      { x: 0.95, y: 0.9 },
      { x: 0.05, y: 0.9 },
    ],
  ]) {
    const matrix = scannerPerspectiveMatrix(corners);
    FULL_CROP.forEach((point, index) =>
      nearPoint(projectScannerPoint(matrix, point.x, point.y), corners[index]),
    );
  }
});

test("the grid follows a perspective crop rather than an axis-aligned rectangle", () => {
  const matrix = scannerPerspectiveMatrix([
    { x: 0.3, y: 0.1 },
    { x: 0.7, y: 0.1 },
    { x: 1, y: 0.9 },
    { x: 0, y: 0.9 },
  ]);
  nearPoint(projectScannerPoint(matrix, 0.5, 0), { x: 0.5, y: 0.1 });
  nearPoint(projectScannerPoint(matrix, 0.5, 1), { x: 0.5, y: 0.9 });
  const center = projectScannerPoint(matrix, 0.5, 0.5);
  near(center.x, 0.5);
  assert.ok(center.y < 0.5);
});

test("invalid, crossed, tiny, and off-photo crops have actionable validation", () => {
  const geometry = scannerRotationGeometry(800, 800, 0);
  assert.match(scannerCropIssue(null, geometry), /four corners/);
  assert.match(
    scannerCropIssue(
      [FULL_CROP[0], FULL_CROP[2], FULL_CROP[1], FULL_CROP[3]],
      geometry,
    ),
    /clockwise/,
  );
  assert.match(
    scannerCropIssue(
      FULL_CROP.map(({ x, y }) => ({ x: x * 0.001, y: y * 0.001 })),
      geometry,
    ),
    /too small/,
  );
  assert.match(
    scannerCropIssue(
      FULL_CROP.map(({ x, y }) => ({ x: x - 0.1, y })),
      geometry,
    ),
    /inside the photo/,
  );
  assert.match(
    scannerCropIssue(FULL_CROP, scannerRotationGeometry(800, 800, 45)),
    /inside the photo/,
  );
  assert.match(
    scannerCropIssue([...FULL_CROP.slice(0, 3), { x: NaN, y: 1 }], geometry),
    /four corners/,
  );
});

test("pointer positions account for horizontal and vertical letterboxing", () => {
  const geometry = scannerRotationGeometry(400, 400, 0);
  const wide = { left: 10, top: 20, width: 600, height: 400 };
  nearPoint(scannerPointerPosition(110, 20, wide, geometry), { x: 0, y: 0 });
  nearPoint(scannerPointerPosition(310, 220, wide, geometry), {
    x: 0.5,
    y: 0.5,
  });
  nearPoint(scannerPointerPosition(0, 1000, wide, geometry), { x: 0, y: 1 });
  const tall = { left: 0, top: 0, width: 400, height: 600 };
  nearPoint(scannerPointerPosition(200, 300, tall, geometry), {
    x: 0.5,
    y: 0.5,
  });
  assert.equal(
    scannerPointerPosition(0, 0, { ...wide, width: 0 }, geometry),
    null,
  );
});

test("moving the entire crop preserves its shape and stops at the photo boundary", () => {
  const crop = FULL_CROP.map(({ x, y }) => ({
    x: 0.2 + x * 0.6,
    y: 0.1 + y * 0.6,
  }));
  const moved = translateScannerCrop(crop, 10, -10);
  nearPoint(moved[0], { x: 0.4, y: 0 });
  nearPoint(moved[2], { x: 1, y: 0.6 });
  nearPoint(crop[0], { x: 0.2, y: 0.1 });
});

test("crop resolution uses original pixels instead of viewport size", () => {
  const geometry = scannerRotationGeometry(1600, 1200, 0);
  assert.equal(scannerCropResolution(FULL_CROP, geometry), 1600);
  assert.equal(
    scannerCropResolution(defaultScannerCrop(geometry), geometry),
    1104,
  );
});

const PIXELS = new Uint8ClampedArray([
  255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 255, 255, 255, 255,
]);

test("identity perspective crop preserves pixel colors and does not mutate the original", () => {
  const original = PIXELS.slice();
  const output = warpScannerPixels(
    { width: 2, height: 2, data: original },
    FULL_CROP,
    2,
  );
  assert.deepEqual(output, PIXELS);
  assert.deepEqual(original, PIXELS);
  assert.notEqual(output, original);
});

test("rotation is applied to the saved pixels, not only to the image preview", () => {
  const geometry = scannerRotationGeometry(2, 2, 90);
  const output = warpScannerPixels(
    { width: 2, height: 2, data: PIXELS },
    FULL_CROP.map((point) => scannerCropToSource(point, geometry)),
    2,
  );
  assert.deepEqual(
    [...output],
    [0, 0, 255, 255, 255, 0, 0, 255, 255, 255, 255, 255, 0, 255, 0, 255],
  );
});

test("perspective sampling interpolates smoothly instead of leaving gaps", () => {
  const output = warpScannerPixels(
    { width: 2, height: 2, data: PIXELS },
    FULL_CROP,
    3,
  );
  assert.deepEqual([...output.slice(16, 20)], [128, 128, 128, 255]);
  const single = warpScannerPixels(
    { width: 2, height: 2, data: PIXELS },
    FULL_CROP,
    1,
  );
  assert.deepEqual([...single], [128, 128, 128, 255]);
  for (let index = 3; index < output.length; index += 4)
    assert.equal(output[index], 255);
});

test("output limits prevent excessive image allocations", () => {
  const source = { width: 2, height: 2, data: PIXELS };
  for (const size of [0, -1, 1.5, MAX_SCANNER_PHOTO_EDGE + 1, Infinity]) {
    assert.throws(
      () => warpScannerPixels(source, FULL_CROP, size),
      /size is invalid/,
    );
  }
});

test("preparing a photo saves a new JPEG, leaves the original untouched, and reports encoder failures", async (context) => {
  let encodedType;
  let failEncoding = false;
  let writtenPixels;
  const canvasContext = {
    fillRect() {},
    drawImage() {},
    getImageData: () => ({ width: 2, height: 2, data: PIXELS }),
    createImageData: (width, height) => ({
      data: new Uint8ClampedArray(width * height * 4),
    }),
    putImageData: (image) => {
      writtenPixels = image.data;
    },
  };
  const canvas = {
    getContext: () => canvasContext,
    toBlob(callback, type) {
      encodedType = type;
      callback(failEncoding ? null : new Blob(["jpeg"], { type }));
    },
  };
  const previousDocument = Object.getOwnPropertyDescriptor(
    globalThis,
    "document",
  );
  Object.defineProperty(globalThis, "document", {
    configurable: true,
    value: {
      createElement: (tag) => {
        assert.equal(tag, "canvas");
        return canvas;
      },
    },
  });
  context.after(() => {
    if (previousDocument)
      Object.defineProperty(globalThis, "document", previousDocument);
    else delete globalThis.document;
  });
  const original = new File(["original bytes"], "chess.board.png", {
    type: "image/png",
  });
  const image = { naturalWidth: 2, naturalHeight: 2 };
  const edits = { rotation: 0, corners: FULL_CROP };
  const prepared = await prepareScannerPhoto(image, original, edits);
  assert.equal(prepared.name, "chess.board-prepared.jpg");
  assert.equal(prepared.type, "image/jpeg");
  assert.equal(encodedType, "image/jpeg");
  assert.equal(canvas.width, canvas.height);
  assert.deepEqual(writtenPixels, PIXELS);
  assert.equal(await original.text(), "original bytes");
  failEncoding = true;
  await assert.rejects(
    prepareScannerPhoto(image, original, edits),
    /could not be saved/,
  );
  await assert.rejects(
    prepareScannerPhoto(image, original, { ...edits, rotation: 45 }),
    /inside the photo/,
  );
});
