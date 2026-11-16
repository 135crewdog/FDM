// Session 05: the measuring procedures, WebAssembly side. The same procedures, statement for statement, as
// tests/gates/sim05.py (native). A procedure sets a simulation up from gates-05.json, steps it, and after EVERY
// step appends one row of numbers to a raw file (float64, little endian). It judges nothing:
// tests/gates/evaluate_05.py reads the rows of both platforms and applies the limits.
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { JSBSim } from "../../src/jsbsim.ts";

const HERE = new URL(".", import.meta.url).pathname;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const G5: any = JSON.parse(readFileSync(join(HERE, "gates-05.json"), "utf8"));
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const CONFIGS: any = JSON.parse(readFileSync(join(HERE, "configs.json"), "utf8"));
const COMMON: string[] = G5.columns;
const UNIT_COLS: string[] = G5.unit_columns;
const D2R = Math.PI / 180;
export type Cfg = { source: string; properties: Record<string, number> };
type Props = Record<string, number>;
const msg = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** Set the configuration's properties. Each must already exist (a missing patch must not pass silently). */
export function applyConfig(sim: JSBSim, cfg: Cfg) {
  for (const [p, v] of Object.entries(cfg.properties)) {
    if (!sim.hasProperty(p)) throw new Error(`property ${p} does not exist in this build (wrong source for this configuration?)`);
    sim.setProperty(p, v);
    if (sim.getProperty(p) !== v) throw new Error(`property ${p} did not take the value ${v} (reads ${sim.getProperty(p)})`);
  }
}
/** The candidate's settings must survive everything the fixture does before the measured part starts. */
function checkConfig(sim: JSBSim, cfg: Cfg) {
  for (const [p, v] of Object.entries(cfg.properties))
    if (sim.getProperty(p) !== v) throw new Error(`property ${p} no longer has the value ${v} (reads ${sim.getProperty(p)})`);
}
function setProps(sim: JSBSim, props: Props) {
  for (const [p, v] of Object.entries(props)) {
    if (!sim.hasProperty(p)) throw new Error(`property ${p} does not exist`);
    sim.setProperty(p, v); // the wrapper throws for a read-only property
  }
}
const clamp = (x: number, lo: number, hi: number) => (x < lo ? lo : x > hi ? hi : x);

/** A growing table of float64 rows, written as one raw file. */
class Table {
  private chunks: Float64Array[] = [];
  private cur: Float64Array;
  private n = 0;
  count = 0;
  constructor(readonly width: number) { this.cur = new Float64Array(width * 4096); }
  push(row: ArrayLike<number>) {
    if (this.n === this.cur.length) { this.chunks.push(this.cur); this.cur = new Float64Array(this.width * 4096); this.n = 0; }
    this.cur.set(row, this.n); this.n += this.width; this.count++;
  }
  write(path: string) {
    const total = this.chunks.reduce((a, c) => a + c.length, 0) + this.n;
    const all = new Float64Array(total);
    let o = 0;
    for (const c of this.chunks) { all.set(c, o); o += c.length; }
    all.set(this.cur.subarray(0, this.n), o);
    writeFileSync(path, new Uint8Array(all.buffer));
  }
}

/** Per-step rows. The header (column names, constants) goes into a .json next to the raw file. */
class Rows {
  units: string[] = [];
  names: string[];
  bogey: boolean[];
  wowIdx: number[];
  private hs: number[];
  private table: Table;
  private v: Float64Array;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  meta: any;
  constructor(private sim: JSBSim, private path: string, extra: object) {
    const n = Math.trunc(sim.getProperty("gear/num-units"));
    for (let k = 0; k < n; k++) {
      const base = sim.hasProperty(`gear/unit[${k}]/WOW`) ? `gear/unit[${k}]` : `contact/unit[${k}]`;
      if (!sim.hasProperty(base + "/WOW")) throw new Error(`no WOW property for contact point ${k}`);
      this.units.push(base);
    }
    this.names = [...COMMON, ...this.units.flatMap((u) => UNIT_COLS.map((c) => `${u}/${c}`))];
    this.hs = this.names.map((p) => { if (!sim.hasProperty(p)) throw new Error(`property ${p} does not exist`); return sim.handle(p); });
    this.table = new Table(this.names.length);
    this.v = new Float64Array(this.names.length);
    this.wowIdx = this.units.map((_, k) => COMMON.length + 4 * k);
    this.bogey = this.units.map((u) => u.startsWith("gear/"));
    const inertia: Props = {};
    for (const k of ["ixx", "iyy", "izz", "ixy", "ixz", "iyz"]) inertia[k] = sim.getProperty(`inertia/${k}-slugs_ft2`);
    this.meta = {
      columns: this.names, units: this.units, bogey: this.bogey, mass_slugs: sim.getProperty("inertia/mass-slugs"), weight_lbs: sim.getProperty("inertia/weight-lbs"),
      inertia, cg_in: ["x", "y", "z"].map((a) => sim.getProperty(`inertia/cg-${a}-in`)), unit_z_in: this.units.map((u) => sim.getProperty(u + "/z-position")),
      dt: sim.dt, ...extra,
    };
  }
  row(): Float64Array {
    const { sim, hs, v } = this;
    for (let j = 0; j < hs.length; j++) v[j] = sim.get(hs[j]!);
    this.table.push(v);
    return v;
  }
  close(more: object) {
    this.table.write(this.path);
    Object.assign(this.meta, { rows: this.table.count }, more);
    writeFileSync(this.path.replace(/\.f64$/, ".json"), JSON.stringify(this.meta));
  }
}
function finite(v: ArrayLike<number>): boolean {
  for (let j = 0; j < v.length; j++) if (!Number.isFinite(v[j]!)) return false;
  return true;
}

/** dt, model, start file, initial conditions, landing configuration, candidate properties, run_ic, engines. */
function start(sim: JSBSim, model: string, hz: number, cfg: Cfg, ic: Props, preset: Props, engines: boolean, throttle: number) {
  const ac = G5.aircraft[model];
  sim.reset(); sim.setDebugLevel(0);
  sim.dt = 1 / hz;
  sim.loadModel(model);
  sim.loadIC(ac.ic_file, true);
  setProps(sim, ic);
  setProps(sim, preset);
  applyConfig(sim, cfg);
  sim.runIC();
  if (engines) sim.setProperty("propulsion/set-running", -1);
  for (const p of ac.throttle_props) sim.setProperty(p, throttle);
  sim.setProperty("propulsion/fuel_freeze", 1);
}

/** The ic/h-agl-ft at which the lowest wheel (BOGEY) just touches the ground in the attitude of `ic`: measured in
 *  a separate, fresh simulation at 100 ft (JSBSim's own geometry; nothing is stepped). */
function wheelGroundH(sim: JSBSim, model: string, hz: number, ic: Props): number {
  const ac = G5.aircraft[model];
  sim.reset(); sim.setDebugLevel(0);
  sim.dt = 1 / hz;
  sim.loadModel(model);
  sim.loadIC(ac.ic_file, true);
  setProps(sim, { ...ic, "ic/h-agl-ft": 100 });
  setProps(sim, ac.preset);
  sim.runIC();
  let lowest = Infinity;
  const n = Math.trunc(sim.getProperty("gear/num-units"));
  for (let k = 0; k < n; k++) if (sim.hasProperty(`gear/unit[${k}]/AGL-ft`)) lowest = Math.min(lowest, sim.getProperty(`gear/unit[${k}]/AGL-ft`));
  return 100 - lowest;
}

const I = Object.fromEntries(([["theta", "attitude/theta-rad"], ["phi", "attitude/phi-rad"], ["psi", "attitude/psi-rad"], ["p", "velocities/p-rad_sec"],
  ["q", "velocities/q-rad_sec"], ["r", "velocities/r-rad_sec"], ["t", "simulation/sim-time-sec"]] as const).map(([n, p]) => [n, COMMON.indexOf(p)])) as Record<string, number>;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Trim = any;
/** Three proportional controllers, the same for every configuration and platform. `r` is the latest row.
 *  Signs: a positive elevator command pitches down, a positive aileron command rolls right, a positive rudder
 *  command yaws left. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function flyControls(sim: JSBSim, ac: any, tr: Trim, r: ArrayLike<number>, thetaTarget: number, phiTarget: number, thr: number, brake: number) {
  const pc = ac.pitch, lc = ac.lateral;
  const theta = r[I.theta!]! / D2R, phi = r[I.phi!]! / D2R;
  let psi = r[I.psi!]! / D2R;
  if (psi > 180) psi -= 360;
  sim.setProperty("fcs/elevator-cmd-norm", clamp(tr.elevator + pc.kp * (theta - thetaTarget) + pc.kq * r[I.q!]!, -1, 1));
  sim.setProperty("fcs/aileron-cmd-norm", clamp(-(lc.kphi * (phi - phiTarget) + lc.kp * r[I.p!]!), -1, 1));
  sim.setProperty("fcs/rudder-cmd-norm", clamp(lc.kpsi * psi + lc.kr * r[I.r!]!, -1, 1));
  for (const p of ac.throttle_props) sim.setProperty(p, thr);
  for (const p of ac.brake_props) sim.setProperty(p, brake);
}

/** Let the engines and the control actuators reach the state of this flight condition before the measured part
 *  starts (see sim05.py). It ends exactly on the initial conditions. */
function settle(sim: JSBSim, model: string, hz: number, tr: Trim) {
  const ac = G5.aircraft[model], ap = ac.approach;
  sim.setProperty("fcs/elevator-cmd-norm", tr.elevator);
  sim.setProperty("fcs/aileron-cmd-norm", 0);
  sim.setProperty("fcs/rudder-cmd-norm", 0);
  for (const p of ac.throttle_props) sim.setProperty(p, tr.throttle);
  const segs = Math.round(ap.settle_s / ap.settle_segment_s), steps = Math.round(ap.settle_segment_s * hz);
  for (let s = 0; s < segs; s++) {
    for (let k = 0; k < steps; k++) sim.run();
    sim.runIC();
  }
}

/** Initial conditions of a steady descent at `sink` ft/s, heading north, at the aircraft's approach speed. */
function approachIC(model: string, sink: number, bank = 0, drift = 0): { ic: Props; theta0: number; tr: Trim } {
  const ac = G5.aircraft[model], ap = ac.approach;
  const tr = ac.trim[String(sink)];
  if (!tr) throw new Error(`no trim for ${model} at ${sink} ft/s`);
  const v = ap.vt_fps;
  const gamma = -Math.asin(sink / v);
  const theta0 = tr.alpha_deg + gamma / D2R;
  const ic: Props = {};
  // A crosswind from the west (see sim05.py): set before the velocities, through the writable wind properties.
  if (drift) Object.assign(ic, { "ic/vw-mag-fps": drift, "ic/vw-dir-deg": 90 });
  Object.assign(ic, {
    "ic/psi-true-deg": 0, "ic/phi-deg": bank, "ic/theta-deg": theta0, "ic/vn-fps": v * Math.cos(gamma), "ic/ve-fps": drift, "ic/vd-fps": sink, "ic/h-agl-ft": 0,
  });
  return { ic, theta0, tr };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function caseOf(model: string, name: string): any {
  const c = { ...G5.landing_cases[name] };
  if (c.sink_fps === "limit") c.sink_fps = G5.aircraft[model].limit_sink_fps;
  return c;
}

/** An approach that suits the aircraft, flown to touchdown and roll-out (G2d), a touch-and-go or skipping (G8). */
export function landing(sim: JSBSim, model: string, caseName: string, hz: number, cfg: Cfg, outPath: string) {
  const ac = G5.aircraft[model], ap = ac.approach;
  const c = caseOf(model, caseName);
  const sink: number = c.sink_fps, bank: number = c.bank_deg ?? 0, drift: number = c.drift_fps ?? 0;
  const { ic, theta0, tr } = approachIC(model, sink, bank, drift);
  ic["ic/h-agl-ft"] = wheelGroundH(sim, model, hz, ic) + sink * ap.free_s;
  start(sim, model, hz, cfg, ic, ac.preset, ac.engines, tr.throttle);
  settle(sim, model, hz, tr);
  checkConfig(sim, cfg);
  const pc = ac.pitch;
  const rows = new Rows(sim, outPath, { kind: "landing", model, case: c, hz, theta0_deg: theta0, ic, trim: tr });
  let r = rows.row(); // the state at the release
  const t0 = r[I.t!]!;
  let tTouch: number | null = null;
  const mode: string = c.mode ?? "full_stop";
  const after: number = c.seconds_after_touch ?? G5.G2d.seconds_after_touch;
  let error: string | null = null;
  const wave = c.wave;
  const terrain0 = sim.getProperty("position/terrain-elevation-asl-ft"), iVn = COMMON.indexOf("velocities/v-north-fps");
  let north = 0;
  for (;;) {
    const t = r[I.t!]! - t0;
    let touched = false;
    for (let k = 0; k < rows.wowIdx.length; k++) if (rows.bogey[k] && r[rows.wowIdx[k]!]! > 0.5) touched = true;
    if (touched && tTouch === null) tTouch = t;
    let target: number, phiTarget: number, thr: number, brake: number;
    if (tTouch === null) {
      target = theta0; phiTarget = bank; thr = tr.throttle; brake = 0;
      if (t > G5.G2d.max_seconds_to_touch) { error = "no touchdown"; break; }
    } else if (mode === "full_stop") {
      target = Math.max(pc.ground_theta_deg, theta0 - pc.derotate_deg_s * (t - tTouch));
      phiTarget = 0; thr = 0; brake = t - tTouch >= ac.brake_delay_s ? ac.brake : 0;
      if (t - tTouch >= after) break;
    } else if (mode === "touch_and_go") {
      target = theta0 + (c.go_pitch_up_deg ?? 0); phiTarget = 0; thr = 1; brake = 0;
      if (t - tTouch >= after) break;
    } else {
      target = theta0; phiTarget = 0; thr = tr.throttle; brake = 0;
      if (t - tTouch >= after) break;
    }
    flyControls(sim, ac, tr, r, target, phiTarget, thr, brake);
    if (wave) {
      north += r[iVn]! / hz;
      sim.setProperty("position/terrain-elevation-asl-ft", terrain0 + 0.5 * wave.amplitude_ft * (1 - Math.cos(2 * Math.PI * north / wave.length_ft)));
    }
    try { sim.run(); } catch (e) { error = `exception: ${msg(e)}`; break; }
    r = rows.row();
    if (!finite(r)) { error = "non-finite"; break; }
  }
  rows.close({ error, t_touch: tTouch, t_release: t0 });
}

/** G2d, helicopter: a rotor-running vertical landing of the ah1s (see sim05.py). */
export function heliLanding(sim: JSBSim, caseName: string, hz: number, cfg: Cfg, outPath: string) {
  const H = G5.heli, ac = G5.aircraft.ah1s;
  const c = caseOf("ah1s", caseName);
  const sink: number = c.sink_fps;
  const dt = 1 / hz;
  const h0 = H.h_skids_ft + sink * sink / (2 * H.sink_acc_fps2) + sink * H.steady_s;
  sim.reset(); sim.setDebugLevel(0);
  sim.dt = dt;
  sim.loadModel("ah1s");
  sim.loadIC(ac.ic_file, true);
  setProps(sim, H.preset);
  applyConfig(sim, cfg);
  sim.runIC();
  setProps(sim, H.after_ic);
  const nSpool = Math.round(H.spool_s * hz);
  for (let i = 0; i < nSpool; i++) {
    sim.setProperty("fcs/rpm-governor-active-norm", clamp((i * dt - H.governor_t0_s) / H.governor_ramp_s, 0, 1));
    sim.run();
  }
  sim.setProperty("fcs/rpm-governor-active-norm", 1);
  setProps(sim, H.engage);
  setProps(sim, {
    "ic/h-agl-ft": h0, "ic/u-fps": 0, "ic/v-fps": 0, "ic/w-fps": 0, "ic/p-rad_sec": 0, "ic/q-rad_sec": 0, "ic/r-rad_sec": 0,
    "ic/phi-rad": H.phi_trim_rad, "ic/theta-rad": H.theta_trim_rad, "ic/psi-true-rad": Math.PI, "fcs/collective-cmd-norm": H.collective_base,
  });
  sim.runIC();
  checkConfig(sim, cfg);
  const [gh, gvd, gvn, gve, gpsi] = ["position/h-agl-ft", "velocities/v-down-fps", "velocities/v-north-fps", "velocities/v-east-fps", "attitude/psi-rad"].map((p) => sim.handle(p)) as [number, number, number, number, number];
  let integ = 0, x = 0, y = 0, col = 0, tht = 0, pht = 0;
  let rows: Rows | null = null;
  let tTouch: number | null = null, error: string | null = null;
  const nHover = Math.round(H.hover_s * hz), nMax = Math.round(H.max_s * hz);
  let kDesc: number | null = null, kTouch: number | null = null;
  const extra = { kind: "landing", model: "ah1s", case: c, hz, theta0_deg: H.theta_trim_rad / D2R, hover_h_agl_ft: h0 };
  let i = 0;
  for (;;) {
    if (kTouch === null) {
      if (kDesc === null && i >= nHover) {
        kDesc = i;
        rows = new Rows(sim, outPath, extra);
        rows.row();
      }
      const vd = sim.get(gvd);
      const vdCmd = kDesc === null ? clamp(H.kh * (sim.get(gh) - h0), -H.climb_fps, H.climb_fps) : Math.min(sink, (i - kDesc) * dt * H.sink_acc_fps2);
      const e = vd - vdCmd;
      integ += e * dt;
      col = clamp(H.collective_base + H.kp * e + H.ki * integ, 0, 1);
      const vn = sim.get(gvn), ve = sim.get(gve), psi = sim.get(gpsi);
      const uh = vn * Math.cos(psi) + ve * Math.sin(psi);
      const vh = -vn * Math.sin(psi) + ve * Math.cos(psi);
      x += uh * dt;
      y += vh * dt;
      tht = H.theta_trim_rad + clamp(H.ku * uh + H.kx * x, -H.trim_limit_rad, H.trim_limit_rad);
      pht = H.phi_trim_rad - clamp(H.kv * vh + H.ky * y, -H.trim_limit_rad, H.trim_limit_rad);
      sim.setProperty("fcs/collective-cmd-norm", col);
      sim.setProperty("ap/afcs/manual/theta-trim-rad", tht);
      sim.setProperty("ap/afcs/manual/phi-trim-rad", pht);
    } else {
      const k = clamp(1 - (i - kTouch) * dt / H.collective_down_s, 0, 1);
      sim.setProperty("fcs/collective-cmd-norm", col * k);
      sim.setProperty("fcs/elevator-cmd-norm", H.engage["fcs/elevator-cmd-norm"] * k);
      sim.setProperty("fcs/aileron-cmd-norm", H.engage["fcs/aileron-cmd-norm"] * k);
      sim.setProperty("fcs/rudder-cmd-norm", H.engage["fcs/rudder-cmd-norm"] * k);
      sim.setProperty("ap/afcs/pitch-channel-active-norm", k);
      sim.setProperty("ap/afcs/roll-channel-active-norm", k);
      if ((i - kTouch) * dt >= H.seconds_after_touch) break;
    }
    try { sim.run(); } catch (ex) { error = `exception: ${msg(ex)}`; break; }
    i++;
    if (rows !== null) {
      const r = rows.row();
      if (!finite(r)) { error = "non-finite"; break; }
      if (kTouch === null) {
        let any = false;
        for (const k of rows.wowIdx) if (r[k]! > 0.5) any = true;
        if (any) { kTouch = i; tTouch = (i - kDesc!) * dt; }
      }
    } else if ((H.wow_props as string[]).some((u) => sim.getProperty(u + "/WOW") > 0.5)) {
      error = "touched the ground before the descent";
      rows = new Rows(sim, outPath, extra);
      rows.row();
      break;
    }
    if (i >= nMax) { error = "no touchdown"; break; }
  }
  if (rows === null) { rows = new Rows(sim, outPath, extra); rows.row(); }
  rows.close({ error, t_touch: tTouch });
}

/** G3d: crash cases (the set-up of the frozen ground tests; every step recorded). */
export function crash(sim: JSBSim, model: string, scenario: string, run: number, hz: number, cfg: Cfg, outPath: string) {
  const g3 = G5.G3d, sc = g3.scenarios[scenario];
  sim.reset(); sim.setDebugLevel(0);
  sim.dt = 1 / hz;
  sim.loadModel(model);
  sim.loadIC(g3.aircraft[model], true);
  const ic: Props = { ...sc.ic };
  (g3.perturbed_properties as string[]).forEach((p, j) => { ic[p] = ic[p]! + g3.draws[run][j]; });
  setProps(sim, ic);
  applyConfig(sim, cfg);
  sim.runIC();
  const rows = new Rows(sim, outPath, { kind: "crash", model, scenario, run, hz, ic });
  rows.row();
  let error: string | null = null;
  const steps = Math.round(sc.seconds * hz);
  for (let k = 0; k < steps; k++) {
    try { sim.run(); } catch (e) { error = `exception: ${msg(e)}`; break; }
    if (!finite(rows.row())) { error = "non-finite"; break; }
  }
  rows.close({ error });
}

// ---- G7: forced flight ----
const PROBE_XML = (aero: string) => `<fdm_config name="probe" version="2.0" release="BETA">
 <planet><rotation_rate>0</rotation_rate></planet>
 <metrics><wingarea unit="FT2">1</wingarea><wingspan unit="FT">1</wingspan><chord unit="FT">1</chord></metrics>
 <mass_balance><ixx unit="SLUG*FT2">1</ixx><iyy unit="SLUG*FT2">1</iyy><izz unit="SLUG*FT2">1</izz>
  <emptywt unit="LBS">32.174049</emptywt></mass_balance>
 <ground_reactions/>
 <external_reactions><moment name="roll" frame="BODY"><direction><x>1</x><y>0</y><z>0</z></direction></moment></external_reactions>
 <aerodynamics>${aero}</aerodynamics>
</fdm_config>
`;
const PROBE_CORE = (c: number, k: number) => `<axis name="ROLL"><function name="moment-law"><sum>
   <product><value>${c}</value><property>velocities/p-rad_sec</property></product>
   <product><value>${k}</value><property>attitude/phi-rad</property></product></sum></function></axis>`;
const PROBE_COLS = ["simulation/sim-time-sec", "velocities/p-rad_sec", "velocities/q-rad_sec", "velocities/r-rad_sec",
  "attitude/phi-rad", "attitude/theta-rad", "attitude/psi-rad", "moments/l-total-lbsft"];

/** One synthetic forced-flight run: moment = -c*p - k*phi on a body of unit inertia, computed inside JSBSim
 *  ("core") or written through the bulk input before every step ("external", the way a game supplies forces). */
export function forcedProbe(sim: JSBSim, caseName: string, where: string, hz: number, cfg: Cfg, outPath: string) {
  const cs = G5.G7.probe_cases[caseName];
  const c: number = cs.kind === "damping" ? cs.rate_per_s : 2 * cs.zeta * cs.omega_rad_s;
  const k: number = cs.kind === "damping" ? 0 : cs.omega_rad_s ** 2;
  sim.reset(); sim.setDebugLevel(0);
  sim.dt = 1 / hz;
  sim.writeFile("aircraft/probe/probe.xml", PROBE_XML(where === "core" ? PROBE_CORE(-c, -k) : ""));
  sim.loadModel("probe");
  setProps(sim, { "ic/h-sl-ft": 100000, "ic/p-rad_sec": cs.p0_rad_s, "ic/phi-rad": cs.phi0_rad });
  applyConfig(sim, cfg);
  sim.runIC();
  const hs = PROBE_COLS.map((p) => sim.handle(p));
  const table = new Table(PROBE_COLS.length);
  const r = new Float64Array(PROBE_COLS.length);
  const read = () => { for (let j = 0; j < hs.length; j++) r[j] = sim.get(hs[j]!); };
  if (where === "external") sim.bindInputs(["external_reactions/roll/magnitude-lbsft"]);
  let error: string | null = null, n = 0;
  read(); table.push(r);
  const steps = Math.round(cs.seconds * hz);
  for (let s = 0; s < steps; s++) {
    try {
      if (where === "external") {
        // What a game does: read the state the last step left, compute the moment, write it (bulk input), step.
        sim.inputs[0] = -c * r[1]! - k * r[4]!;
        sim.step(1);
      } else sim.run();
    } catch (e) { error = `exception: ${msg(e)}`; break; }
    read(); table.push(r); n++;
    if (!finite(r) || Math.abs(r[1]!) > 1e6) { error = "non-finite or runaway"; break; }
  }
  table.write(outPath);
  writeFileSync(outPath.replace(/\.f64$/, ".json"), JSON.stringify({ kind: "probe", case: caseName, where, hz, columns: PROBE_COLS, c, k, error, rows: n + 1, dt: 1 / hz }));
}

/** A real aircraft at the fastest point of its envelope, with small control doublets (see sim05.py). */
export function fastFlight(sim: JSBSim, model: string, hz: number, cfg: Cfg, outPath: string) {
  const g7 = G5.G7, ac = G5.aircraft[model], pt = g7.fast_points[model];
  const ic: Props = {
    "ic/h-sl-ft": g7.altitude_ft, "ic/terrain-elevation-ft": 0, "ic/vc-kts": pt.kts, "ic/psi-true-deg": 0, "ic/phi-deg": 0,
    "ic/alpha-deg": pt.alpha_deg, "ic/beta-deg": 0, "ic/gamma-deg": 0, "ic/theta-deg": pt.alpha_deg,
  };
  start(sim, model, hz, cfg, ic, g7.preset[model], ac.engines, pt.throttle);
  settle(sim, model, hz, pt);
  checkConfig(sim, cfg);
  const cols: string[] = g7.flight_columns;
  const hs = cols.map((p) => sim.handle(p)), hc = COMMON.map((p) => sim.handle(p));
  const table = new Table(cols.length);
  const r = new Float64Array(cols.length), rc = new Float64Array(COMMON.length);
  const every = hz / g7.sample_hz, seg = Math.round(g7.segment_s * hz);
  if (!Number.isInteger(every) || Math.abs(seg - g7.segment_s * hz) > 1e-9) throw new Error(`step rate ${hz} does not fit the sampling of G7`);
  const doublets = (g7.doublets as [string, number][]).map(([p, m]) => [sim.handle(p), m] as const);
  let error: string | null = null, n = 0;
  for (let j = 0; j < hs.length; j++) r[j] = sim.get(hs[j]!);
  table.push(r); n++;
  const steps = Math.round(g7.seconds * hz);
  for (let k = 0; k < steps; k++) {
    for (let j = 0; j < hc.length; j++) rc[j] = sim.get(hc[j]!);
    flyControls(sim, ac, pt, rc, pt.alpha_deg, 0, pt.throttle, 0);
    for (const [h, mult] of doublets) sim.set(h, clamp(sim.get(h) + ((Math.floor(k / (seg * mult)) % 3) - 1) * g7.doublet_amplitude, -1, 1));
    try { sim.run(); } catch (e) { error = `exception: ${msg(e)}`; break; }
    if ((k + 1) % every === 0) {
      for (let j = 0; j < hs.length; j++) r[j] = sim.get(hs[j]!);
      table.push(r); n++;
      if (!finite(r)) { error = "non-finite"; break; }
    }
  }
  table.write(outPath);
  writeFileSync(outPath.replace(/\.f64$/, ".json"), JSON.stringify({ kind: "fast_flight", model, hz, columns: cols, error, rows: n }));
}

// ---- G8, synthetic case (reported only): the review's repeated-contact test ----
const RELEASE_XML = (amp: number, w: number) => `<fdm_config name="relprobe" version="2.0" release="BETA">
<planet><rotation_rate>0</rotation_rate></planet>
<metrics><wingarea unit="FT2">1</wingarea><wingspan unit="FT">1</wingspan><chord unit="FT">1</chord></metrics>
<mass_balance><ixx unit="SLUG*FT2">1</ixx><iyy unit="SLUG*FT2">1</iyy>
<izz unit="SLUG*FT2">1</izz><emptywt unit="LBS">32.174049</emptywt></mass_balance>
<ground_reactions><contact type="BOGEY" name="flag-probe"><location unit="IN"><x>0</x><y>0</y><z>-12</z></location>
<static_friction>0</static_friction><dynamic_friction>0</dynamic_friction><rolling_friction>0</rolling_friction>
<spring_coeff unit="LBS/FT">0.000001</spring_coeff><damping_coeff unit="LBS/FT/SEC">0</damping_coeff>
<max_steer unit="DEG">0</max_steer><brake_group>NONE</brake_group></contact></ground_reactions>
<aerodynamics><axis name="ROLL"><function name="sinusoidal-moment"><product><value>${amp}</value>
<cos><product><value>${w}</value><property>simulation/sim-time-sec</property></product></cos>
</product></function></axis></aerodynamics></fdm_config>
`;
export function releaseProbe(sim: JSBSim, hz: number, cfg: Cfg, outPath: string) {
  const syn = G5.G8.synthetic_reported_only;
  sim.reset(); sim.setDebugLevel(0);
  sim.dt = 1 / hz;
  sim.writeFile("aircraft/relprobe/relprobe.xml", RELEASE_XML(syn.moment_amplitude, 2 * Math.PI * syn.moment_hz));
  sim.loadModel("relprobe");
  sim.setProperty("ic/h-sl-ft", 100000);
  applyConfig(sim, cfg);
  sim.runIC();
  const cols = ["simulation/sim-time-sec", "velocities/pi-rad_sec", "attitude/phi-rad", "gear/unit/WOW", "moments/l-gear-lbsft"];
  const hs = cols.map((p) => sim.handle(p));
  const hTerrain = sim.handle("position/terrain-elevation-asl-ft"), hH = sim.handle("position/h-sl-ft");
  const table = new Table(cols.length);
  const r = new Float64Array(cols.length);
  const every = Math.round(syn.contact_every_s * hz), length = Math.round(syn.contact_for_s * hz);
  let error: string | null = null, contactSteps = 0, maxMoment = 0;
  for (let j = 0; j < hs.length; j++) r[j] = sim.get(hs[j]!);
  table.push(r);
  const steps = Math.round(syn.seconds * hz);
  for (let k = 0; k < steps; k++) {
    if (k % every < length) sim.set(hTerrain, sim.get(hH) - Math.cos(sim.get(hs[2]!)) + 0.001);
    else sim.set(hTerrain, sim.get(hH) - 1000);
    try { sim.run(); } catch (e) { error = `exception: ${msg(e)}`; break; }
    for (let j = 0; j < hs.length; j++) r[j] = sim.get(hs[j]!);
    table.push(r);
    if (r[3]! > 0.5) contactSteps++;
    maxMoment = Math.max(maxMoment, Math.abs(r[4]!));
  }
  table.write(outPath);
  writeFileSync(outPath.replace(/\.f64$/, ".json"), JSON.stringify({ kind: "release", hz, columns: cols, error, contact_steps: contactSteps, max_gear_moment: maxMoment }));
}
