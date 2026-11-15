// Later gates of session 04, measurements in our WebAssembly build. It only measures; evaluate_04.py judges.
// usage: JSBSIM_VARIANT=jsbsim-weh [JSBSIM_BIN=<dir>] tsx tests/gates/run_wasm_04.ts <config> [rigidb] [repeat] [--models a,b,...]
// Output: out/gates/<config>/rigidb.wasm-<variant>.jsonl, repeat.wasm-<variant>.<model>.jsonl
// The same procedures, in the same order, are in run_native_04.py. Definitions: gates-04.json and GATES-04.md;
// everything else comes from the frozen gates.json. Set-up and per-step checks follow the frozen run_wasm.ts.
import { existsSync, mkdirSync, readFileSync, writeFileSync, appendFileSync } from "node:fs";
import { join } from "node:path";
import { BIN, DATA, ROOT_DIR, copyTree, createSim, currentVariant, describeBuild } from "../../src/wasm.ts";
import type { JSBSim } from "../../src/jsbsim.ts";

const HERE = new URL(".", import.meta.url).pathname;
const G = JSON.parse(readFileSync(join(HERE, "gates.json"), "utf8"));
const G4 = JSON.parse(readFileSync(join(HERE, "gates-04.json"), "utf8"));
const CONFIGS = JSON.parse(readFileSync(join(HERE, "configs.json"), "utf8"));
const NASA_ROOT = DATA + "check_cases/NASA_EOM_2015/";
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

const INERTIA = ["inertia/ixx-slugs_ft2", "inertia/iyy-slugs_ft2", "inertia/izz-slugs_ft2", "inertia/ixy-slugs_ft2", "inertia/ixz-slugs_ft2", "inertia/iyz-slugs_ft2"];
const OMEGA_I = ["velocities/pi-rad_sec", "velocities/qi-rad_sec", "velocities/ri-rad_sec"];

/** G5b: G5's body, spin and set-up; drift of T = w.Jw/2 and |H| = |Jw| against their values at measure_from_seconds. */
function rigidbTrial(sim: JSBSim, cfg: Cfg, body: string, spin: string, hz: number) {
  const g5 = G.G5, g5b = G4.G5b;
  sim.reset(); sim.setDebugLevel(0);
  sim.dt = 1 / hz;
  sim.loadModel(body);
  sim.loadIC("reset_Atmos_02", true);
  sim.setProperty("ic/h-sl-ft", g5.ic_altitude_ft);
  ["ic/p-rad_sec", "ic/q-rad_sec", "ic/r-rad_sec"].forEach((p, i) => sim.setProperty(p, (g5.spins_deg_s[spin][i] * Math.PI) / 180));
  applyConfig(sim, cfg);
  sim.runIC();
  const [ixx, iyy, izz, ixy, ixz, iyz] = INERTIA.map((p) => sim.getProperty(p));
  const J = [[ixx, -ixy, ixz], [-ixy, iyy, -iyz], [ixz, -iyz, izz]];
  const hw = handles(sim, OMEGA_I);
  const sample = () => {
    const w = hw.map((h) => sim.get(h));
    const hb = J.map((row) => row[0] * w[0] + row[1] * w[1] + row[2] * w[2]);
    return { T: 0.5 * (w[0] * hb[0] + w[1] * hb[1] + w[2] * hb[2]), H: Math.hypot(hb[0], hb[1], hb[2]) };
  };
  const s0 = sample();
  const kRef = Math.round(g5b.measure_from_seconds * hz), steps = Math.round(g5b.seconds * hz);
  let Tr = NaN, Hr = NaN, dT = 0, dH = 0, dT0 = 0, dH0 = 0, finite = true;
  for (let k = 1; k <= steps; k++) {
    sim.run();
    const s = sample();
    if (!(Number.isFinite(s.T) && Number.isFinite(s.H))) { finite = false; break; }
    dT0 = Math.max(dT0, Math.abs(s.T - s0.T) / s0.T);
    dH0 = Math.max(dH0, Math.abs(s.H - s0.H) / s0.H);
    if (k === kRef) { Tr = s.T; Hr = s.H; }
    else if (k > kRef) { dT = Math.max(dT, Math.abs(s.T - Tr) / Tr); dH = Math.max(dH, Math.abs(s.H - Hr) / Hr); }
  }
  return {
    body, spin, hz, seconds: g5b.seconds, measure_from_seconds: g5b.measure_from_seconds, finite,
    energy_drift: dT, momentum_magnitude_drift: dH, energy_drift_from_start: dT0, momentum_magnitude_drift_from_start: dH0,
    end_h_agl_ft: sim.getProperty("position/h-agl-ft"),
  };
}

async function runRigidb(cfg: Cfg, out: string, platform: string, _models: string[]) {
  const file = join(out, `rigidb.${platform}.jsonl`);
  writeFileSync(file, "");
  const sim = await createSim({ dirs: [] });
  copyTree(sim, NASA_ROOT + "aircraft/brick", "aircraft/brick");
  sim.writeFile("aircraft/brick_poi/brick_poi.xml", readFileSync(join(HERE, "fixtures/brick_poi.xml")));
  sim.writeFile("aircraft/brick_poi/reset_Atmos_02.xml", readFileSync(NASA_ROOT + "aircraft/brick/reset_Atmos_02.xml"));
  for (const body of G.G5.bodies) for (const spin of Object.keys(G.G5.spins_deg_s)) for (const hz of [...G.G5.report_only_rates_hz, ...G.G5.rates_hz]) {
    let rec: Record<string, unknown>;
    try { rec = rigidbTrial(sim, cfg, body, spin, hz); } catch (e) { rec = { body, spin, hz, error: msg(e) }; }
    appendFileSync(file, JSON.stringify(rec) + "\n");
    console.log("rigidb", body, spin, hz, "error" in rec ? "error" : "ok");
  }
  sim.delete();
}

/** G2b/G3b: G2's set-up and per-step checks, with the run's perturbation added to the scenario's initial conditions. */
function repeatTrial(sim: JSBSim, cfg: Cfg, model: string, scenario: string, hz: number, run: number) {
  const sc = G.scenarios[scenario], rp = G4.repeats;
  const ic: Record<string, number> = { ...sc.ic };
  rp.perturbed_properties.forEach((p: string, i: number) => { ic[p] = ic[p] + rp.draws[run][i]; });
  sim.reset(); sim.setDebugLevel(0);
  sim.dt = 1 / hz;
  sim.loadModel(model);
  sim.loadIC(G.aircraft[model], true);
  for (const [p, v] of Object.entries(ic)) sim.setProperty(p, v);
  applyConfig(sim, cfg);
  sim.runIC();
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
    model, scenario, hz, run, ic, steps, steps_done: done, first_nonfinite: firstNonfinite, nonfinite_property: nonfiniteProperty,
    first_runaway: firstRunaway, first_contact: firstContact, contact_steps: contactSteps, peak_rate: peak,
  };
}

async function runRepeat(cfg: Cfg, out: string, platform: string, models: string[]) {
  const scenarios: string[] = [G4.G2b.scenario, ...G4.G3b.scenarios];
  let sim = await createSim();
  for (const model of models) {
    const file = join(out, `repeat.${platform}.${model}.jsonl`);
    writeFileSync(file, "");
    for (const scenario of scenarios) for (const hz of G.rates_hz) {
      for (let run = 0; run < G4.repeats.draws.length; run++) {
        let rec: Record<string, unknown>;
        try { rec = repeatTrial(sim, cfg, model, scenario, hz, run); }
        catch (e) { rec = { model, scenario, hz, run, error: msg(e) }; try { sim.delete(); } catch { /* ignore */ } sim = await createSim(); }
        appendFileSync(file, JSON.stringify(rec) + "\n");
      }
      console.log("repeat", model, scenario, hz, "done");
    }
  }
  sim.delete();
}

const argv = process.argv.slice(2);
let models: string[] = Object.keys(G.aircraft);
const mi = argv.indexOf("--models");
if (mi >= 0) { models = argv[mi + 1].split(","); argv.splice(mi, 2); }
const name = argv[0];
const cfg: Cfg = CONFIGS[name];
if (!cfg) throw new Error(`unknown configuration ${name}`);
const want = argv.slice(1).length ? argv.slice(1) : ["rigidb", "repeat"];
const variant = currentVariant(), platform = `wasm-${variant}`;
const infoPath = join(BIN, "build-info.json");
const info = existsSync(infoPath) ? JSON.parse(readFileSync(infoPath, "utf8")) : {};
if (info.patchSet !== cfg.source)
  throw new Error(`configuration ${name} needs the '${cfg.source}' WebAssembly build, but ${BIN} is '${info.patchSet}' (unpatched: JSBSIM_BIN=build/wasm-bin-unpatched)`);
const out = join(ROOT_DIR, "out/gates", name);
mkdirSync(out, { recursive: true });
writeFileSync(join(out, `${platform}.info04.json`), JSON.stringify({ config: name, properties: cfg.properties, build: describeBuild(variant), patchSet: info.patchSet, patches: info.patches ?? [] }, null, 1));
console.log(`# later gates, ${platform}, configuration ${name}: ${describeBuild(variant)}`);
for (const part of want) await ({ rigidb: runRigidb, repeat: runRepeat } as Record<string, (c: Cfg, o: string, p: string, m: string[]) => Promise<void>>)[part](cfg, out, platform, models);
