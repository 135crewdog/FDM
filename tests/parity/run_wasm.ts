// Run a JSBSim script in the WebAssembly package (headless, Node) and log every step.
// usage: tsx tests/parity/run_wasm.ts scripts/c1721.xml out/c1721.wasm.csv
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { createSdk, copyTree, DATA, LOG_PROPS, sample, toCsv, describeError } from "../../src/wasm.ts";

const [script, out] = process.argv.slice(2);
const sdk = await createSdk();
for (const d of ["aircraft", "engine", "systems", "scripts"]) copyTree(sdk, DATA + d, d);
sdk.setDebugLevel(0);
const rows: number[][] = [];
try {
  if (!sdk.loadScript(script)) throw new Error("loadScript returned false");
  if (!sdk.runIc()) throw new Error("runIc returned false");
  rows.push(sample(sdk));
  const t0 = performance.now();
  while (sdk.run()) rows.push(sample(sdk));
  const ms = performance.now() - t0;
  console.log(`${script}: ${rows.length} rows, ${(ms * 1000 / rows.length).toFixed(1)} us/step incl. logging`);
} catch (e) {
  console.log(`${script}: FAILED in WASM: ${describeError(e)}`);
  process.exitCode = 2;
}
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, toCsv(LOG_PROPS, rows));
