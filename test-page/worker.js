var __defProp = Object.defineProperty;
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __publicField = (obj, key, value) => __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);

// ts/codes.ts
var State = { NEW: 0, LOADED: 1, RUNNING: 2, ENDED: 3, DEAD: 4 };
var StepResult = {
  OK: 0,
  SCRIPT_END: 1,
  TERMINATE: 2,
  NONFINITE: 3,
  ERROR: -1,
  NOT_RUNNING: -2,
  BAD_INPUT: -3
};
var SetStatus = {
  OK: 0,
  READ_ONLY: 1,
  NAN: 2,
  NOT_INTEGER: 3,
  REJECTED: 4,
  READBACK_DIFFERS: 5,
  BAD_HANDLE: 6
};
var SET_STATUS_NAME = ["ok", "read-only", "nan", "not-integer", "rejected", "readback-differs", "bad-handle"];
var Counter = {
  DT_RESTORED: 0,
  INTEGRATORS_RESTORED: 1,
  DT_CHANGED: 2,
  INTEGRATORS_CHANGED: 3,
  TIME_STALLED: 4,
  GROUND_CALLS: 5,
  TERRAIN_ELEV_IGNORED: 6,
  STEPS: 7
};
var COUNTER_NAME = [
  "dt-restored",
  "integrators-restored",
  "dt-changed",
  "integrators-changed",
  "time-stalled",
  "ground-calls",
  "terrain-elevation-ignored",
  "steps"
];
var PropFlag = { READ: 1, WRITE: 2, INTEGER: 4 };
var LOG_LEVEL_NAME = ["BULK", "DEBUG", "INFO", "WARN", "ERROR", "FATAL", "STDOUT"];

// ts/core.ts
var FdmError = class extends Error {
  constructor(message, status = -1) {
    super(message);
    __publicField(this, "status");
    this.name = "FdmError";
    this.status = status;
  }
};
var FdmCrash = class extends FdmError {
  constructor(message) {
    super(message);
    this.name = "FdmCrash";
  }
};
var FdmModule = class {
  constructor(raw, onLog) {
    /** The Emscripten module object. */
    __publicField(this, "raw");
    __publicField(this, "onLog");
    /** Set after a trap: nothing in this module may be used again. */
    __publicField(this, "dead", false);
    __publicField(this, "deadReason", "");
    this.raw = raw;
    this.onLog = onLog;
  }
  /** Calls into WebAssembly. A trap marks the module dead and becomes FdmCrash. */
  call(fn) {
    if (this.dead) throw new FdmCrash(`module is dead: ${this.deadReason}`);
    try {
      return fn();
    } catch (e) {
      if (e instanceof FdmError) throw e;
      this.dead = true;
      this.deadReason = e instanceof Error ? `${e.name}: ${e.message}` : String(e);
      throw new FdmCrash(`WebAssembly trap: ${this.deadReason}`);
    }
  }
  /** Runs fn with C strings for the given JavaScript strings; frees them afterwards. */
  withStrings(strings, fn) {
    const m = this.raw;
    const ptrs = [];
    try {
      return this.call(() => {
        for (const s of strings) {
          const n = m.lengthBytesUTF8(s) + 1;
          const p = m._malloc(n);
          if (!p) throw new FdmError("out of memory");
          m.stringToUTF8(s, p, n);
          ptrs.push(p);
        }
        return fn(...ptrs);
      });
    } finally {
      if (!this.dead) for (const p of ptrs) m._free(p);
    }
  }
  str(ptr) {
    return this.raw.UTF8ToString(ptr);
  }
  version() {
    return this.call(() => this.str(this.raw._fdm_version()));
  }
  /** Delivers pending JSBSim log records to onLog. Called after every host call. */
  drainLog() {
    if (this.dead) return;
    const text = this.call(() => this.str(this.raw._fdm_log_take()));
    if (!text || !this.onLog) return;
    for (const rec of text.split("")) {
      if (!rec) continue;
      const f = rec.split("");
      const level = Number(f[0]);
      this.onLog({ level, levelName: LOG_LEVEL_NAME[level] ?? String(level), file: f[1] ?? "", line: Number(f[2]), text: f.slice(3).join("") });
    }
  }
  /** Bytes in use on the C heap. */
  heapInUse() {
    return this.call(() => this.raw._fdm_heap_in_use());
  }
  /** Highest address the C heap has reached (it never shrinks): shows the peak. */
  heapTop() {
    return this.call(() => this.raw._fdm_heap_top());
  }
  stackFree() {
    return this.call(() => this.raw._fdm_stack_free());
  }
  /** Total size of the fixed WebAssembly memory, bytes. */
  memoryBytes() {
    return this.raw.HEAPU8.buffer.byteLength;
  }
  // --- in-memory file system -----------------------------------------------------------------------------
  mkdir(path) {
    this.call(() => this.raw.FS.mkdirTree(path));
  }
  writeFile(path, data) {
    this.call(() => {
      const slash = path.lastIndexOf("/");
      if (slash > 0) this.raw.FS.mkdirTree(path.slice(0, slash));
      this.raw.FS.writeFile(path, data);
    });
  }
  readFile(path) {
    return this.call(() => this.raw.FS.readFile(path));
  }
  exists(path) {
    return this.call(() => this.raw.FS.analyzePath(path).exists);
  }
};
async function loadFdmModule(factory, options = {}) {
  const holder = {};
  const print = (level) => (text) => {
    const onLog = holder.mod ? holder.mod.onLog : options.onLog;
    if (onLog) onLog({ level, levelName: level === 6 ? "STDOUT" : "STDERR", text: String(text), file: "", line: -1 });
  };
  const moduleOptions = { print: print(6), printErr: print(4) };
  if (options.wasmBinary) moduleOptions.wasmBinary = options.wasmBinary;
  if (options.locateFile) moduleOptions.locateFile = options.locateFile;
  const raw = await factory(moduleOptions);
  const mod = new FdmModule(raw, options.onLog);
  holder.mod = mod;
  mod.mkdir("/out");
  return mod;
}
var Fdm = class _Fdm {
  constructor(module, ptr) {
    __publicField(this, "module");
    __publicField(this, "onEvent");
    /** Bulk inputs: write here, then step(). Bound by bindInputs. */
    __publicField(this, "inputs", new Float64Array(0));
    /** Bulk outputs before and after the last step. Bound by bindOutputs. */
    __publicField(this, "prev", new Float64Array(0));
    __publicField(this, "curr", new Float64Array(0));
    __publicField(this, "inputNames", []);
    __publicField(this, "outputNames", []);
    __publicField(this, "ptr");
    __publicField(this, "lastCounters", new Array(COUNTER_NAME.length).fill(0));
    __publicField(this, "handleCache", /* @__PURE__ */ new Map());
    this.module = module;
    this.ptr = ptr;
  }
  static create(module, options = {}) {
    const m = module.raw;
    const dt = options.dt ?? 1 / 120;
    const ptr = module.withStrings([options.root ?? "/data", options.outDir ?? "/out"], (root, out) => m._fdm_new(dt, root, out));
    module.drainLog();
    if (!ptr) throw new FdmError(module.str(m._fdm_global_error()));
    const fdm = new _Fdm(module, ptr);
    fdm.onEvent = options.onEvent;
    try {
      if (options.paths) {
        const p = options.paths;
        fdm.check(module.withStrings([p.aircraft, p.engine, p.systems], (a, e, s) => m._fdm_set_paths(ptr, a, e, s)));
      }
      if (options.integrators) {
        const i = options.integrators;
        fdm.check(module.call(() => m._fdm_set_integrators(ptr, i[0], i[1], i[2], i[3])));
      }
      if (options.ground) fdm.setGround(options.ground);
    } catch (e) {
      fdm.dispose();
      throw e;
    }
    return fdm;
  }
  /** Frees the instance. Safe to call twice. */
  dispose() {
    if (!this.ptr) return;
    const p = this.ptr;
    this.ptr = 0;
    if (!this.module.dead) {
      this.module.call(() => this.module.raw._fdm_delete(p));
      this.module.drainLog();
    }
  }
  get p() {
    if (!this.ptr) throw new FdmError("this Fdm instance was disposed");
    return this.ptr;
  }
  lastError() {
    return this.module.str(this.module.raw._fdm_last_error(this.p));
  }
  /** Turns a failed status into FdmError, after delivering the log and any warnings. */
  check(status) {
    this.afterCall();
    if (status !== 0) throw new FdmError(this.lastError(), status);
  }
  afterCall() {
    this.module.drainLog();
    this.reportWarnings();
  }
  emit(event) {
    if (this.onEvent) this.onEvent(event);
  }
  setGround(g) {
    const m = this.module.raw;
    if (g.heights.length !== g.nlat * g.nlon) throw new FdmError("ground grid: heights.length must be nlat * nlon");
    const bytes = g.heights.length * 8;
    const buf = this.module.call(() => m._malloc(bytes));
    if (!buf) throw new FdmError("out of memory");
    try {
      new Float64Array(m.HEAPF64.buffer, buf, g.heights.length).set(g.heights);
      this.check(this.module.call(() => m._fdm_set_ground_grid(this.p, g.lat0, g.lon0, g.dlat, g.dlon, g.nlat, g.nlon, buf)));
    } finally {
      if (!this.module.dead) m._free(buf);
    }
  }
  // --- load ----------------------------------------------------------------------------------------------
  loadModel(name) {
    this.check(this.module.withStrings([name], (n) => this.module.raw._fdm_load_model(this.p, n)));
  }
  /** path is relative to the root folder. A host dt other than 0 overrides the script's own dt. */
  loadScript(path, initfile = "") {
    this.check(this.module.withStrings([path, initfile], (a, b) => this.module.raw._fdm_load_script(this.p, a, b)));
  }
  /** Initial-condition file, relative to the aircraft's folder. After loadModel, before runIC. */
  loadIC(file) {
    this.check(this.module.withStrings([file], (f) => this.module.raw._fdm_load_ic(this.p, f)));
  }
  runIC() {
    this.check(this.module.call(() => this.module.raw._fdm_run_ic(this.p)));
  }
  // --- properties ----------------------------------------------------------------------------------------
  /** Handle of a property. Throws if the name is unknown or invalid; never creates a property. */
  prop(name) {
    const cached = this.handleCache.get(name);
    if (cached !== void 0) return cached;
    const h = this.module.withStrings([name], (n) => this.module.raw._fdm_prop(this.p, n));
    this.afterCall();
    if (h < 0) throw new FdmError(this.lastError());
    this.handleCache.set(name, h);
    return h;
  }
  has(name) {
    try {
      this.prop(name);
      return true;
    } catch (e) {
      if (e instanceof FdmCrash) throw e;
      return false;
    }
  }
  isWritable(handle2) {
    return (this.module.call(() => this.module.raw._fdm_prop_flags(this.p, handle2)) & PropFlag.WRITE) !== 0;
  }
  isInteger(handle2) {
    return (this.module.call(() => this.module.raw._fdm_prop_flags(this.p, handle2)) & PropFlag.INTEGER) !== 0;
  }
  get(handle2) {
    return this.module.call(() => this.module.raw._fdm_get(this.p, handle2));
  }
  getByName(name) {
    return this.get(this.prop(name));
  }
  /**
   * Writes one property and returns the value read back.
   * Throws FdmError (status = SetStatus) for a read-only property, NaN/infinity, a non-integer written to an
   * integer property, or a setter that refused. The property is unchanged in those cases.
   */
  set(handle2, value) {
    const m = this.module.raw;
    if (typeof value !== "number") throw new FdmError("set: value must be a number", SetStatus.NAN);
    const status = this.module.call(() => m._fdm_set(this.p, handle2, value));
    this.afterCall();
    if (status === SetStatus.OK || status === SetStatus.READBACK_DIFFERS) return this.module.call(() => m._fdm_set_readback(this.p));
    const detail = status === SetStatus.REJECTED ? `: ${this.lastError()}` : "";
    throw new FdmError(`set refused (${SET_STATUS_NAME[status] ?? status})${detail}`, status);
  }
  setByName(name, value) {
    return this.set(this.prop(name), value);
  }
  bind(names, fn) {
    const m = this.module.raw;
    const handles = names.map((n) => this.prop(n));
    const buf = this.module.call(() => m._malloc(Math.max(4, handles.length * 4)));
    if (!buf) throw new FdmError("out of memory");
    try {
      new Int32Array(m.HEAP32.buffer, buf, handles.length).set(handles);
      this.check(this.module.call(() => m[fn](this.p, buf, handles.length)));
    } finally {
      if (!this.module.dead) m._free(buf);
    }
  }
  /** Binds the bulk input array. `inputs[i]` is written to names[i] before every step. */
  bindInputs(names) {
    this.bind(names, "_fdm_bind_inputs");
    const m = this.module.raw;
    this.inputNames = names.slice();
    this.inputs = new Float64Array(m.HEAPF64.buffer, this.module.call(() => m._fdm_in(this.p)), names.length);
    return this.inputs;
  }
  /** Binds the bulk output arrays. After each step, `prev` and `curr` hold names[i] before and after it. */
  bindOutputs(names) {
    this.bind(names, "_fdm_bind_outputs");
    const m = this.module.raw;
    this.outputNames = names.slice();
    this.prev = new Float64Array(m.HEAPF64.buffer, this.module.call(() => m._fdm_prev(this.p)), names.length);
    this.curr = new Float64Array(m.HEAPF64.buffer, this.module.call(() => m._fdm_curr(this.p)), names.length);
  }
  // --- stepping ------------------------------------------------------------------------------------------
  /**
   * Runs n steps and returns the StepResult code (see codes.ts). Does not throw for script end, terminate,
   * a non-finite state or a JSBSim error: those are reported through onEvent and the return value.
   * It throws FdmCrash only when the WebAssembly module itself trapped.
   */
  step(n = 1) {
    const m = this.module.raw;
    let result;
    try {
      result = this.module.call(() => m._fdm_step(this.p, n));
    } catch (e) {
      if (e instanceof FdmCrash) this.emit({ type: "crash", reason: "trap", message: e.message, simTime: NaN, step: this.lastCounters[Counter.STEPS] });
      throw e;
    }
    if (result === StepResult.OK) {
      this.fastWarnings();
      return result;
    }
    this.afterCall();
    const simTime = this.simTime;
    const step = this.counter(Counter.STEPS);
    if (result === StepResult.SCRIPT_END) this.emit({ type: "script-end", simTime, step });
    else if (result === StepResult.TERMINATE) this.emit({ type: "terminate", simTime, step });
    else if (result === StepResult.NONFINITE) this.emit({ type: "crash", reason: "non-finite", message: this.lastError(), simTime, step });
    else this.emit({ type: "error", message: this.lastError(), simTime, step });
    return result;
  }
  /** Steps actually run by the last step() call. */
  get stepsInLastCall() {
    return this.module.call(() => this.module.raw._fdm_steps_in_last_call(this.p));
  }
  // After an ordinary step, only look at the log and counters when a listener exists (keeps the hot path short).
  fastWarnings() {
    if (this.module.onLog) this.module.drainLog();
    if (this.onEvent) this.reportWarnings();
  }
  reportWarnings() {
    if (!this.ptr || this.module.dead) return;
    const m = this.module.raw;
    for (let i = 0; i <= Counter.TIME_STALLED; i++) {
      const c = m._fdm_counter(this.ptr, i);
      if (c !== this.lastCounters[i]) {
        this.lastCounters[i] = c;
        if (this.onEvent) this.onEvent({ type: "warning", what: COUNTER_NAME[i], count: c, simTime: m._fdm_sim_time(this.ptr), step: m._fdm_counter(this.ptr, Counter.STEPS) });
      }
    }
    this.lastCounters[Counter.STEPS] = m._fdm_counter(this.ptr, Counter.STEPS);
  }
  // --- state ---------------------------------------------------------------------------------------------
  get state() {
    return this.module.call(() => this.module.raw._fdm_state(this.p));
  }
  get running() {
    return this.state === State.RUNNING;
  }
  get dt() {
    return this.module.call(() => this.module.raw._fdm_dt(this.p));
  }
  get simTime() {
    return this.module.call(() => this.module.raw._fdm_sim_time(this.p));
  }
  counter(which) {
    return this.module.call(() => this.module.raw._fdm_counter(this.p, which));
  }
  /** Asks the installed ground callback about an ECEF point (feet). */
  groundProbe(x, y, z) {
    const m = this.module.raw;
    const buf = this.module.call(() => m._malloc(7 * 8));
    try {
      this.check(this.module.call(() => m._fdm_ground_probe(this.p, x, y, z, buf)));
      const v = new Float64Array(m.HEAPF64.buffer, buf, 7);
      return { height: v[0], normal: [v[1], v[2], v[3]], contact: [v[4], v[5], v[6]] };
    } finally {
      if (!this.module.dead) m._free(buf);
    }
  }
};

// ts/bench.ts
var BENCH_OUTPUTS = [
  "simulation/sim-time-sec",
  "position/ecef-x-ft",
  "position/ecef-y-ft",
  "position/ecef-z-ft",
  "position/h-sl-ft",
  "position/h-agl-ft",
  "velocities/u-fps",
  "velocities/v-fps",
  "velocities/w-fps",
  "velocities/vtrue-kts",
  "velocities/p-rad_sec",
  "velocities/q-rad_sec",
  "velocities/r-rad_sec",
  "attitude/phi-rad",
  "attitude/theta-rad",
  "attitude/psi-rad"
];
var NUM_FORCES = 20;
var forceName = (i) => `f${String(i).padStart(2, "0")}`;
function forceInputs(kind) {
  const names = [];
  for (let i = 0; i < NUM_FORCES; i++) {
    const base = `external_reactions/${forceName(i)}`;
    if (kind === 140) names.push(`${base}/location-x-in`, `${base}/location-y-in`, `${base}/location-z-in`, `${base}/x`, `${base}/y`, `${base}/z`);
    names.push(`${base}/magnitude`);
  }
  return names;
}
function fillForceInputs(inputs, kind, step) {
  for (let i = 0; i < NUM_FORCES; i++) {
    const period = 64 + 8 * i;
    const phase = (step + 5 * i) % period;
    const tri = phase < period / 2 ? phase : period - phase;
    const magnitude = tri * 4 / period * 8 - 8;
    if (kind === 140) {
      const o = i * 7;
      inputs[o] = 43.2;
      inputs[o + 1] = -190 + 380 * i / (NUM_FORCES - 1);
      inputs[o + 2] = 59.4;
      inputs[o + 3] = 0;
      inputs[o + 4] = 0;
      inputs[o + 5] = -1;
      inputs[o + 6] = magnitude;
    } else {
      inputs[i] = magnitude;
    }
  }
}
function benchSteps(module, o) {
  const warmup = o.warmupSteps ?? 300;
  const batch = o.batchSteps ?? 3e3;
  const repeats = o.repeats ?? 5;
  const now = o.now ?? (() => performance.now());
  const all = [];
  let endAltitudeFt = NaN, endAirspeedKt = NaN;
  for (let r = 0; r < repeats; r++) {
    const fdm = Fdm.create(module, o.forces ? { dt: o.dt, paths: { aircraft: o.fixtureAircraftPath, engine: "engine", systems: "systems" } } : { dt: o.dt });
    try {
      fdm.loadModel(o.forces ? "c172x_ext20" : "c172x");
      fdm.loadIC("reset01");
      fdm.bindOutputs(BENCH_OUTPUTS);
      const inputs = fdm.bindInputs(o.forces ? forceInputs(o.forces) : []);
      fdm.runIC();
      let step = 0;
      const run = (n) => {
        for (let k = 0; k < n; k++, step++) {
          if (o.forces) fillForceInputs(inputs, o.forces, step);
          if (fdm.step(1) !== StepResult.OK) throw new Error(`benchmark step failed at step ${step}`);
        }
      };
      run(warmup);
      const t0 = now();
      run(batch);
      all.push((now() - t0) * 1e3 / batch);
      endAltitudeFt = fdm.curr[4];
      endAirspeedKt = fdm.curr[9];
    } finally {
      fdm.dispose();
    }
  }
  const sorted = all.slice().sort((a, b) => a - b);
  return { dt: o.dt, forces: o.forces, usPerStep: sorted[Math.floor(sorted.length / 2)], all, batchSteps: batch, endAltitudeFt, endAirspeedKt };
}
function runCycles(module, count, model, ic, steps) {
  const heap = [];
  for (let i = 0; i < count; i++) {
    const fdm = Fdm.create(module);
    try {
      fdm.loadModel(model);
      fdm.loadIC(ic);
      fdm.bindOutputs(BENCH_OUTPUTS);
      fdm.runIC();
      if (fdm.step(steps) !== StepResult.OK) throw new Error(`cycle ${i}: step failed`);
    } finally {
      fdm.dispose();
    }
    heap.push(module.heapInUse());
  }
  return { heap, heapTop: module.heapTop(), memoryBytes: module.memoryBytes() };
}

// ts/files.ts
function writeFiles(module, mountPoint, files) {
  for (const [path, bytes] of files) module.writeFile(`${mountPoint}/${path}`, bytes);
}
function readPack(pack) {
  const headLength = new DataView(pack.buffer, pack.byteOffset, pack.byteLength).getUint32(0, true);
  const index = JSON.parse(new TextDecoder().decode(pack.subarray(4, 4 + headLength)));
  const base = 4 + headLength;
  const files = /* @__PURE__ */ new Map();
  for (const [path, offset, length] of index) files.set(path, pack.subarray(base + offset, base + offset + length));
  return files;
}

// ts/loop.ts
var FixedStepLoop = class {
  constructor(sim, options = {}) {
    __publicField(this, "sim");
    __publicField(this, "maxFrameSeconds");
    __publicField(this, "maxStepsPerAdvance");
    /** Real time not yet turned into steps; always less than dt after advance(). */
    __publicField(this, "accumulator", 0);
    __publicField(this, "paused", false);
    /** Steps run since the loop was created. */
    __publicField(this, "totalSteps", 0);
    /** Real time thrown away by the frame cut and the step cap: the sim ran slower than real time by this much. */
    __publicField(this, "droppedSeconds", 0);
    /** Result of the last step call; not OK means the sim ended or failed and the loop has stopped. */
    __publicField(this, "lastResult", StepResult.OK);
    __publicField(this, "lastTime", null);
    this.sim = sim;
    this.maxFrameSeconds = options.maxFrameSeconds ?? 0.25;
    this.maxStepsPerAdvance = options.maxStepsPerAdvance ?? 8;
  }
  /**
   * Call once per frame with the current time in seconds (any monotonic clock).
   * Returns the number of steps run.
   */
  advance(nowSeconds) {
    if (this.paused || this.lastResult !== StepResult.OK) return 0;
    if (this.lastTime === null) {
      this.lastTime = nowSeconds;
      return 0;
    }
    let frame = nowSeconds - this.lastTime;
    this.lastTime = nowSeconds;
    if (!(frame > 0)) return 0;
    if (frame > this.maxFrameSeconds) {
      this.droppedSeconds += frame - this.maxFrameSeconds;
      frame = this.maxFrameSeconds;
    }
    const dt = this.sim.dt;
    this.accumulator += frame;
    const due = Math.floor(this.accumulator / dt + 1e-9);
    const steps = Math.min(due, this.maxStepsPerAdvance);
    if (due > steps) this.droppedSeconds += (due - steps) * dt;
    this.accumulator = Math.max(0, this.accumulator - due * dt);
    if (steps > 0) {
      this.lastResult = this.sim.step(steps);
      this.totalSteps += steps;
    }
    return steps;
  }
  /** The page was hidden: stop stepping. */
  pause() {
    this.paused = true;
  }
  /** The page is visible again: carry on from now. The hidden time is not caught up. */
  resume() {
    this.paused = false;
    this.lastTime = null;
  }
  /** How far the present is between prev (0) and curr (1): for drawing between two physics states. */
  get alpha() {
    const a = this.accumulator / this.sim.dt;
    return a < 0 ? 0 : a >= 1 ? 1 - Number.EPSILON : a;
  }
  get prev() {
    return this.sim.prev;
  }
  get curr() {
    return this.sim.curr;
  }
};

// ts/worker-handler.ts
function createHandler(post) {
  let module;
  let fdm;
  let loop;
  let inputsView;
  const need = () => {
    if (!module) throw new Error("not initialised: send init first");
    return module;
  };
  const onEvent = (event) => post({ type: "event", event });
  async function run(req) {
    switch (req.type) {
      case "init": {
        const factory = (await import(
          /* @vite-ignore */
          req.moduleUrl
        )).default;
        module = await loadFdmModule(factory, {
          wasmBinary: req.wasmBinary,
          onLog: req.forwardLogs ? (record) => post({ type: "log", record }) : void 0
        });
        for (const [mountPoint, pack] of req.packs ?? []) writeFiles(module, mountPoint, readPack(pack));
        return { version: module.version(), memoryBytes: module.memoryBytes() };
      }
      case "files": {
        writeFiles(need(), req.mountPoint, readPack(req.pack));
        return {};
      }
      case "create": {
        const m = need();
        if (fdm) fdm.dispose();
        fdm = Fdm.create(m, { dt: req.dt, root: req.root, paths: req.paths, ground: req.ground, onEvent });
        if (req.script) fdm.loadScript(req.script, req.initfile ?? "");
        else fdm.loadModel(req.model);
        if (req.ic) fdm.loadIC(req.ic);
        fdm.bindOutputs(req.outputs);
        inputsView = fdm.bindInputs(req.inputs ?? []);
        fdm.runIC();
        loop = new FixedStepLoop(fdm, req.loop);
        return { dt: fdm.dt, outputs: fdm.outputNames, simTime: fdm.simTime, curr: Float64Array.from(fdm.curr) };
      }
      case "tick": {
        if (!fdm || !loop) throw new Error("no instance: send create first");
        if (req.inputs && inputsView) inputsView.set(req.inputs);
        const steps = loop.advance(req.now);
        const prev = Float64Array.from(loop.prev);
        const curr = Float64Array.from(loop.curr);
        return [
          {
            steps,
            alpha: loop.alpha,
            simTime: fdm.simTime,
            result: loop.lastResult,
            ended: loop.lastResult !== StepResult.OK,
            totalSteps: loop.totalSteps,
            droppedSeconds: loop.droppedSeconds,
            prev,
            curr
          },
          [prev.buffer, curr.buffer]
        ];
      }
      case "pause":
        if (loop) loop.pause();
        return {};
      case "resume":
        if (loop) loop.resume();
        return {};
      case "dispose":
        if (fdm) fdm.dispose();
        fdm = void 0;
        loop = void 0;
        return {};
      case "bench":
        return { result: benchSteps(need(), req.options) };
      case "cycles":
        return { ...runCycles(need(), req.count, req.model, req.ic, req.steps) };
      case "tryload": {
        const f = Fdm.create(need(), { paths: req.paths });
        try {
          f.loadModel(req.model);
          return { loaded: true };
        } catch (e) {
          if (e instanceof FdmCrash) throw e;
          return { loaded: false, errorName: e.name, isError: e instanceof Error, message: e.message };
        } finally {
          f.dispose();
        }
      }
    }
  }
  return async (req) => {
    try {
      const out = await run(req);
      if (Array.isArray(out)) post({ id: req.id, ok: true, ...out[0] }, out[1]);
      else post({ id: req.id, ok: true, ...out });
    } catch (e) {
      const crash = e instanceof FdmCrash;
      if (crash) post({ type: "event", event: { type: "crash", reason: "trap", message: e.message, simTime: NaN, step: -1 } });
      post({ id: req.id, ok: false, error: e instanceof Error ? e.message : String(e), crash });
    }
  };
}

// ts/worker.ts
var scope = self;
var handle = createHandler((message, transfer) => scope.postMessage(message, transfer ?? []));
scope.onmessage = (e) => {
  void handle(e.data);
};
