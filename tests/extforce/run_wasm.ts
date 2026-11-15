// Test 2 in the WebAssembly package.
//  parity: tsx run_wasm.ts parity <out.csv> [zero]   (1 force, schedule applied every step; "zero" = magnitude 0)
//  bench:  tsx run_wasm.ts bench                       (cost of 20 forces updated every step)
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { createSdk, copyTree, DATA, LOG_PROPS, sample, toCsv } from "../../src/wasm.ts";
import { forceAt, SUFFIX } from "./schedule.ts";

const EXTRA = ["forces/fbx-external-lbs", "forces/fby-external-lbs", "forces/fbz-external-lbs",
  "moments/l-external-lbsft", "moments/m-external-lbsft", "moments/n-external-lbsft"];
const PROPS = [...LOG_PROPS, ...EXTRA];

async function setup(script: string) {
  const sdk = await createSdk();
  for (const d of ["aircraft/c172p_ext1", "aircraft/c172p_ext20", "aircraft/c172p", "engine", "systems", "scripts"]) copyTree(sdk, DATA + d, d);
  sdk.setDebugLevel(0);
  if (!sdk.loadScript(script) || !sdk.runIc()) throw new Error("load failed: " + script);
  return sdk;
}

const [mode, out, variant] = process.argv.slice(2);
if (mode === "parity") {
  const sdk = await setup("scripts/ext_c172p_ext1.xml");
  const names = SUFFIX.map((s) => `external_reactions/f0/${s}`);
  const rows = [sample(sdk, PROPS)];
  for (let k = 0; k < 3600; k++) {          // 30 s at 120 Hz
    const v = forceAt(0, k);
    if (variant === "zero") v[6] = 0;
    for (let j = 0; j < 7; j++) sdk.setPropertyValue(names[j], v[j]);
    sdk.run();
    rows.push(sample(sdk, PROPS));
  }
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, toCsv(PROPS, rows));
} else if (mode === "bench") {
  const STEPS = 6000, REPS = 5;
  const cases: [string, string, boolean][] = [
    ["c172p, no external forces", "scripts/ext_c172p_ext1.xml", false],
    ["c172p + 20 forces, not updated", "scripts/ext_c172p_ext20.xml", false],
    ["c172p + 20 forces, 7 props each set every step", "scripts/ext_c172p_ext20.xml", true],
  ];
  const result: Record<string, number> = {};
  for (const [label, script, update] of cases) {
    const sdk = await setup(script);
    const names = Array.from({ length: 20 }, (_, i) => SUFFIX.map((s) => `external_reactions/f${i}/${s}`));
    let best = Infinity, k = 0;
    for (let r = 0; r < REPS; r++) {
      const t0 = performance.now();
      for (let s = 0; s < STEPS; s++, k++) {
        if (update) for (let i = 0; i < 20; i++) { const v = forceAt(i, k); v[6] *= 0.1; for (let j = 0; j < 7; j++) sdk.setPropertyValue(names[i][j], v[j]); }
        sdk.run();
      }
      best = Math.min(best, (performance.now() - t0) * 1000 / STEPS);
    }
    result[label] = best;
    console.log(`${label.padEnd(50)} ${best.toFixed(2)} us/step (best of ${REPS} x ${STEPS})`);
  }
  // Just the property writes, to separate binding cost from physics cost.
  const sdk = await setup("scripts/ext_c172p_ext20.xml");
  const names = Array.from({ length: 20 }, (_, i) => SUFFIX.map((s) => `external_reactions/f${i}/${s}`));
  const t0 = performance.now();
  for (let s = 0; s < STEPS; s++) for (let i = 0; i < 20; i++) { const v = forceAt(i, s); for (let j = 0; j < 7; j++) sdk.setPropertyValue(names[i][j], v[j]); }
  console.log(`${"140 setPropertyValue calls only (no run)".padEnd(50)} ${((performance.now() - t0) * 1000 / STEPS).toFixed(2)} us/step`);
}
