// Cost per step in Node for one configuration (no gate; the iPhone runs the same WebAssembly, so the
// RATIO between configurations is what carries over, not the absolute numbers).
// usage: JSBSIM_VARIANT=jsbsim-weh [JSBSIM_BIN=<dir>] tsx tests/gates/cost.ts <config>
// Every repetition is the same workload: fresh load, the same warm-up, the same timed steps.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { ROOT_DIR, createSim, currentVariant, describeBuild } from "../../src/wasm.ts";

const HERE = new URL(".", import.meta.url).pathname;
const G = JSON.parse(readFileSync(join(HERE, "gates.json"), "utf8"));
const cfg = JSON.parse(readFileSync(join(HERE, "configs.json"), "utf8"))[process.argv[2]];
const C = G.cost;
const sim = await createSim();
const median = (a: number[]) => [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)];
const rows: string[] = [];
for (const hz of C.hz) for (const [kind, models] of [["flight", C.flight_models], ["ground at rest", C.ground_models]] as const) for (const model of models) {
  const times: number[] = [];
  for (let rep = 0; rep < C.repetitions; rep++) {
    sim.reset(); sim.setDebugLevel(0);
    sim.dt = 1 / hz;
    sim.loadModel(model);
    if (kind === "flight") for (const [p, v] of Object.entries(C.flight_initial)) sim.setProperty(p, v as number);
    else sim.loadIC(G.aircraft[model], true);
    for (const [p, v] of Object.entries(cfg.properties)) { if (!sim.hasProperty(p)) throw new Error(`no property ${p}`); sim.setProperty(p, v as number); }
    sim.runIC();
    sim.runSteps(C.warmup_steps);
    const t0 = performance.now();
    const n = sim.runSteps(C.timed_steps);
    const us = ((performance.now() - t0) * 1000) / n;
    if (n !== C.timed_steps || !Number.isFinite(sim.getProperty("position/h-sl-ft"))) throw new Error("invalid timing run");
    times.push(us);
  }
  const rec = { config: process.argv[2], kind, model, hz, median_us_per_step: median(times), min_us_per_step: Math.min(...times), max_us_per_step: Math.max(...times) };
  rows.push(JSON.stringify(rec));
  console.log(`cost ${kind} ${model} ${hz} Hz: median ${rec.median_us_per_step.toFixed(2)} us/step (min ${rec.min_us_per_step.toFixed(2)}, max ${rec.max_us_per_step.toFixed(2)}) [${describeBuild(currentVariant())}]`);
}
const out = join(ROOT_DIR, "out/gates", process.argv[2]);
mkdirSync(out, { recursive: true });
writeFileSync(join(out, `cost.wasm-${currentVariant()}.jsonl`), rows.join("\n") + "\n");
sim.delete();
