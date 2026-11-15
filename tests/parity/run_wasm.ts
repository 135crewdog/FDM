// Run a JSBSim script in our WebAssembly build (headless, Node) and log every step.
// usage: tsx tests/parity/run_wasm.ts scripts/c1721.xml out/c1721.wasm.csv [rateRotationalIntegrator]
// JSBSIM_VARIANT=jsbsim-weh selects the -fwasm-exceptions build.
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { createSim, LOG_PROPS, sample, toCsv, describeError } from "../../src/wasm.ts";

const [script, out, rateInt] = process.argv.slice(2);
const sim = await createSim();
sim.setDebugLevel(0);
const rows: number[][] = [];
try {
  sim.loadScript(script);
  if (rateInt) sim.setIntegrators({ rateRotational: Number(rateInt) });
  sim.runIC();
  rows.push(sample(sim));
  const t0 = performance.now();
  while (sim.run()) rows.push(sample(sim));
  const ms = performance.now() - t0;
  console.log(`${script}: ${rows.length} rows, ${(ms * 1000 / rows.length).toFixed(1)} us/step incl. logging (wasm ${sim.version.split(" ")[0]})`);
} catch (e) {
  console.log(`${script}: FAILED in WASM: ${describeError(e)}`);
  process.exitCode = 2;
}
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, toCsv(LOG_PROPS, rows));
