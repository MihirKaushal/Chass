// Runs the same worker inference code in ONNX Web WASM; not a browser/UI speed benchmark.
import * as ort from "onnxruntime-web/webgpu";
import { readFile, writeFile } from "node:fs/promises";
import { inferImage } from "../src/scanner/browserInference.js";
const [fixture, output, models = "public/scanner-models"] = process.argv.slice(2);
if (!fixture || !output) throw new Error("Provide an RGBA JSON fixture and output JSON path.");
const { image } = JSON.parse(await readFile(fixture, "utf8"));
const config = JSON.parse(await readFile(`${models}/manifest.json`, "utf8"));
ort.env.wasm.numThreads = 1;
const sessions = {};
try {
  for (const name of ["detector", "classifier"])
    sessions[name] = await ort.InferenceSession.create(await readFile(`${models}/${name}.onnx`), { executionProviders: ["wasm"] });
  const started = performance.now();
  const result = await inferImage(ort, sessions, image, config);
  await writeFile(output, JSON.stringify({ ...result, ms: performance.now() - started }));
} finally {
  for (const session of Object.values(sessions)) await session.release();
}
