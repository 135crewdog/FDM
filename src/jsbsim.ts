// TypeScript wrapper around our own WebAssembly build of JSBSim (wasm/bin/jsbsim.mjs).
// Works in Node and in the browser (no Node imports here; Node helpers live in src/wasm.ts).
//
// Errors: the C++ binding catches every C++ exception and returns a status code; this wrapper
// turns that into a JSBSimError whose message is the C++ exception text. A load that JSBSim
// reports as `false` (no exception) also throws, with JSBSim's recent console output as message.

/** Raw embind class exported by wasm/bindings.cpp. */
interface RawSim {
  init(root: string): number;
  loadModel(model: string, addModelToPath: boolean): number;
  loadScript(script: string, dt: number, initfile: string): number;
  runIC(): number;
  run(): number;
  runSteps(n: number): number;
  getProperty(name: string): number;
  setProperty(name: string, v: number): number;
  hasProperty(name: string): boolean;
  handle(name: string, create: boolean): number;
  get(h: number): number;
  set(h: number, v: number): number;
  bindInputs(handles: number[]): number;
  bindOutputs(handles: number[]): number;
  inputPtr(): number;
  outputPtr(): number;
  applyInputs(): number;
  readOutputs(): void;
  stepBulk(n: number): number;
  getDt(): number;
  setDt(dt: number): void;
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
  /** simulation/integrator/rate/rotational: 0 none, 1 rect Euler (default), 2 trapezoidal, 3 AB2, 4 AB3, 5 AB4 */
  rateRotational?: number;
  rateTranslational?: number;
  positionRotational?: number;
  positionTranslational?: number;
}

export interface CreateOptions {
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
  ) {
    this.root = root;
  }

  static async create(opts: CreateOptions): Promise<JSBSim> {
    const log = new LogBuffer(60, opts.echo);
    const module = await opts.factory({ print: log.push, printErr: log.push, ...opts.moduleOptions });
    const root = opts.root ?? "/jsbsim";
    module.FS.mkdirTree(root);
    const sim = new module.Sim();
    const s = new JSBSim(module, sim, log, root);
    s.check(sim.init(root), "init");
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

  /** Re-create the FGFDMExec instance (fresh state; files in the file system are kept). */
  reset(): void { this.check(this.sim.init(this.root), "init"); this.inView = this.outView = undefined; }

  setDebugLevel(level: number): void { this.sim.setDebugLevel(level); }

  loadModel(model: string, addModelToPath = true): void {
    this.log.clear();
    const r = this.sim.loadModel(model, addModelToPath);
    this.check(r, `loadModel(${model})`);
    if (r === 0) throw new JSBSimError(`loadModel(${model}) returned false. ${this.log.text()}`.trim());
  }

  loadScript(script: string, dt = 0, initfile = ""): void {
    this.log.clear();
    const r = this.sim.loadScript(script, dt, initfile);
    this.check(r, `loadScript(${script})`);
    if (r === 0) throw new JSBSimError(`loadScript(${script}) returned false. ${this.log.text()}`.trim());
  }

  runIC(): void {
    const r = this.sim.runIC();
    this.check(r, "runIC");
    if (r === 0) throw new JSBSimError(`runIC returned false. ${this.log.text()}`.trim());
  }

  /** One step. Returns false when a script has finished (like FGFDMExec::Run). */
  run(): boolean { return this.check(this.sim.run(), "run") === 1; }

  /** Up to n steps; returns steps completed (fewer if a script finished). */
  runSteps(n: number): number { return this.check(this.sim.runSteps(n), "runSteps"); }

  // ---- properties by name (simple, ~1 µs per call) ----
  getProperty(name: string): number {
    const v = this.sim.getProperty(name);
    if (this.sim.lastStatus() < 0) this.check(-1, `getProperty(${name})`);
    return v;
  }
  setProperty(name: string, value: number): void { this.check(this.sim.setProperty(name, value), `setProperty(${name})`); }
  hasProperty(name: string): boolean { return this.sim.hasProperty(name); }

  // ---- cached handles ----
  /** Look a property up once; throws if it does not exist (unless create = true). */
  handle(name: string, create = false): number { return this.check(this.sim.handle(name, create), `handle(${name})`); }
  get(h: number): number { return this.sim.get(h); }
  set(h: number, v: number): void { if (this.sim.set(h, v) < 0) this.check(-1, `set(handle ${h})`); }

  // ---- bulk exchange ----
  private inView?: Float64Array;
  private outView?: Float64Array;
  private nIn = 0;
  private nOut = 0;

  /** Bind input properties (names or handles). Then write `inputs` and call step(). */
  bindInputs(props: (string | number)[]): void {
    const hs = props.map((p) => (typeof p === "number" ? p : this.handle(p)));
    this.nIn = this.check(this.sim.bindInputs(hs), "bindInputs");
    this.inView = undefined;
  }
  /** Bind output properties (names or handles). After step(), read `outputs`. */
  bindOutputs(props: (string | number)[]): void {
    const hs = props.map((p) => (typeof p === "number" ? p : this.handle(p)));
    this.nOut = this.check(this.sim.bindOutputs(hs), "bindOutputs");
    this.outView = undefined;
  }
  /** Float64Array view of the bound inputs (re-created if WASM memory has grown). */
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
   *  Returns the number of steps run; negative (-steps) if a script finished during the call. */
  step(n = 1): number {
    const r = this.sim.stepBulk(n);
    if (r === -1) this.check(-1, "step");
    return r >= 0 ? r : r + 2;
  }
  applyInputs(): void { this.check(this.sim.applyInputs(), "applyInputs"); }
  readOutputs(): void { this.sim.readOutputs(); }

  // ---- misc ----
  get dt(): number { return this.sim.getDt(); }
  set dt(v: number) { this.sim.setDt(v); }
  get simTime(): number { return this.sim.simTime(); }
  /** Recent JSBSim console output (ANSI colours stripped). */
  get recentLog(): string { return this.log.text(); }

  setIntegrators(s: IntegratorSettings): void {
    const map: [keyof IntegratorSettings, string][] = [
      ["rateRotational", "simulation/integrator/rate/rotational"],
      ["rateTranslational", "simulation/integrator/rate/translational"],
      ["positionRotational", "simulation/integrator/position/rotational"],
      ["positionTranslational", "simulation/integrator/position/translational"],
    ];
    for (const [k, prop] of map) if (s[k] !== undefined) this.setProperty(prop, s[k]!);
  }

  delete(): void { this.sim.delete(); }

  private check(r: number, what: string): number {
    if (r === -1) throw new JSBSimError(`${what}: ${this.sim.lastError()}`);
    return r;
  }
}
