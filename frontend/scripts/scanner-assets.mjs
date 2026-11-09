import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile, copyFile, rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("..", import.meta.url));
const source = path.resolve(root, "../scanner/models/onnx");
const output = path.join(root, "public/scanner-models");
// Immutable, already-public FP32 weights. Vercel's frontend-only build may lack ../scanner.
const published = "https://raw.githubusercontent.com/MihirKaushal/Chass/478957ac02f76af27276b6be964b97e119a37e6f/scanner/models/onnx";
async function asset(name) {
  try { return await readFile(path.join(source, name)); }
  catch (error) {
    if (error.code !== "ENOENT") throw error;
    const response = await fetch(`${published}/${name}`, { signal: AbortSignal.timeout(120000) });
    if (!response.ok) throw new Error(`Scanner asset download failed: ${name}`);
    return Buffer.from(await response.arrayBuffer());
  }
}
const manifest = JSON.parse(await asset("manifest.json"));
await mkdir(output, { recursive: true });
for (const name of ["detector", "classifier"]) {
  const bytes = await asset(`${name}.onnx`);
  if (createHash("sha256").update(bytes).digest("hex") !== manifest.sha256[name])
    throw new Error(`Scanner asset checksum mismatch: ${name}`);
  await writeFile(path.join(output, `${name}.onnx`), bytes);
}
await writeFile(path.join(output, "manifest.json"), JSON.stringify(manifest));
await writeFile(path.join(output, "README.md"), await asset("README.md"));
const wasm = path.join(root, "public/scanner-runtime");
await rm(wasm, { recursive: true, force: true });
await mkdir(wasm, { recursive: true });
for (const name of ["ort-wasm-simd-threaded.asyncify.mjs", "ort-wasm-simd-threaded.asyncify.wasm"])
  await copyFile(path.join(root, "node_modules/onnxruntime-web/dist", name), path.join(wasm, name));
console.log("Prepared checksum-verified scanner models and ONNX web runtime.");
