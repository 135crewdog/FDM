// Session 05: cost per physics step in Node for a configuration AT ITS OWN STEP RATES (configs.json, rates_05).
// No gate. The frozen cost.ts measures at 120 and 1000 Hz only; this is the same workload at other rates.
// usage: JSBSIM_VARIANT=jsbsim-weh [JSBSIM_BIN=<dir>] tsx tests/gates/cost05.ts <config> [<config> ...]
// Prints one line per configuration and rate: microseconds per step (median of 7 identical repetitions) for the
// c172x and the f16, flying and standing on the ground, and what one second of flight costs at that rate.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createSim, describeBuild } from "../../src/wasm.ts";

const HERE = new URL(".", import.meta.url).pathname;
const G = JSON.parse(readFileSync(join(HERE, "gates.json"), "utf8"));
const CONFIGS = JSON.parse(readFileSync(join(HERE, "configs.json"), "utf8"));
const C = G.cost;
const sim = await createSim();
const median = (a: number[]) => [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)]!;
console.log(`# Cost per step in Node, ${describeBuild()}`);
console.log("| configuration | step rate | c172x flying, on the ground (us/step) | f16 flying, on the ground (us/step) | one second of c172x flight costs |");
console.log("|---|---|---|---|---|");
for (const name of process.argv.slice(2)) {
  const cfg = CONFIGS[name];
  for (const hz of cfg.rates_05 as number[]) {
    const cell: Record<string, number> = {};
    for (const model of ["c172x", "f16"]) for (const kind of ["flight", "ground"]) {
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
        times.push(((performance.now() - t0) * 1000) / n);
        if (n !== C.timed_steps || !Number.isFinite(sim.getProperty("position/h-sl-ft"))) throw new Error("invalid timing run");
      }
      cell[`${model} ${kind}`] = median(times);
    }
    console.log(`| \`${name}\` | ${hz} Hz | ${cell["c172x flight"]!.toFixed(1)}, ${cell["c172x ground"]!.toFixed(1)} | ${cell["f16 flight"]!.toFixed(1)}, ${cell["f16 ground"]!.toFixed(1)} | ${(cell["c172x flight"]! * hz / 1000).toFixed(1)} ms |`);
  }
}
sim.delete();
