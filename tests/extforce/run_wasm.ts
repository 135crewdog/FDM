// Test 3 in our WebAssembly build.
//  parity: tsx run_wasm.ts parity <out.csv> [zero]   (1 force, schedule applied every step; "zero" = magnitude 0)
//  bench:  tsx run_wasm.ts bench                       (20 forces updated every step: by name, by handle, bulk)
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { createSim, currentVariant, LOG_PROPS, sample, toCsv } from "../../src/wasm.ts";
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
console.error(`extforce ${mode}: variant ${currentVariant()}`);
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
  // Every case and every repetition runs the SAME workload: a fresh instance state (reset, load, runIC),
  // the same warm-up, then the same STEPS steps with the same force schedule (k starts at 0 each time).
  // The "no external forces" case uses an aircraft with no <force> at all (c172p_ext0).
  const STEPS = 6000, WARMUP = 600, REPS = 5, N = 20;
  const names = Array.from({ length: N }, (_, i) => SUFFIX.map((s) => `external_reactions/f${i}/${s}`));
  type M = "none" | "name" | "handle" | "bulk";
  const cases: [string, string, M][] = [
    ["c172p, no external forces", "scripts/ext_c172p_ext0.xml", "none"],
    ["c172p + 20 forces, not updated", "scripts/ext_c172p_ext20.xml", "none"],
    ["c172p + 20 forces updated by name (140 writes)", "scripts/ext_c172p_ext20.xml", "name"],
    ["c172p + 20 forces updated by cached handle", "scripts/ext_c172p_ext20.xml", "handle"],
    ["c172p + 20 forces updated by bulk array", "scripts/ext_c172p_ext20.xml", "bulk"],
  ];
  const END = [...LOG_PROPS, "position/lat-gc-rad", "position/long-gc-rad", "velocities/u-fps", "velocities/v-fps", "velocities/w-fps"];
  const median = (a: number[]) => [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)];
  const finals: Record<string, string> = {};
  console.log(`workload per repetition: fresh load, ${WARMUP} warm-up steps, then ${STEPS} timed steps; ${REPS} repetitions`);
  for (const [label, script, method] of cases) {
    const times: number[] = [];
    let end = "";
    for (let r = 0; r < REPS; r++) {
      const sim = await setup(script);
      const hs = method === "handle" ? names.map((row) => row.map((n) => sim.handle(n))) : [];
      if (method === "bulk") { sim.bindInputs(names.flat()); sim.bindOutputs([]); }
      const stepFn = (k: number) => {
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
      };
      for (let k = 0; k < WARMUP; k++) stepFn(k);
      const t0 = performance.now();
      for (let k = WARMUP; k < WARMUP + STEPS; k++) stepFn(k);
      times.push((performance.now() - t0) * 1000 / STEPS);
      const e = JSON.stringify(sample(sim, END));
      if (r > 0 && e !== end) throw new Error(`${label}: repetitions ended in different states (not the same workload)`);
      end = e;
    }
    finals[`${script}|${method}`] = end;
    console.log(`${label.padEnd(50)} median ${median(times).toFixed(2)} us/step, min ${Math.min(...times).toFixed(2)}, max ${Math.max(...times).toFixed(2)}`);
  }
  const f = (m: M) => finals[`scripts/ext_c172p_ext20.xml|${m}`];
  console.log(`same full end state (${END.length} properties) by name / handle / bulk: ${f("name") === f("handle") && f("handle") === f("bulk")}`);
  // The writes alone (no physics), to separate binding cost from physics cost.
  const sim = await setup("scripts/ext_c172p_ext20.xml");
  const hs = names.map((r) => r.map((n) => sim.handle(n)));
  sim.bindInputs(names.flat());
  const vals = Array.from({ length: STEPS }, (_, s) => Array.from({ length: N }, (_, i) => { const v = forceAt(i, s); v[6] *= 0.1; return v; }));
  const time = (fn: (s: number) => void) => { const t: number[] = []; for (let r = 0; r < REPS; r++) { const t0 = performance.now(); for (let s = 0; s < STEPS; s++) fn(s); t.push((performance.now() - t0) * 1000 / STEPS); } return median(t); };
  const tName = time((s) => { for (let i = 0; i < N; i++) for (let j = 0; j < 7; j++) sim.setProperty(names[i][j], vals[s][i][j]); });
  const tHandle = time((s) => { for (let i = 0; i < N; i++) for (let j = 0; j < 7; j++) sim.set(hs[i][j], vals[s][i][j]); });
  const tBulk = time((s) => { const inp = sim.inputs; for (let i = 0; i < N; i++) for (let j = 0; j < 7; j++) inp[i * 7 + j] = vals[s][i][j]; sim.applyInputs(); });
  console.log(`writes only, the same 140 values per step (median of ${REPS}): by name ${tName.toFixed(2)} us, by handle ${tHandle.toFixed(2)} us, bulk ${tBulk.toFixed(2)} us`);
}
