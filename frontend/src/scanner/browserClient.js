import { validateScanResponse } from "../scannerApi.js";

export function browserScannerSupported() {
  return typeof Worker !== "undefined" && typeof OffscreenCanvas !== "undefined" &&
    typeof createImageBitmap === "function" && Boolean(globalThis.crypto?.subtle);
}

export function recognizeInBrowser(file, signal, onStatus = () => {}, {
  workerFactory = () => new Worker(new URL("./browserWorker.js", import.meta.url), { type: "module" }),
  timeoutMs = 180000,
} = {}) {
  signal?.throwIfAborted();
  return new Promise((resolve, reject) => {
    const worker = workerFactory();
    const finish = (callback, value) => {
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
      worker.terminate();
      callback(value);
    };
    const abort = () => finish(reject, signal.reason);
    const timer = setTimeout(() => finish(reject, new Error("On-device recognition timed out.")), timeoutMs);
    signal?.addEventListener("abort", abort, { once: true });
    worker.onmessage = ({ data }) => {
      if (data.status) onStatus(data.status);
      else if (data.error) finish(reject, new Error(data.error));
      else {
        try { finish(resolve, validateScanResponse(data.result)); }
        catch (error) { finish(reject, error); }
      }
    };
    worker.onerror = () => finish(reject, new Error("On-device recognition failed."));
    try { worker.postMessage({ file }); }
    catch (error) { finish(reject, error); }
  });
}

export async function recognizeWithFallback({ enabled, file, signal, onStatus, browser, server }) {
  if (enabled) {
    try { return await browser(file, signal, onStatus); }
    catch {
      signal.throwIfAborted();
      onStatus("On-device recognition unavailable. Using the server...");
    }
  }
  signal.throwIfAborted();
  return server();
}
