// Test 1 (WASM side): try loadModel on every folder in jsbsim-data/aircraft. -> out/loadmatrix.<variant>.json
import { readdirSync, statSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { createSim, DATA, type Variant } from "../../src/wasm.ts";
import { tryLoad, type LoadResult } from "../../src/checks.ts";

const variant = (process.argv[2] ?? "jsbsim") as Variant;
const names = readdirSync(join(DATA, "aircraft")).filter((d) => statSync(join(DATA, "aircraft", d)).isDirectory() && !/^c172p_ext\d+$/.test(d)).sort(); // skip test-generated copies
let sim = await createSim({ variant });
const results: LoadResult[] = [];
for (const name of names) {
  const r = tryLoad(sim, name);
  if (!r.clean) sim = await createSim({ variant }); // e.g. a WebAssembly trap: start a fresh module
  results.push(r);
}
mkdirSync("out", { recursive: true });
writeFileSync(`out/loadmatrix.${variant}.json`, JSON.stringify(results, null, 1));
console.log(`${variant}: ${results.filter((r) => r.ok).length}/${results.length} aircraft load`);
