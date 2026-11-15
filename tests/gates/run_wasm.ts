// Gate measurements in our WebAssembly build. It only measures; tests/gates/evaluate.py judges.
// usage: JSBSIM_VARIANT=<variant> [JSBSIM_BIN=<dir>] tsx tests/gates/run_wasm.ts <config> [ground] [nasa] [rigid] [flights]
// Output: out/gates/<config>/{ground,rigid}.wasm-<variant>.jsonl, nasa-<hz>.wasm-<variant>.csv, flight-<model>.wasm-<variant>.csv
// The same procedures, in the same order, are in run_native.py. Definitions: gates.json and GATES.md.
import { existsSync, mkdirSync, readFileSync, writeFileSync, appendFileSync } from "node:fs";
import { join } from "node:path";
import { BIN, DATA, ROOT_DIR, copyTree, createSim, currentVariant, describeBuild } from "../../src/wasm.ts";
import type { JSBSim } from "../../src/jsbsim.ts";

const HERE = new URL(".", import.meta.url).pathname;
const G = JSON.parse(readFileSync(join(HERE, "gates.json"), "utf8"));
const CONFIGS = JSON.parse(readFileSync(join(HERE, "configs.json"), "utf8"));
const NASA_COLS: [string, string, string][] = JSON.parse(readFileSync(join(HERE, "../nasa/columns.json"), "utf8"));
const NASA_ROOT = DATA + "check_cases/NASA_EOM_2015/";
type Cfg = { source: string; properties: Record<string, number> };
const msg = (e: unknown) => (e instanceof Error ? `${e.name}: ${e.message}` : `non-Error thrown: ${String(e)}`);

/** Set the configuration's properties. Each must already exist (a missing patch must not pass silently). */
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

/** G1-G3: one aircraft, one scenario, one step rate. dt is set before the model is loaded. */
function groundTrial(sim: JSBSim, cfg: Cfg, model: string, scenario: string, hz: number) {
  const sc = G.scenarios[scenario];
  sim.reset(); sim.setDebugLevel(0);
  sim.dt = 1 / hz;
  sim.loadModel(model);
  sim.loadIC(G.aircraft[model], true);
  for (const [p, v] of Object.entries(sc.ic)) sim.setProperty(p, v as number);
  applyConfig(sim, cfg);
  sim.runIC();
  const nUnits = Math.trunc(sim.getProperty("gear/num-units"));
  // Every contact point: BOGEY (gear/unit[k]/WOW) and STRUCTURE (contact/unit[k]/WOW). Not gear/wow.
  const bogey: string[] = [], struct: string[] = [];
  for (let k = 0; k < nUnits; k++) {
    if (sim.hasProperty(`gear/unit[${k}]/WOW`)) bogey.push(`gear/unit[${k}]/WOW`);
    if (sim.hasProperty(`contact/unit[${k}]/WOW`)) struct.push(`contact/unit[${k}]/WOW`);
  }
  if (bogey.length + struct.length !== nUnits) throw new Error("could not find a WOW property for every contact point");
  const names: string[] = G.state;
  const hs = handles(sim, names), hb = handles(sim, bogey), hstr = handles(sim, struct);
  const ir = G.body_rates.map((p: string) => names.indexOf(p)), ie = G.ecef.map((p: string) => names.indexOf(p));
  const steps = Math.round(sc.seconds * hz), tailStart = steps - Math.round(G.G1.tail_seconds * hz);
  let firstNonfinite: number | null = null, nonfiniteProperty: string | null = null, firstRunaway: number | null = null, firstContact: number | null = null;
  let peak = 0, tailRate = 0, tailDisp = 0, bogeySteps = 0, structSteps = 0, done = 0, tailAlwaysContact = true;
  let ref: number[] = [], up: number[] = [];
  const v = new Array<number>(names.length).fill(0);
  const t0 = performance.now();
  for (let k = 1; k <= steps; k++) {
    const more = sim.run();
    done = k;
    const t = k / hz;
    let bad = -1;
    for (let j = 0; j < hs.length; j++) { v[j] = sim.get(hs[j]); if (bad < 0 && !Number.isFinite(v[j])) bad = j; }
    if (bad >= 0) { firstNonfinite = t; nonfiniteProperty = names[bad]; break; }
    const cb = hb.some((h) => sim.get(h) > 0.5), cs = hstr.some((h) => sim.get(h) > 0.5);
    if (cb) bogeySteps++;
    if (cs) structSteps++;
    if ((cb || cs) && firstContact === null) firstContact = t;
    const w = Math.max(...ir.map((j: number) => Math.abs(v[j])));
    if (w > G.runaway_rate_rad_s && firstRunaway === null) firstRunaway = t;
    peak = Math.max(peak, w);
    if (k >= tailStart) {
      const pos = ie.map((j: number) => v[j]);
      if (k === tailStart) { ref = pos; const r = Math.hypot(...pos); up = pos.map((x: number) => x / r); }
      const d = pos.map((x: number, i: number) => x - ref[i]);
      const dv = d[0] * up[0] + d[1] * up[1] + d[2] * up[2];
      tailDisp = Math.max(tailDisp, Math.sqrt(Math.max(0, d[0] * d[0] + d[1] * d[1] + d[2] * d[2] - dv * dv)));
      tailRate = Math.max(tailRate, w);
      tailAlwaysContact = tailAlwaysContact && (cb || cs);
    }
    if (!more) break;
  }
  return {
    model, scenario, hz, seconds: sc.seconds, steps, steps_done: done, first_nonfinite: firstNonfinite, nonfinite_property: nonfiniteProperty,
    first_runaway: firstRunaway, first_contact: firstContact, bogey_contact_steps: bogeySteps, structure_contact_steps: structSteps,
    contact_points: { bogey: bogey.length, structure: struct.length }, peak_rate: peak, tail_max_rate: tailRate,
    tail_max_horizontal_displacement_ft: tailDisp, tail_always_in_contact: tailAlwaysContact && done === steps,
    end_time: sim.simTime, end_h_agl_ft: v[names.indexOf("position/h-agl-ft")], wall_us_per_step: ((performance.now() - t0) * 1000) / Math.max(done, 1),
  };
}

async function runGround(cfg: Cfg, out: string, platform: string) {
  const file = join(out, `ground.${platform}.jsonl`);
  writeFileSync(file, "");
  let sim = await createSim();
  for (const model of Object.keys(G.aircraft)) for (const scenario of Object.keys(G.scenarios)) for (const hz of G.rates_hz) {
    let rec: Record<string, unknown>;
    try { rec = groundTrial(sim, cfg, model, scenario, hz); }
    catch (e) { rec = { model, scenario, hz, error: msg(e) }; try { sim.delete(); } catch { /* ignore */ } sim = await createSim(); }
    appendFileSync(file, JSON.stringify(rec) + "\n");
    console.log("ground", model, scenario, hz, "error" in rec ? "error" : "ok");
  }
  sim.delete();
}

const conv = (kind: string, v: number) => (kind === "deg" ? v * (180.0 / Math.PI) : kind === "yaw" ? ((v + 180.0) % 360.0) - 180 : v);

/** G4: NASA check case 02 with JSBSim's own unchanged files; dt given to loadScript (before the model loads). */
async function runNasa(cfg: Cfg, out: string, platform: string) {
  const sim = await createSim({ dirs: [] });
  copyTree(sim, NASA_ROOT + "aircraft", "aircraft");
  copyTree(sim, NASA_ROOT + "scripts", "scripts");
  for (const hz of G.G4.rates_hz) {
    const every = hz / 10;
    if (!Number.isInteger(every)) throw new Error("rate must be a multiple of 10 Hz");
    sim.reset(); sim.setDebugLevel(0);
    sim.loadScript("scripts/Atmos_02.xml", 1 / hz);
    applyConfig(sim, cfg);
    sim.runIC();
    const hs = handles(sim, NASA_COLS.map((c) => c[1]));
    const rows = [NASA_COLS.map((c) => c[0]).join(",")];
    for (let k = 0; k <= G.G4.seconds * hz; k++) {
      if (k % every === 0) rows.push(NASA_COLS.map((c, j) => (c[0] === "time" ? k / hz : conv(c[2], sim.get(hs[j]))).toPrecision(17)).join(","));
      if (k < G.G4.seconds * hz) sim.run();
    }
    writeFileSync(join(out, `nasa-${hz}.${platform}.csv`), rows.join("\n") + "\n");
    console.log("nasa", hz, "ok");
  }
  sim.delete();
}

const INERTIA = ["inertia/ixx-slugs_ft2", "inertia/iyy-slugs_ft2", "inertia/izz-slugs_ft2", "inertia/ixy-slugs_ft2", "inertia/ixz-slugs_ft2", "inertia/iyz-slugs_ft2"];
const OMEGA_I = ["velocities/pi-rad_sec", "velocities/qi-rad_sec", "velocities/ri-rad_sec"];

/** G5: torque-free body. T = w.Jw/2 and |H| = |Jw| must stay constant (w = inertial angular velocity, body axes). */
function rigidTrial(sim: JSBSim, cfg: Cfg, body: string, spin: string, hz: number) {
  const g5 = G.G5;
  sim.reset(); sim.setDebugLevel(0);
  sim.dt = 1 / hz;
  sim.loadModel(body);
  sim.loadIC("reset_Atmos_02", true);
  sim.setProperty("ic/h-sl-ft", g5.ic_altitude_ft);
  ["ic/p-rad_sec", "ic/q-rad_sec", "ic/r-rad_sec"].forEach((p, i) => sim.setProperty(p, (g5.spins_deg_s[spin][i] * Math.PI) / 180));
  applyConfig(sim, cfg);
  sim.runIC();
  const [ixx, iyy, izz, ixy, ixz, iyz] = INERTIA.map((p) => sim.getProperty(p));
  // JSBSim's sign convention (FGMassBalance.h): GetIxy = -J(1,2), GetIxz = +J(1,3), GetIyz = -J(2,3).
  // run_native.py checks this convention against FGMassBalance::GetJ.
  const J = [[ixx, -ixy, ixz], [-ixy, iyy, -iyz], [ixz, -iyz, izz]];
  const hw = handles(sim, OMEGA_I);
  const sample = () => {
    const w = hw.map((h) => sim.get(h));
    const hb = J.map((row) => row[0] * w[0] + row[1] * w[1] + row[2] * w[2]);
    return { w, T: 0.5 * (w[0] * hb[0] + w[1] * hb[1] + w[2] * hb[2]), H: Math.hypot(hb[0], hb[1], hb[2]) };
  };
  const s0 = sample();
  let dT = 0, dH = 0, finite = true;
  for (let k = 0; k < g5.seconds * hz; k++) {
    sim.run();
    const s = sample();
    if (!(Number.isFinite(s.T) && Number.isFinite(s.H))) { finite = false; break; }
    dT = Math.max(dT, Math.abs(s.T - s0.T) / s0.T);
    dH = Math.max(dH, Math.abs(s.H - s0.H) / s0.H);
  }
  return {
    body, spin, hz, seconds: g5.seconds, finite, initial_rate_deg_s: s0.w.map((x) => (x * 180) / Math.PI), energy0: s0.T, momentum0: s0.H,
    energy_drift: dT, momentum_magnitude_drift: dH, end_h_agl_ft: sim.getProperty("position/h-agl-ft"),
    total_moment_lbsft: ["moments/l-total-lbsft", "moments/m-total-lbsft", "moments/n-total-lbsft"].map((p) => sim.getProperty(p)),
  };
}

async function runRigid(cfg: Cfg, out: string, platform: string) {
  const file = join(out, `rigid.${platform}.jsonl`);
  writeFileSync(file, "");
  const sim = await createSim({ dirs: [] });
  copyTree(sim, NASA_ROOT + "aircraft/brick", "aircraft/brick");
  sim.writeFile("aircraft/brick_poi/brick_poi.xml", readFileSync(join(HERE, "fixtures/brick_poi.xml")));
  sim.writeFile("aircraft/brick_poi/reset_Atmos_02.xml", readFileSync(NASA_ROOT + "aircraft/brick/reset_Atmos_02.xml"));
  for (const body of G.G5.bodies) for (const spin of Object.keys(G.G5.spins_deg_s)) for (const hz of [...G.G5.report_only_rates_hz, ...G.G5.rates_hz]) {
    let rec: Record<string, unknown>;
    try { rec = rigidTrial(sim, cfg, body, spin, hz); } catch (e) { rec = { body, spin, hz, error: msg(e) }; }
    appendFileSync(file, JSON.stringify(rec) + "\n");
    console.log("rigid", body, spin, hz, "error" in rec ? "error" : "ok");
  }
  sim.delete();
}

/** G6, WebAssembly side: the review's open-loop controlled flights with this configuration's integrators. */
async function runFlights(cfg: Cfg, out: string, platform: string) {
  const g6 = G.G6;
  const sim = await createSim();
  for (const model of g6.models) {
    sim.reset(); sim.setDebugLevel(0);
    sim.dt = 1 / g6.hz;
    sim.loadModel(model);
    for (const [p, v] of Object.entries(g6.initial)) sim.setProperty(p, v as number);
    applyConfig(sim, cfg);
    sim.runIC();
    const hs = handles(sim, g6.properties);
    const hc = (g6.controls as [string, number][]).map(([p, n]) => [sim.handle(p), n] as const);
    const rows = [g6.properties.join(",")];
    const sample = () => rows.push(hs.map((h) => sim.get(h).toPrecision(17)).join(","));
    sample();
    for (let k = 0; k < g6.hz * g6.seconds; k++) {
      for (const [h, n] of hc) sim.set(h, ((Math.floor(k / n) % 3) - 1) / 128);
      if (!sim.run()) throw new Error("run returned false");
      sample();
    }
    writeFileSync(join(out, `flight-${model}.${platform}.csv`), rows.join("\n") + "\n");
    console.log("flight", model, "ok");
  }
  sim.delete();
}

const name = process.argv[2];
const cfg: Cfg = CONFIGS[name];
if (!cfg) throw new Error(`unknown configuration ${name}`);
const want = process.argv.slice(3).length ? process.argv.slice(3) : ["ground", "nasa", "rigid", "flights"];
const variant = currentVariant(), platform = `wasm-${variant}`;
const infoPath = join(BIN, "build-info.json");
const info = existsSync(infoPath) ? JSON.parse(readFileSync(infoPath, "utf8")) : {};
if (info.patchSet !== cfg.source && !process.env.GATES_ALLOW_KEY_MISMATCH)
  throw new Error(`configuration ${name} needs the '${cfg.source}' WebAssembly build, but ${BIN} is '${info.patchSet}' (unpatched: JSBSIM_BIN=build/wasm-bin-unpatched)`);
const out = join(ROOT_DIR, "out/gates", name);
mkdirSync(out, { recursive: true });
writeFileSync(join(out, `${platform}.info.json`), JSON.stringify({ config: name, properties: cfg.properties, build: describeBuild(variant), patchSet: info.patchSet, patches: info.patches ?? [] }, null, 1));
console.log(`# gates, ${platform}, configuration ${name}: ${describeBuild(variant)}`);
for (const part of want) await ({ ground: runGround, nasa: runNasa, rigid: runRigid, flights: runFlights } as Record<string, (c: Cfg, o: string, p: string) => Promise<void>>)[part](cfg, out, platform);
