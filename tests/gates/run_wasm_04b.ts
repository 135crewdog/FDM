// G2c (GATES-04b.md), measurements in our WebAssembly build. It only measures.
// usage: JSBSIM_VARIANT=jsbsim-weh [JSBSIM_BIN=<dir>] tsx tests/gates/run_wasm_04b.ts <config> [--models a,b,...]
// Output: out/gates/<config>/forward.wasm-<variant>.<model>.jsonl
// The trial is the one of run_wasm_04.ts (repeatTrial: same set-up, same per-step checks, same perturbation draws);
// only the scenario differs: the heading is set to north first, so that "100 ft/s north" really is forward.
// The start is checked: body velocity must be (100, 0, 30) ft/s, or the run is recorded as an error.
import { existsSync, mkdirSync, readFileSync, writeFileSync, appendFileSync } from "node:fs";
import { join } from "node:path";
import { BIN, ROOT_DIR, createSim, currentVariant, describeBuild } from "../../src/wasm.ts";
import type { JSBSim } from "../../src/jsbsim.ts";

const HERE = new URL(".", import.meta.url).pathname;
const G = JSON.parse(readFileSync(join(HERE, "gates.json"), "utf8"));
const G4 = JSON.parse(readFileSync(join(HERE, "gates-04.json"), "utf8"));
const G2C = JSON.parse(readFileSync(join(HERE, "gates-04b.json"), "utf8")).G2c;
const CONFIGS = JSON.parse(readFileSync(join(HERE, "configs.json"), "utf8"));
type Cfg = { source: string; properties: Record<string, number> };
const msg = (e: unknown) => (e instanceof Error ? `${e.name}: ${e.message}` : `non-Error thrown: ${String(e)}`);

function applyConfig(sim: JSBSim, cfg: Cfg) {
  for (const [p, v] of Object.entries(cfg.properties)) {
    if (!sim.hasProperty(p)) throw new Error(`property ${p} does not exist in this build (wrong source for this configuration?)`);
    sim.setProperty(p, v);
    if (sim.getProperty(p) !== v) throw new Error(`property ${p} did not take the value ${v} (reads ${sim.getProperty(p)})`);
  }
}
function handles(sim: JSBSim, names: string[]): number[] {
  return names.map((n) => { if (!sim.hasProperty(n)) throw new Error(`property ${n} does not exist`); return sim.handle(n); });
}
function setUp(sim: JSBSim, cfg: Cfg, model: string, hz: number, ic: Record<string, number>) {
  sim.reset(); sim.setDebugLevel(0);
  sim.dt = 1 / hz;
  sim.loadModel(model);
  sim.loadIC(G.aircraft[model], true);
  for (const [p, v] of Object.entries(ic)) sim.setProperty(p, v);
  applyConfig(sim, cfg);
  sim.runIC();
}

/** Same as repeatTrial in run_wasm_04.ts, for the scenario given here. */
function trial(sim: JSBSim, cfg: Cfg, model: string, hz: number, run: number) {
  const sc = G2C.scenario_definition, rp = G4.repeats;
  const ic: Record<string, number> = { ...sc.ic };
  rp.perturbed_properties.forEach((p: string, i: number) => { ic[p] = ic[p] + rp.draws[run][i]; });
  setUp(sim, cfg, model, hz, ic);
  const nUnits = Math.trunc(sim.getProperty("gear/num-units"));
  const wow: string[] = [];
  for (let k = 0; k < nUnits; k++) for (const p of [`gear/unit[${k}]/WOW`, `contact/unit[${k}]/WOW`]) if (sim.hasProperty(p)) wow.push(p);
  if (wow.length !== nUnits) throw new Error("could not find a WOW property for every contact point");
  const names: string[] = G.state;
  const hs = handles(sim, names), hw = handles(sim, wow);
  const ir = G.body_rates.map((p: string) => names.indexOf(p));
  const steps = Math.round(sc.seconds * hz);
  let firstNonfinite: number | null = null, nonfiniteProperty: string | null = null, firstRunaway: number | null = null, firstContact: number | null = null;
  let peak = 0, done = 0, contactSteps = 0;
  const v = new Array<number>(names.length).fill(0);
  for (let k = 1; k <= steps; k++) {
    const more = sim.run();
    done = k;
    let bad = -1;
    for (let j = 0; j < hs.length; j++) { v[j] = sim.get(hs[j]); if (bad < 0 && !Number.isFinite(v[j])) bad = j; }
    if (bad >= 0) { firstNonfinite = k / hz; nonfiniteProperty = names[bad]; break; }
    if (hw.some((h) => sim.get(h) > 0.5)) { contactSteps++; if (firstContact === null) firstContact = k / hz; }
    const w = Math.max(...ir.map((j: number) => Math.abs(v[j])));
    if (w > G.runaway_rate_rad_s && firstRunaway === null) firstRunaway = k / hz;
    peak = Math.max(peak, w);
    if (!more) break;
  }
  return {
    model, scenario: G2C.scenario, hz, run, ic, steps, steps_done: done, first_nonfinite: firstNonfinite, nonfinite_property: nonfiniteProperty,
    first_runaway: firstRunaway, first_contact: firstContact, contact_steps: contactSteps, peak_rate: peak,
  };
}

const argv = process.argv.slice(2);
let models: string[] = Object.keys(G.aircraft);
const mi = argv.indexOf("--models");
if (mi >= 0) { models = argv[mi + 1].split(","); argv.splice(mi, 2); }
const name = argv[0];
const cfg: Cfg = CONFIGS[name];
if (!cfg) throw new Error(`unknown configuration ${name}`);
const variant = currentVariant(), platform = `wasm-${variant}`;
const infoPath = join(BIN, "build-info.json");
const info = existsSync(infoPath) ? JSON.parse(readFileSync(infoPath, "utf8")) : {};
if (info.patchSet !== cfg.source) throw new Error(`configuration ${name} needs the '${cfg.source}' WebAssembly build, but ${BIN} is '${info.patchSet}'`);
const out = join(ROOT_DIR, "out/gates", name);
mkdirSync(out, { recursive: true });
console.log(`# G2c, ${platform}, configuration ${name}: ${describeBuild(variant)}`);
let sim = await createSim();
const want: number[] = G2C.required_start_body_velocity_fps, tol: number = G2C.start_body_velocity_tolerance_fps;
for (const model of models) {
  const file = join(out, `forward.${platform}.${model}.jsonl`);
  writeFileSync(file, "");
  for (const hz of G.rates_hz) {
    setUp(sim, cfg, model, hz, G2C.scenario_definition.ic);
    const uvw = ["velocities/u-fps", "velocities/v-fps", "velocities/w-fps"].map((p) => sim.getProperty(p));
    const forward = uvw.every((x, i) => Math.abs(x - want[i]) <= tol);
    for (let run = 0; run < G4.repeats.draws.length; run++) {
      let rec: Record<string, unknown>;
      try {
        if (!forward) throw new Error(`start is not a forward landing: body velocity ${uvw}`);
        rec = trial(sim, cfg, model, hz, run);
      } catch (e) { rec = { model, scenario: G2C.scenario, hz, run, error: msg(e) }; try { sim.delete(); } catch { /* ignore */ } sim = await createSim(); }
      rec.start_body_velocity_fps = uvw;
      appendFileSync(file, JSON.stringify(rec) + "\n");
    }
    console.log("forward", model, hz, "done");
  }
}
sim.delete();
