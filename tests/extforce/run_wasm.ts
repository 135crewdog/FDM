// Test 3 in our WebAssembly build.
//  parity: tsx run_wasm.ts parity <out.csv> [zero]   (1 force, schedule applied every step; "zero" = magnitude 0)
//  bench:  tsx run_wasm.ts bench                       (20 forces updated every step: by name, by handle, bulk)
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { createSim, LOG_PROPS, sample, toCsv } from "../../src/wasm.ts";
import { forceAt, SUFFIX } from "./schedule.ts";
import type { JSBSim } from "../../src/jsbsim.ts";

const EXTRA = ["forces/fbx-external-lbs", "forces/fby-external-lbs", "forces/fbz-external-lbs",
  "moments/l-external-lbsft", "moments/m-external-lbsft", "moments/n-external-lbsft"];
const PROPS = [...LOG_PROPS, ...EXTRA];

let shared: JSBSim | undefined;
async function setup(script: string): Promise<JSBSim> {
  shared ??= await createSim();
  shared.reset();
  shared.setDebugLevel(0);
  shared.loadScript(script);
  shared.runIC();
  return shared;
}

const [mode, out, variant] = process.argv.slice(2);
if (mode === "parity") {
  const sim = await setup("scripts/ext_c172p_ext1.xml");
  const names = SUFFIX.map((s) => `external_reactions/f0/${s}`);
  const rows = [sample(sim, PROPS)];
  for (let k = 0; k < 3600; k++) {          // 30 s at 120 Hz
    const v = forceAt(0, k);
    if (variant === "zero") v[6] = 0;
    for (let j = 0; j < 7; j++) sim.setProperty(names[j], v[j]);
    sim.run();
    rows.push(sample(sim, PROPS));
  }
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, toCsv(PROPS, rows));
} else if (mode === "bench") {
  const STEPS = 6000, REPS = 5, N = 20;
  const names = Array.from({ length: N }, (_, i) => SUFFIX.map((s) => `external_reactions/f${i}/${s}`));
  type M = "none" | "name" | "handle" | "bulk";
  const cases: [string, string, M][] = [
    ["c172p, no external forces", "scripts/ext_c172p_ext1.xml", "none"],
    ["c172p + 20 forces, not updated", "scripts/ext_c172p_ext20.xml", "none"],
    ["c172p + 20 forces updated by name (140 writes)", "scripts/ext_c172p_ext20.xml", "name"],
    ["c172p + 20 forces updated by cached handle", "scripts/ext_c172p_ext20.xml", "handle"],
    ["c172p + 20 forces updated by bulk array", "scripts/ext_c172p_ext20.xml", "bulk"],
  ];
  const finals: Record<string, number[]> = {};
  for (const [label, script, method] of cases) {
    const sim = await setup(script);
    const hs = method === "handle" ? names.map((r) => r.map((n) => sim.handle(n))) : [];
    if (method === "bulk") { sim.bindInputs(names.flat()); sim.bindOutputs([]); }
    let best = Infinity, k = 0;
    for (let r = 0; r < REPS; r++) {
      const t0 = performance.now();
      for (let s = 0; s < STEPS; s++, k++) {
        if (method === "name") {
          for (let i = 0; i < N; i++) { const v = forceAt(i, k); v[6] *= 0.1; for (let j = 0; j < 7; j++) sim.setProperty(names[i][j], v[j]); }
          sim.run();
        } else if (method === "handle") {
          for (let i = 0; i < N; i++) { const v = forceAt(i, k); v[6] *= 0.1; for (let j = 0; j < 7; j++) sim.set(hs[i][j], v[j]); }
          sim.run();
        } else if (method === "bulk") {
          const inp = sim.inputs;
          for (let i = 0; i < N; i++) { const v = forceAt(i, k); v[6] *= 0.1; for (let j = 0; j < 7; j++) inp[i * 7 + j] = v[j]; }
          sim.step(1);
        } else sim.run();
      }
      best = Math.min(best, (performance.now() - t0) * 1000 / STEPS);
    }
    finals[method] = [sim.getProperty("position/h-sl-ft"), sim.getProperty("velocities/vtrue-kts")];
    console.log(`${label.padEnd(50)} ${best.toFixed(2)} us/step (best of ${REPS} x ${STEPS})`);
  }
  console.log(`same end state by name / handle / bulk: ${JSON.stringify(finals.name) === JSON.stringify(finals.handle) && JSON.stringify(finals.handle) === JSON.stringify(finals.bulk)} (alt ft, kts = ${finals.bulk.map((x) => x.toFixed(6)).join(", ")})`);
  // The writes alone (no physics), to separate binding cost from physics cost.
  const sim = await setup("scripts/ext_c172p_ext20.xml");
  const hs = names.map((r) => r.map((n) => sim.handle(n)));
  sim.bindInputs(names.flat());
  const vals = Array.from({ length: STEPS }, (_, s) => Array.from({ length: N }, (_, i) => { const v = forceAt(i, s); v[6] *= 0.1; return v; }));
  const time = (f: (s: number) => void) => { let best = Infinity; for (let r = 0; r < REPS; r++) { const t0 = performance.now(); for (let s = 0; s < STEPS; s++) f(s); best = Math.min(best, (performance.now() - t0) * 1000 / STEPS); } return best; };
  const tName = time((s) => { for (let i = 0; i < N; i++) for (let j = 0; j < 7; j++) sim.setProperty(names[i][j], vals[s][i][j]); });
  const tHandle = time((s) => { for (let i = 0; i < N; i++) for (let j = 0; j < 7; j++) sim.set(hs[i][j], vals[s][i][j]); });
  const tBulk = time((s) => { const inp = sim.inputs; for (let i = 0; i < N; i++) for (let j = 0; j < 7; j++) inp[i * 7 + j] = vals[s][i][j]; sim.applyInputs(); });
  console.log(`writes only, 140 values per step: by name ${tName.toFixed(2)} us, by handle ${tHandle.toFixed(2)} us, bulk ${tBulk.toFixed(2)} us`);
}
