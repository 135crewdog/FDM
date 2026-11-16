// TypeScript wrapper around our own WebAssembly build of JSBSim (wasm/bin/jsbsim.mjs).
// Works in Node and in the browser (no Node imports here; Node helpers live in src/wasm.ts).
//
// Errors: the C++ binding catches every C++ exception and returns a status code; this wrapper
// turns that into a JSBSimError whose message is the C++ exception text. A load that JSBSim
// reports as `false` (no exception) also throws, with JSBSim's recent console output as message.
// Nothing fails silently: writes to read-only properties, invalid handles, unknown integrator ids,
// bad dt values and bad step counts all throw a JSBSimError.
//
// Lifetime rules (tested by tests/binding/regress.ts):
// - A handle (from handle()) and the bulk bindings (bindInputs/bindOutputs) belong to the FGFDMExec
//   instance that was current when they were made. reset() creates a new instance: every earlier
//   handle is then invalid (using one throws; it can never address a new property), and `inputs` and
//   `outputs` are empty until bound again.
// - `inputs` and `outputs` are views into WebAssembly memory. Read the property again (sim.inputs)
//   after reset(), after binding, and after any call that can allocate (loading, handle()); do not
//   keep the Float64Array across such calls.
// - Set `dt` before loading a model: flight-control filters cache dt when they are loaded. Changing
//   dt after loading throws; setDtAfterLoad() is the explicit override.
// - Socket input (<input port=...> in aircraft files) is disabled in this runtime.
// - Defaults (session 05): unless created with `profile: "jsbsim"`, a simulation runs the configuration that
//   passed every gate (FDM_DEFAULT below): 1200 steps per second, implicit-midpoint body rates, Buss 2 attitude,
//   the strut limits of patch 0004. The step rate is set at create() and reset(); the integrators and the strut
//   limits are set after every successful loadModel() or loadScript() (JSBSim returns them to its own defaults
//   whenever a model is initialised). A script loaded without an explicit dt keeps its own dt: the configuration
//   is qualified at 1200 Hz only.
// - A step that throws halts the simulation (see setContainment and `halted`): every later run/runSteps/step
//   throws until reset(). Errors of other calls (properties, handles, arguments) halt nothing.

/** Raw embind class exported by wasm/bindings.cpp. */
interface RawSim {
  init(root: string): number;
  loadModel(model: string, addModelToPath: boolean): number;
  loadScript(script: string, dt: number, initfile: string): number;
  loadIC(name: string, useAircraftPath: boolean): number;
  runIC(): number;
  run(): number;
  runSteps(n: number): number;
  getProperty(name: string): number;
  setProperty(name: string, v: number): number;
  hasProperty(name: string): number;
  handle(name: string, create: boolean): number;
  get(h: number): number;
  set(h: number, v: number): number;
  bindInputs(handles: number[]): number;
  bindOutputs(handles: number[]): number;
  inputPtr(): number;
  outputPtr(): number;
  inputCount(): number;
  outputCount(): number;
  applyInputs(): number;
  readOutputs(): number;
  stepBulk(n: number): number;
  setContainment(on: boolean, maxRateRadS: number, minCgAglFt: number, maxTiltOnGroundDeg: number, maxGroundForceWeights: number): number;
  haltReason(): number;
  haltDetail(): string;
  haltTime(): number;
  getDt(): number;
  setDt(dt: number): number;
  simTime(): number;
  setDebugLevel(lvl: number): void;
  lastStatus(): number;
  lastError(): string;
  delete(): void;
}

interface EmFS {
  mkdirTree(path: string): void;
  writeFile(path: string, data: string | Uint8Array): void;
  readFile(path: string, opts?: { encoding: "utf8" }): string | Uint8Array;
  analyzePath(path: string): { exists: boolean };
}

export interface JSBSimModule {
  Sim: { new (): RawSim; version(): string };
  FS: EmFS;
  HEAPF64: Float64Array;
}

export type ModuleFactory = (opts: Record<string, unknown>) => Promise<JSBSimModule>;

export class JSBSimError extends Error {
  override name = "JSBSimError";
}

/** Recent console lines from JSBSim (used to explain loads that return false). */
class LogBuffer {
  lines: string[] = [];
  constructor(private max = 60, public echo?: (line: string) => void) {}
  push = (line: string) => {
    // eslint-disable-next-line no-control-regex
    line = line.replace(/\x1b\[[0-9;]*m/g, "");
    this.lines.push(line);
    if (this.lines.length > this.max) this.lines.shift();
    this.echo?.(line);
  };
  mark(): number { return this.lines.length; }
  clear(): void { this.lines.length = 0; }
  text(): string { return this.lines.filter((l) => l.trim()).join("\n"); }
}

export interface IntegratorSettings {
  /** simulation/integrator/rate/rotational (body rates): 0 none, 1 rect Euler (default), 2 trapezoidal, 3 AB2, 4 AB3, 5 AB4, 9 AB5,
   *  10 implicit midpoint (patch 0002) */
  rateRotational?: number;
  /** simulation/integrator/rate/rotational-on-contact (patch 0003): the body-rate scheme while any contact point touches the
   *  ground; -1 (default) = no switching, otherwise the same ids as rateRotational (1 = Euler) */
  rateRotationalOnContact?: number;
  /** simulation/integrator/rate/translational: same ids; JSBSim's default is 3 (AB2) */
  rateTranslational?: number;
  /** simulation/integrator/position/rotational (attitude): same ids plus 6 Buss 1, 7 Buss 2, 8 local linearization; default 1 */
  positionRotational?: number;
  /** simulation/integrator/position/translational: same ids as the rates; default 4 (AB3) */
  positionTranslational?: number;
}

const INTEGRATOR_PROPS: [keyof IntegratorSettings, string][] = [
  ["rateRotational", "simulation/integrator/rate/rotational"],
  ["rateRotationalOnContact", "simulation/integrator/rate/rotational-on-contact"],
  ["rateTranslational", "simulation/integrator/rate/translational"],
  ["positionRotational", "simulation/integrator/position/rotational"],
  ["positionTranslational", "simulation/integrator/position/translational"],
];
function validIntegrator(slot: keyof IntegratorSettings, id: number): boolean {
  if (!Number.isInteger(id)) return false;
  if (slot === "rateRotationalOnContact" && id === -1) return true;
  // 10 (implicit midpoint) exists only for the body rates and only in a build with patch 0002; the C++ side has the last word.
  if ((slot === "rateRotational" || slot === "rateRotationalOnContact") && id === 10) return true;
  if (id < 0 || id > 9) return false;
  return slot === "positionRotational" || !(id >= 6 && id <= 8);
}

/** Limits of the crash containment (setContainment). Omitted = the default; null = that check is off. */
export interface ContainmentLimits {
  /** Largest body rate, rad/s. Default 30 (1,700 deg/s: no aircraft tumbles that fast). */
  maxBodyRateRadS?: number | null;
  /** Lowest height of the centre of gravity above the ground, ft. Default 0 (the centre of gravity is under the surface). */
  minCgHeightAglFt?: number | null;
  /** Largest tilt from upright while any contact point touches the ground, deg. Default 75. */
  maxTiltOnGroundDeg?: number | null;
  /** Largest total ground force, in units of the aircraft's weight. Default 50. */
  maxGroundForceWeights?: number | null;
}
export const CONTAINMENT_DEFAULTS = { maxBodyRateRadS: 30, minCgHeightAglFt: 0, maxTiltOnGroundDeg: 75, maxGroundForceWeights: 50 } as const;
export type HaltReason = "non-finite" | "runaway-rate" | "below-surface" | "tipped-over" | "ground-force" | "exception";
const HALT_REASONS: HaltReason[] = ["non-finite", "runaway-rate", "below-surface", "tipped-over", "ground-force", "exception"];
/** Why the simulation was halted, and the simulation time of the step that was refused. */
export interface Halt { reason: HaltReason; detail: string; simTime: number }

/** The configuration that passed every gate of session 05 (REPORT-05.md): `c2-mid-g` at 1200 Hz. */
export const FDM_DEFAULT = {
  stepRateHz: 1200,
  integrators: { rateRotational: 10, positionRotational: 7 } as IntegratorSettings,
  /** patch 0004: limits on the wheel strut model */
  properties: { "gear/strut-limits/enabled": 1 } as Record<string, number>,
} as const;
/** "fdm" (default): FDM_DEFAULT is applied. "jsbsim": JSBSim's own defaults, untouched (120 Hz, Euler body rates,
 *  Euler attitude, no strut limits); what every earlier test and the native answer key use. */
export type Profile = "fdm" | "jsbsim";

export interface CreateOptions {
  /** Which defaults a simulation starts with (see Profile). Default "fdm". */
  profile?: Profile;
  /** Module factory (default import of wasm/bin/jsbsim.mjs or jsbsim-weh.mjs). */
  factory: ModuleFactory;
  /** Extra Emscripten module options (e.g. wasmBinary, locateFile). */
  moduleOptions?: Record<string, unknown>;
  /** Root directory of the JSBSim data inside the in-memory file system. */
  root?: string;
  /** Echo JSBSim console output (default: keep it quiet, only buffered). */
  echo?: (line: string) => void;
}

export class JSBSim {
  readonly root: string;
  private constructor(
    readonly module: JSBSimModule,
    private readonly sim: RawSim,
    private readonly log: LogBuffer,
    root: string,
    /** The defaults this simulation was created with (CreateOptions.profile). */
    readonly profile: Profile,
  ) {
    this.root = root;
  }

  /** The profile's step rate, set before anything is loaded (create and reset). */
  private applyProfileDt(): void {
    if (this.profile === "fdm") this.check(this.sim.setDt(1 / FDM_DEFAULT.stepRateHz), "dt");
  }
  /** The profile's integrators and switches, set after a model has been loaded. */
  private applyProfile(): void {
    if (this.profile !== "fdm") return;
    for (const prop of ["simulation/integrator/midpoint/steps", ...Object.keys(FDM_DEFAULT.properties)])
      if (!this.hasProperty(prop)) throw new JSBSimError(`the default configuration needs a build with patches 0002 and 0004 (${prop} is missing); create the simulation with profile: "jsbsim" to run JSBSim's own defaults`);
    this.setIntegrators(FDM_DEFAULT.integrators);
    for (const [prop, v] of Object.entries(FDM_DEFAULT.properties)) this.setProperty(prop, v);
  }

  static async create(opts: CreateOptions): Promise<JSBSim> {
    const log = new LogBuffer(60, opts.echo);
    const module = await opts.factory({ print: log.push, printErr: log.push, ...opts.moduleOptions });
    const root = opts.root ?? "/jsbsim";
    module.FS.mkdirTree(root);
    const sim = new module.Sim();
    const profile = opts.profile ?? "fdm";
    if (profile !== "fdm" && profile !== "jsbsim") throw new JSBSimError(`unknown profile ${String(profile)} (use "fdm" or "jsbsim")`);
    const s = new JSBSim(module, sim, log, root, profile);
    try {
      s.check(sim.init(root), "init");
      s.applyProfileDt();
    } catch (e) {
      sim.delete(); // embind objects are not garbage collected
      throw e;
    }
    return s;
  }

  /** JSBSim version string, e.g. "1.3.3 Nov 15 2026 14:42:00". */
  get version(): string { return this.module.Sim.version(); }

  /** Write a file into the in-memory file system; `path` is relative to the root unless absolute. */
  writeFile(path: string, data: string | Uint8Array): void {
    const full = path.startsWith("/") ? path : `${this.root}/${path}`;
    this.module.FS.mkdirTree(full.slice(0, full.lastIndexOf("/")) || "/");
    this.module.FS.writeFile(full, data);
  }

  /** Re-create the FGFDMExec instance (fresh state; files in the file system are kept).
   *  All earlier handles become invalid and the bulk inputs/outputs become empty (see the lifetime rules above). */
  reset(): void {
    this.inView = this.outView = undefined;
    this.nIn = this.nOut = 0;
    this.loaded = false;
    this.check(this.sim.init(this.root), "init");
    this.applyProfileDt();
  }
  private loaded = false;

  setDebugLevel(level: number): void { this.sim.setDebugLevel(level); }

  loadModel(model: string, addModelToPath = true): void {
    this.log.clear();
    this.loaded = true; // even a failed load may have constructed components with the current dt
    const r = this.sim.loadModel(model, addModelToPath);
    this.check(r, `loadModel(${model})`);
    if (r === 0) throw new JSBSimError(`loadModel(${model}) returned false. ${this.log.text()}`.trim());
    this.applyProfile();
  }

  loadScript(script: string, dt = 0, initfile = ""): void {
    this.log.clear();
    if (!(dt >= 0) || !Number.isFinite(dt)) throw new JSBSimError(`loadScript(${script}): invalid dt ${dt} (must be finite and positive, or 0 for the script's own dt)`);
    this.loaded = true;
    const r = this.sim.loadScript(script, dt, initfile);
    this.check(r, `loadScript(${script})`);
    if (r === 0) throw new JSBSimError(`loadScript(${script}) returned false. ${this.log.text()}`.trim());
    this.applyProfile();
  }

  /** Load an initial-conditions file after loadModel, e.g. loadIC("reset00") for aircraft/<model>/reset00.xml
   *  (like the Python module's load_ic). Then set any ic/... properties and call runIC(). */
  loadIC(name: string, useAircraftPath = true): void {
    this.log.clear();
    const r = this.sim.loadIC(name, useAircraftPath);
    this.check(r, `loadIC(${name})`);
    if (r === 0) throw new JSBSimError(`loadIC(${name}) returned false. ${this.log.text()}`.trim());
  }

  runIC(): void {
    const r = this.sim.runIC();
    this.check(r, "runIC");
    if (r === 0) throw new JSBSimError(`runIC returned false. ${this.log.text()}`.trim());
  }

  /** One step. Returns false when a script has finished (like FGFDMExec::Run) or when the step halted the
   *  simulation (crash containment: then `halted` says why). */
  run(): boolean { return this.check(this.sim.run(), "run") === 1; }

  /** Up to n steps; returns the steps completed and accepted (fewer if a script finished or the simulation was halted). */
  runSteps(n: number): number { return this.check(this.sim.runSteps(n), "runSteps"); }

  // ---- crash containment ----
  /** Inspect the state after EVERY physics step (inside run, runSteps and step(n), not once per call): non-finite
   *  values, runaway body rates, centre of gravity below the surface, tipped over while touching the ground,
   *  ground force beyond the limit. On a hit the simulation is halted: the offending step is not published (the
   *  bulk `outputs` keep the last accepted state, so the game can keep drawing it), no further step runs, and
   *  `halted` says why. Only reset() clears a halt. Off until this is called; null switches it off again.
   *
   *  Independently of this setting, a step that THROWS also halts the simulation: JSBSim has already advanced time
   *  and may have updated the attitude when it throws, so catching the error is not a rollback. */
  setContainment(limits: ContainmentLimits | null): void {
    const v = (k: keyof ContainmentLimits): number => {
      const x = limits![k];
      if (x === null) return NaN; // a comparison with NaN is never true: the check is off
      if (x === undefined) return CONTAINMENT_DEFAULTS[k];
      if (typeof x !== "number" || Number.isNaN(x)) throw new JSBSimError(`setContainment: ${k} must be a number or null`);
      return x;
    };
    if (limits === null) this.check(this.sim.setContainment(false, NaN, NaN, NaN, NaN), "setContainment");
    else this.check(this.sim.setContainment(true, v("maxBodyRateRadS"), v("minCgHeightAglFt"), v("maxTiltOnGroundDeg"), v("maxGroundForceWeights")), "setContainment");
  }
  /** null while the simulation may be stepped; otherwise why it was halted. */
  get halted(): Halt | null {
    const r = this.sim.haltReason();
    return r === 0 ? null : { reason: HALT_REASONS[r - 1] ?? "exception", detail: this.sim.haltDetail(), simTime: this.sim.haltTime() };
  }

  // ---- properties by name (simple, ~1 µs per call) ----
  getProperty(name: string): number {
    const v = this.sim.getProperty(name);
    if (this.sim.lastStatus() < 0) this.check(-1, `getProperty(${name})`);
    return v;
  }
  setProperty(name: string, value: number): void { this.check(this.sim.setProperty(name, value), `setProperty(${name})`); }
  hasProperty(name: string): boolean { return this.check(this.sim.hasProperty(name), `hasProperty(${name})`) === 1; }

  // ---- cached handles ----
  /** Look a property up once; throws if it does not exist (unless create = true). */
  handle(name: string, create = false): number { return this.check(this.sim.handle(name, create), `handle(${name})`); }
  /** Read by handle. Throws for an invalid handle (NaN, fraction, out of range, or from before reset()). */
  get(h: number): number {
    const v = this.sim.get(h);
    if (v !== v && this.sim.lastStatus() < 0) this.check(-1, `get(handle ${h})`); // NaN: error, or a genuine NaN value
    return v;
  }
  /** Write by handle. Throws for an invalid handle or a read-only property. */
  set(h: number, v: number): void { if (this.sim.set(h, v) < 0) this.check(-1, `set(handle ${h})`); }

  // ---- bulk exchange ----
  private inView?: Float64Array;
  private outView?: Float64Array;
  private nIn = 0;
  private nOut = 0;

  /** Bind input properties (names or handles). Then write `inputs` and call step(). */
  bindInputs(props: (string | number)[]): void {
    const hs = props.map((p) => (typeof p === "number" ? p : this.handle(p)));
    this.nIn = this.check(this.sim.bindInputs(hs), "bindInputs"); // a failed bind keeps the previous binding
    this.inView = undefined;
  }
  /** Bind output properties (names or handles). After step(), read `outputs`. */
  bindOutputs(props: (string | number)[]): void {
    const hs = props.map((p) => (typeof p === "number" ? p : this.handle(p)));
    this.nOut = this.check(this.sim.bindOutputs(hs), "bindOutputs");
    this.outView = undefined;
  }
  /** Float64Array view of the bound inputs (re-created if WASM memory has grown). Do not keep it across
   *  reset(), a new binding, or calls that can allocate: read `sim.inputs` again. */
  get inputs(): Float64Array {
    if (!this.inView || this.inView.buffer !== this.module.HEAPF64.buffer)
      this.inView = new Float64Array(this.module.HEAPF64.buffer, this.sim.inputPtr(), this.nIn);
    return this.inView;
  }
  get outputs(): Float64Array {
    if (!this.outView || this.outView.buffer !== this.module.HEAPF64.buffer)
      this.outView = new Float64Array(this.module.HEAPF64.buffer, this.sim.outputPtr(), this.nOut);
    return this.outView;
  }
  /** Write `inputs` into JSBSim, run up to n steps, read `outputs`.
   *  Returns the number of steps run; negative (-steps) if a script finished during the call. With crash
   *  containment on, fewer than n steps and `halted` non-null mean that the next step was refused; `outputs`
   *  then hold the last accepted state. */
  step(n = 1): number {
    const r = this.sim.stepBulk(n);
    if (r === -1) this.check(-1, "step");
    return r >= 0 ? r : r + 2;
  }
  applyInputs(): void { this.check(this.sim.applyInputs(), "applyInputs"); }
  readOutputs(): void { this.check(this.sim.readOutputs(), "readOutputs"); }

  // ---- misc ----
  get dt(): number { return this.sim.getDt(); }
  /** Time step in seconds. Must be finite and positive, and must be set BEFORE loading a model. */
  set dt(v: number) {
    if (this.loaded) throw new JSBSimError(`dt: set dt before loading a model (flight-control filters cache dt at load); call reset() first, or setDtAfterLoad()`);
    this.check(this.sim.setDt(v), "dt");
  }
  /** Change dt although a model is loaded. Its flight-control filters keep the coefficients of the old dt. */
  setDtAfterLoad(v: number): void { this.check(this.sim.setDt(v), "dt"); }
  get simTime(): number { return this.sim.simTime(); }
  /** Recent JSBSim console output (ANSI colours stripped). */
  get recentLog(): string { return this.log.text(); }

  /** Select integrators. Unknown ids throw (JSBSim itself would silently freeze the state).
   *  All or nothing: each setting is read from `s` exactly once, everything is validated before anything is written,
   *  and if a write still fails (the C++ side has the last word) the writes already made are undone. */
  setIntegrators(s: IntegratorSettings): void {
    const want: [string, number][] = [];
    for (const [k, prop] of INTEGRATOR_PROPS) {
      const v = s[k]; // the only read of this setting
      if (v === undefined) continue;
      if (!validIntegrator(k, v)) throw new JSBSimError(`setIntegrators: invalid integrator id ${v} for ${prop}`);
      want.push([prop, v]);
    }
    for (const [prop] of want)
      if (!this.hasProperty(prop)) throw new JSBSimError(`setIntegrators: ${prop} does not exist in this build`);
    const before = want.map(([prop]) => this.getProperty(prop));
    let done = 0;
    try {
      for (const [prop, v] of want) { this.setProperty(prop, v); done++; }
    } catch (e) {
      let undone = true;
      for (let i = done - 1; i >= 0; i--) {
        try { this.setProperty(want[i]![0], before[i]!); } catch { undone = false; }
      }
      if (!undone && e instanceof Error) e.message += " (and an earlier setting could not be restored)";
      throw e;
    }
  }

  delete(): void { this.sim.delete(); }

  private check(r: number, what: string): number {
    if (r === -1) throw new JSBSimError(`${what}: ${this.sim.lastError()}`);
    return r;
  }
}
