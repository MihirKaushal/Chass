import * as ort from "onnxruntime-web/webgpu";
import { inferImage } from "./browserInference.js";

const hash = async (bytes) => Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
  (b) => b.toString(16).padStart(2, "0")).join("");

async function weights(name, manifest) {
  const expected = manifest.sha256[name];
  const url = `/scanner-models/${name}.onnx?v=${expected}`;
  let cache;
  try { cache = await caches.open("chass-scanner-models-v1"); } catch { /* Private browsing may deny caching. */ }
  const cached = await cache?.match(url);
  if (cached) {
    const bytes = await cached.arrayBuffer();
    if (await hash(bytes) === expected) return bytes;
    await cache.delete(url);
  }
  const response = await fetch(url);
  if (!response.ok) throw new Error("Model download failed.");
  const bytes = await response.arrayBuffer();
  if (await hash(bytes) !== expected) throw new Error("Model verification failed.");
  try {
    await cache?.put(url, new Response(bytes));
    for (const entry of await cache?.keys() || []) {
      if (new URL(entry.url).pathname === `/scanner-models/${name}.onnx` && entry.url !== new URL(url, self.location.origin).href)
        await cache.delete(entry);
    }
  } catch { /* Full cache must not block recognition. */ }
  return bytes;
}

async function recognize(file) {
  if (!file.size || file.size > 10 * 1024 * 1024) throw new Error("Invalid image size.");
  const bitmap = await createImageBitmap(file);
  if (Math.min(bitmap.width, bitmap.height) < 128 || Math.max(bitmap.width, bitmap.height) > 2048) {
    bitmap.close();
    throw new Error("Apply the board crop before scanning.");
  }
  const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.drawImage(bitmap, 0, 0);
  bitmap.close();
  const image = context.getImageData(0, 0, canvas.width, canvas.height);
  self.postMessage({ status: "Loading on-device models..." });
  const response = await fetch("/scanner-models/manifest.json");
  if (!response.ok) throw new Error("Model manifest unavailable.");
  const config = await response.json();
  if (config.format_version !== 1 || config.selection.pipeline !== "combined") throw new Error("Unsupported model.");
  ort.env.wasm.numThreads = 1;
  ort.env.wasm.wasmPaths = new URL("/scanner-runtime/", self.location.origin).href;
  const sessions = {};
  let provider = "wasm";
  try {
    if (self.navigator.gpu && await self.navigator.gpu.requestAdapter()) provider = "webgpu";
    for (const name of ["detector", "classifier"]) {
      const bytes = await weights(name, config);
      try {
        sessions[name] = await ort.InferenceSession.create(bytes, { executionProviders: [provider] });
      } catch (error) {
        if (provider === "wasm") throw error;
        // Mixed graph support varies by GPU; the CPU path supports the full operator set.
        sessions[name] = await ort.InferenceSession.create(bytes, { executionProviders: ["wasm"] });
      }
    }
    self.postMessage({ status: "Recognizing on this device..." });
    const started = performance.now();
    const board = await inferImage(ort, sessions, image, config);
    return {
      ...board,
      pipeline: "combined", runtime: "browser-onnx", rectified: true,
      inferenceMs: Math.round(performance.now() - started),
      imageSha256: await hash(await file.arrayBuffer()),
      datasetFingerprint: config.selection.dataset_fingerprint,
      modelSha256: config.sha256,
      classificationScoresAreCalibrated: false,
      warnings: ["Check all 64 squares, including empty squares.",
        "Square assignment uses box centers; check tall pieces and neighboring squares."],
    };
  } finally {
    for (const session of Object.values(sessions)) await session.release();
  }
}

self.onmessage = async ({ data }) => {
  try { self.postMessage({ result: await recognize(data.file) }); }
  catch { self.postMessage({ error: "On-device recognition is not available on this browser." }); }
};
