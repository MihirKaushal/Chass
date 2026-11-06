// Pure preprocessing and decoding shared by the browser worker and parity tests.
export const roundEven = (x) => Math.abs(x % 1) === 0.5 ? 2 * Math.round(x / 2) : Math.round(x);
export function softmax(values) {
  const max = Math.max(...values);
  const out = Array.from(values, (v) => Math.exp(v - max));
  const total = out.reduce((a, b) => a + b, 0);
  return out.map((v) => v / total);
}
export function iou(a, b) {
  const area = (x) => Math.max(0, x[2] - x[0]) * Math.max(0, x[3] - x[1]);
  const intersection = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0])) *
    Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  return intersection / (area(a) + area(b) - intersection || 1);
}
export function suppress(items, threshold, inclusive = false) {
  const kept = [];
  for (const item of [...items].sort((a, b) => b.score - a.score))
    if (!kept.some((other) => inclusive ? iou(item.box, other.box) >= threshold : iou(item.box, other.box) > threshold)) kept.push(item);
  return kept;
}

export function detectorTensor({ data, width, height }, size) {
  const out = new Float32Array(3 * size * size);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const sx = Math.max(0, (x + 0.5) * width / size - 0.5);
    const sy = Math.max(0, (y + 0.5) * height / size - 0.5);
    const x0 = Math.floor(sx), y0 = Math.floor(sy);
    const x1 = Math.min(x0 + 1, width - 1), y1 = Math.min(y0 + 1, height - 1);
    const wx = sx - x0, wy = sy - y0;
    for (let c = 0; c < 3; c++) {
      const p = (xx, yy) => data[(yy * width + xx) * 4 + c] / 255;
      out[c * size * size + y * size + x] =
        (p(x0, y0) * (1 - wx) + p(x1, y0) * wx) * (1 - wy) +
        (p(x0, y1) * (1 - wx) + p(x1, y1) * wx) * wy;
    }
  }
  return out;
}

function weights(length, target) {
  const scale = length / target, filter = Math.max(1, scale);
  return Array.from({ length: target }, (_, index) => {
    const center = (index + 0.5) * scale, entries = [];
    for (let i = Math.max(0, Math.floor(center - filter + 0.5)); i < Math.min(length, Math.floor(center + filter + 0.5)); i++)
      entries.push([i, Math.max(0, 1 - Math.abs((i + 0.5 - center) / filter))]);
    const total = entries.reduce((sum, [, weight]) => sum + weight, 0);
    // Pillow uses fixed-point bilinear coefficients and rounds after each pass.
    return entries.map(([i, weight]) => [i, Math.floor(weight / total * 4194304 + 0.5)]);
  });
}

export function cropPixels(image, box, config) {
  const { width, height, data } = image, { size, context } = config;
  const bw = box[2] - box[0], bh = box[3] - box[1];
  const left = Math.max(0, Math.floor(box[0] - bw * context));
  const top = Math.max(0, Math.floor(box[1] - bh * context));
  const cw = Math.min(width, Math.ceil(box[2] + bw * context)) - left;
  const ch = Math.min(height, Math.ceil(box[3] + bh * context)) - top;
  if (cw <= 0 || ch <= 0) throw new Error("Invalid piece crop.");
  const dw = cw < ch ? roundEven(cw / ch * size) : size;
  const dh = cw > ch ? roundEven(ch / cw * size) : size;
  const result = new Uint8Array(size * size * 3).fill(127);
  if (!dw || !dh) return result;
  const horizontal = new Uint8Array(ch * dw * 3);
  const wx = weights(cw, dw), wy = weights(ch, dh);
  const rounded = (v) => Math.min(255, Math.max(0, Math.floor((v + 2097152) / 4194304)));
  for (let y = 0; y < ch; y++) for (let x = 0; x < dw; x++) for (let c = 0; c < 3; c++) {
    horizontal[(y * dw + x) * 3 + c] = rounded(wx[x].reduce((sum, [i, w]) =>
      sum + data[((top + y) * width + left + i) * 4 + c] * w, 0));
  }
  const ox = roundEven((size - dw) / 2), oy = roundEven((size - dh) / 2);
  for (let y = 0; y < dh; y++) for (let x = 0; x < dw; x++) for (let c = 0; c < 3; c++) {
    result[((oy + y) * size + ox + x) * 3 + c] = rounded(wy[y].reduce((sum, [i, w]) =>
      sum + horizontal[(i * dw + x) * 3 + c] * w, 0));
  }
  return result;
}
export function classifierTensor(image, box, config) {
  const pixels = cropPixels(image, box, config), n = config.size ** 2;
  const out = new Float32Array(n * 3), mean = [0.485, 0.456, 0.406], std = [0.229, 0.224, 0.225];
  for (let i = 0; i < n; i++) for (let c = 0; c < 3; c++) out[c * n + i] = (pixels[i * 3 + c] / 255 - mean[c]) / std[c];
  return out;
}

export function decodeDetections(raw, config, width, height) {
  const regression = raw.regression.data, logits = raw.logits.data, anchors = raw.anchors.data;
  const classes = config.classes.length, boxes = [], probabilities = [];
  const [h, w] = config.detector_size;
  for (let i = 0; i < anchors.length / 4; i++) {
    const a = Array.from(anchors.slice(i * 4, i * 4 + 4));
    const r = Array.from(regression.slice(i * 4, i * 4 + 4), (v, j) => v / config.box_weights[j]);
    const aw = a[2] - a[0], ah = a[3] - a[1];
    const cx = a[0] + aw / 2 + r[0] * aw, cy = a[1] + ah / 2 + r[1] * ah;
    const pw = Math.exp(Math.min(r[2], config.box_clip)) * aw, ph = Math.exp(Math.min(r[3], config.box_clip)) * ah;
    boxes.push([Math.max(0, Math.min(w, cx - pw / 2)), Math.max(0, Math.min(h, cy - ph / 2)),
      Math.max(0, Math.min(w, cx + pw / 2)), Math.max(0, Math.min(h, cy + ph / 2))]);
    probabilities.push(softmax(logits.slice(i * classes, (i + 1) * classes)));
  }
  const found = [];
  for (let label = 1; label < classes; label++) {
    const candidates = boxes.map((box, i) => ({ box, label, score: probabilities[i][label] }))
      .filter((p) => p.score > config.score_threshold).sort((a, b) => b.score - a.score)
      .slice(0, config.topk_candidates);
    found.push(...suppress(candidates, config.nms_threshold));
  }
  return suppress(found.sort((a, b) => b.score - a.score).slice(0, config.detections_per_image)
    .filter((p) => p.score >= config.selection.threshold), config.selection.overlap, true)
    .map((p) => ({ ...p, box: p.box.map((v, i) => v * (i % 2 ? height / h : width / w)) }));
}

export function assembleBoard(pieces, width, height) {
  const board = Array.from({ length: 8 }, () => Array(8).fill(null));
  const groups = new Map(), reviewSquares = [], squareCandidates = [];
  for (const piece of pieces) {
    const x = (piece.box[0] + piece.box[2]) / 2 / width * 8;
    const y = (piece.box[1] + piece.box[3]) / 2 / height * 8;
    if (!(x >= 0 && x < 8 && y >= 0 && y < 8)) continue;
    const row = Math.floor(y), col = Math.floor(x), reasons = [];
    if (piece.classifierScore < 0.7 || piece.score < 0.5) reasons.push("Low model confidence");
    if (Math.min(x % 1, 1 - x % 1, y % 1, 1 - y % 1) < 0.18) reasons.push("Piece center is close to a square boundary");
    if (piece.box[2] - piece.box[0] > width / 8 * 1.2 || piece.box[3] - piece.box[1] > height / 8 * 1.2)
      reasons.push("Piece spans multiple squares; check its base");
    const key = row * 8 + col;
    const values = groups.get(key) || [];
    values.push({ class: piece.class, score: piece.score, classifierScore: piece.classifierScore,
      alternatives: piece.alternatives, reasons });
    groups.set(key, values);
  }
  for (const [key, candidates] of [...groups.entries()].sort((a, b) => a[0] - b[0])) {
    candidates.sort((a, b) => b.score - a.score);
    const row = Math.floor(key / 8), col = key % 8, label = `${"abcdefgh"[col]}${8 - row}`;
    const reasons = [...candidates[0].reasons];
    if (candidates.length > 1) reasons.push("Multiple pieces mapped here; inspect this and neighboring squares");
    board[row][col] = candidates[0].class;
    squareCandidates.push({ row, col, label, candidates });
    if (reasons.length) reviewSquares.push({ row, col, label, reasons });
  }
  return { board, reviewSquares, squareCandidates };
}
