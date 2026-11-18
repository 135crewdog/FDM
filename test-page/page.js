var __defProp = Object.defineProperty;
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __publicField = (obj, key, value) => __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);

// <define:__BUILD_INFO__>
var define_BUILD_INFO_default = { jsbsim: "JSBSim v1.3.3", commit: "66f7fafc07fe13e7ede9db20873030fed2881713", emscripten: "Emscripten 6.0.13", memoryBytes: 16777216, files: { "fdm-weh.wasm": { bytes: 1734938, sha256: "ab2357c849ba72d8e9e26a42b071ff9009e12a1756307a3aa53acd32e26353eb" }, "fdm-weh.mjs": { bytes: 82263, sha256: "ef1fc74eb7bdac8d086567234dbc12bb01539a7d7c0e533cec90e6d1a6d99acc" }, "fdm-jseh.wasm": { bytes: 2236922, sha256: "5631da24f912a5104e394f2356a1dba4fa6854aa2011c881fa017957e4c4185d" }, "fdm-jseh.mjs": { bytes: 94843, sha256: "130ccb9f9e6c04afa8fb2eede03de67e6185574c9b266137555155ed7f40e874" } } };

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
  constructor(message, status2 = -1) {
    super(message);
    __publicField(this, "status");
    this.name = "FdmError";
    this.status = status2;
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
    const ptr = module.withStrings([options.root ?? "/data", options.outDir ?? "/out"], (root, out2) => m._fdm_new(dt, root, out2));
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
  check(status2) {
    this.afterCall();
    if (status2 !== 0) throw new FdmError(this.lastError(), status2);
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
  isWritable(handle) {
    return (this.module.call(() => this.module.raw._fdm_prop_flags(this.p, handle)) & PropFlag.WRITE) !== 0;
  }
  isInteger(handle) {
    return (this.module.call(() => this.module.raw._fdm_prop_flags(this.p, handle)) & PropFlag.INTEGER) !== 0;
  }
  get(handle) {
    return this.module.call(() => this.module.raw._fdm_get(this.p, handle));
  }
  getByName(name) {
    return this.get(this.prop(name));
  }
  /**
   * Writes one property and returns the value read back.
   * Throws FdmError (status = SetStatus) for a read-only property, NaN/infinity, a non-integer written to an
   * integer property, or a setter that refused. The property is unchanged in those cases.
   */
  set(handle, value) {
    const m = this.module.raw;
    if (typeof value !== "number") throw new FdmError("set: value must be a number", SetStatus.NAN);
    const status2 = this.module.call(() => m._fdm_set(this.p, handle, value));
    this.afterCall();
    if (status2 === SetStatus.OK || status2 === SetStatus.READBACK_DIFFERS) return this.module.call(() => m._fdm_set_readback(this.p));
    const detail = status2 === SetStatus.REJECTED ? `: ${this.lastError()}` : "";
    throw new FdmError(`set refused (${SET_STATUS_NAME[status2] ?? status2})${detail}`, status2);
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

// ts/worker-handler.ts
var WorkerClient = class {
  constructor(send) {
    __publicField(this, "onEvent");
    __publicField(this, "onLog");
    __publicField(this, "nextId", 1);
    __publicField(this, "pending", /* @__PURE__ */ new Map());
    __publicField(this, "send");
    this.send = send;
  }
  /** Feed every message that arrives from the worker into this. */
  receive(message) {
    if (message && message.type === "event") {
      if (this.onEvent) this.onEvent(message.event);
      return;
    }
    if (message && message.type === "log") {
      if (this.onLog) this.onLog(message.record);
      return;
    }
    const p = this.pending.get(message.id);
    if (!p) return;
    this.pending.delete(message.id);
    if (message.ok) p.resolve(message);
    else p.reject(new Error(message.error));
  }
  /** Fails every request still waiting (the worker died). */
  failAll(reason) {
    for (const p of this.pending.values()) p.reject(new Error(reason));
    this.pending.clear();
  }
  request(body, transfer) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.send({ ...body, id }, transfer);
    });
  }
};

// web/page.ts
var VARIANT_NAME = { weh: "-fwasm-exceptions", jseh: "-fexceptions" };
var V = "30f1c44d37";
var asset = (name) => new URL(`${name}?v=${V}`, location.href).href;
var FIX_PATHS = { aircraft: "/fix/aircraft", engine: "engine", systems: "systems" };
var DTS = [["1/120", 1 / 120], ["1/240", 1 / 240], ["1/480", 1 / 480], ["1/1000", 1 / 1e3]];
var out = document.getElementById("out");
var statusEl = document.getElementById("status");
var lines = [];
function line(text = "") {
  lines.push(text);
  out.textContent = lines.join("\n");
}
function status(text) {
  statusEl.textContent = text;
}
var sleep = (ms) => new Promise((r) => setTimeout(r, ms));
var nextFrame = () => new Promise((r) => requestAnimationFrame(r));
var errText = (e) => e instanceof Error ? `${e.name}: ${e.message}` : String(e);
var oneLine = (s) => s.replace(/\s+/g, " ").trim();
var uncaught = 0;
window.addEventListener("error", (e) => {
  uncaught++;
  line(`UNCAUGHT ERROR: ${e.message} (${e.filename}:${e.lineno})`);
});
window.addEventListener("unhandledrejection", (e) => {
  uncaught++;
  line(`UNHANDLED REJECTION: ${errText(e.reason)}`);
});
var marker = {
  get() {
    try {
      return sessionStorage.getItem("fdm-starting");
    } catch {
      return null;
    }
  },
  set(v) {
    try {
      if (v === null) sessionStorage.removeItem("fdm-starting");
      else sessionStorage.setItem("fdm-starting", v);
    } catch {
    }
  }
};
function timerResolutionMs() {
  let min = Infinity, last = performance.now(), changes = 0;
  const end = last + 200;
  while (changes < 50 && performance.now() < end) {
    const t = performance.now();
    if (t !== last) {
      min = Math.min(min, t - last);
      last = t;
      changes++;
    }
  }
  return min;
}
async function fetchBytes(name) {
  const res = await fetch(asset(name));
  if (!res.ok) throw new Error(`cannot fetch ${name}: ${res.status}`);
  return new Uint8Array(await res.arrayBuffer());
}
function newWorker() {
  const worker = new Worker(asset("worker.js"), { type: "module" });
  const client = new WorkerClient((message, transfer) => worker.postMessage(message, transfer ?? []));
  worker.onmessage = (e) => client.receive(e.data);
  worker.onerror = (e) => client.failAll(`worker error: ${e.message}`);
  return { worker, client };
}
function fmtBench(r) {
  return `${r.usPerStep.toFixed(1)}`;
}
async function runVariant(variant, shared) {
  const name = VARIANT_NAME[variant];
  let ok = true;
  const fail = (what) => {
    ok = false;
    line(`  ** FAILED: ${what}`);
  };
  line(`===== Build ${name} (fdm-${variant}) =====`);
  const info = define_BUILD_INFO_default.files[`fdm-${variant}.wasm`];
  line(`wasm ${info.bytes} bytes, sha256 ${info.sha256.slice(0, 16)}...`);
  status(`${name}: loading`);
  let t0 = performance.now();
  const wasmBinary = await fetchBytes(`fdm-${variant}.wasm`);
  const tFetch = performance.now() - t0;
  t0 = performance.now();
  const logs = [];
  const factory = (await import(asset(`fdm-${variant}.mjs`))).default;
  const module = await loadFdmModule(factory, { wasmBinary, onLog: (r) => logs.push(`${r.levelName}: ${r.text}`) });
  writeFiles(module, "/data", readPack(shared.dataPack));
  writeFiles(module, "/fix", readPack(shared.fixPack));
  line(`1. Start. Main thread: ${module.version()}; fixed memory ${module.memoryBytes() / 1048576} MiB; wasm download ${tFetch.toFixed(0)} ms, module + files ${(performance.now() - t0).toFixed(0)} ms`);
  t0 = performance.now();
  const { worker, client } = newWorker();
  let workerEvents = 0;
  client.onEvent = () => workerEvents++;
  const init = await client.request({ type: "init", moduleUrl: asset(`fdm-${variant}.mjs`), wasmBinary: wasmBinary.slice(), packs: [["/data", shared.dataPack], ["/fix", shared.fixPack]] });
  line(`   Worker: ${init.version}; fixed memory ${init.memoryBytes / 1048576} MiB; start ${(performance.now() - t0).toFixed(0)} ms`);
  marker.set(null);
  status(`${name}: broken aircraft`);
  line("2. Broken aircraft (malformed XML), caught and shown:");
  {
    const f = Fdm.create(module, { paths: FIX_PATHS });
    let caught;
    try {
      f.loadModel("broken_xml");
    } catch (e) {
      caught = e;
    } finally {
      f.dispose();
    }
    const isError = caught instanceof Error;
    const msg = isError ? oneLine(caught.message) : String(caught);
    line(`   main thread: ${isError ? `Error (${caught.name})` : "NOT an Error"}: ${msg}`);
    if (!isError || !/XML parse error/.test(msg)) fail("main thread: no Error carrying JSBSim's message");
    const w = await client.request({ type: "tryload", model: "broken_xml", paths: FIX_PATHS });
    line(`   Worker: ${w.loaded ? "LOADED?!" : `${w.isError ? `Error (${w.errorName})` : "NOT an Error"}: ${oneLine(w.message)}`}`);
    if (w.loaded || !w.isError || !/XML parse error/.test(w.message)) fail("Worker: no Error carrying JSBSim's message");
    const g = Fdm.create(module);
    g.loadModel("c172x");
    g.loadIC("reset01");
    g.runIC();
    const r = g.step(120);
    line(`   afterwards a good aircraft loads and flies 120 steps on the main thread: ${r === StepResult.OK ? "yes" : `NO (result ${r})`}`);
    if (r !== StepResult.OK) fail("good aircraft after the broken one");
    g.dispose();
  }
  line("3. Time per step, microseconds (c172x airborne; median of 5 fresh instances x 3000 single steps after 300 warm-up steps;");
  line("   one call into WebAssembly per step, 16 outputs read per step; '20 forces' = 20 force magnitudes written every step):");
  line("   dt      | Worker: no forces | Worker: 20 forces | main: no forces | main: 20 forces");
  let cells = 0;
  for (const [label, dt] of DTS) {
    const row = [];
    for (const where of ["worker", "main"]) {
      for (const forces of [0, 20]) {
        status(`${name}: timing dt ${label}, ${where}, ${forces} forces`);
        await sleep(0);
        const options = { dt, forces, fixtureAircraftPath: "/fix/aircraft" };
        try {
          const r = where === "worker" ? (await client.request({ type: "bench", options })).result : benchSteps(module, options);
          if (Number.isFinite(r.usPerStep)) cells++;
          row.push(fmtBench(r));
        } catch (e) {
          row.push(`ERROR ${errText(e)}`);
        }
      }
    }
    line(`   ${label.padEnd(7)} | ${row[0].padStart(17)} | ${row[1].padStart(17)} | ${row[2].padStart(15)} | ${row[3].padStart(15)}`);
  }
  if (cells !== 16) fail(`timing: ${cells} of 16 cells have a number`);
  {
    const options = { dt: 1 / 120, forces: 140, fixtureAircraftPath: "/fix/aircraft" };
    const w = (await client.request({ type: "bench", options })).result;
    const m = benchSteps(module, options);
    line(`   extra, dt 1/120, 20 forces with all 140 values written: Worker ${fmtBench(w)}, main ${fmtBench(m)}; end of last run: ${m.endAltitudeFt.toFixed(0)} ft, ${m.endAirspeedKt.toFixed(0)} kt`);
  }
  status(`${name}: create/destroy`);
  line("4. Memory. One instance created, loaded, stepped 100 times and destroyed, 20 times in the same module:");
  for (const where of ["Worker", "main thread"]) {
    try {
      const c = where === "Worker" ? await client.request({ type: "cycles", count: 20, model: "c172x", ic: "reset01", steps: 100 }) : runCycles(module, 20, "c172x", "reset01", 100);
      const h = c.heap;
      line(`   ${where}: 20 of 20 done; C heap in use after cycle 1: ${h[0]}, cycle 2: ${h[1]}, cycle 20: ${h[19]} bytes (growth from 2 to 20: ${h[19] - h[1]}); heap top ${(c.heapTop / 1048576).toFixed(2)} MiB of ${c.memoryBytes / 1048576}`);
      if (h.length !== 20) fail(`${where}: cycles incomplete`);
    } catch (e) {
      fail(`${where}: create/destroy cycles: ${errText(e)}`);
    }
  }
  try {
    t0 = performance.now();
    for (let i = 0; i < 20; i++) {
      const m2 = await loadFdmModule(factory, { wasmBinary });
      writeFiles(m2, "/data", readPack(shared.dataPack));
      const f = Fdm.create(m2);
      f.loadModel("c172x");
      f.loadIC("reset01");
      f.runIC();
      if (f.step(10) !== StepResult.OK) throw new Error(`module ${i}: step failed`);
      f.dispose();
    }
    line(`   20 fresh modules on the main thread (each ${module.memoryBytes() / 1048576} MiB, dropped after use): 20 of 20 done in ${(performance.now() - t0).toFixed(0)} ms`);
  } catch (e) {
    fail(`fresh modules on the main thread: ${errText(e)}`);
  }
  try {
    t0 = performance.now();
    for (let i = 0; i < 20; i++) {
      const w2 = newWorker();
      await w2.client.request({ type: "init", moduleUrl: asset(`fdm-${variant}.mjs`), wasmBinary: wasmBinary.slice(), packs: [["/data", shared.dataPack]] });
      await w2.client.request({ type: "create", model: "c172x", ic: "reset01", outputs: ["simulation/sim-time-sec"] });
      await w2.client.request({ type: "dispose" });
      w2.worker.terminate();
    }
    line(`   20 fresh Workers (started, used, terminated): 20 of 20 done in ${(performance.now() - t0).toFixed(0)} ms`);
  } catch (e) {
    fail(`fresh Workers: ${errText(e)}`);
  }
  status(`${name}: loop`);
  line("5. Fixed-step loop in the Worker (1/120 s), driven by display frames for 2 s:");
  try {
    let hiddenEvents = 0;
    const onVis = () => {
      hiddenEvents++;
      void client.request({ type: document.hidden ? "pause" : "resume" });
    };
    document.addEventListener("visibilitychange", onVis);
    await client.request({ type: "create", model: "c172x", ic: "reset01", outputs: ["simulation/sim-time-sec", "position/h-sl-ft", "attitude/theta-rad"] });
    const start = performance.now();
    let frames = 0, state, maxSteps = 0;
    while (performance.now() - start < 2e3) {
      const now = await Promise.race([nextFrame(), sleep(250).then(() => performance.now())]);
      state = await client.request({ type: "tick", now: now / 1e3 });
      frames++;
      maxSteps = Math.max(maxSteps, state.steps);
    }
    const wall = (performance.now() - start) / 1e3;
    line(`   ${frames} frames in ${wall.toFixed(2)} s (${(frames / wall).toFixed(0)} per s); ${state.totalSteps} steps; sim time ${state.simTime.toFixed(3)} s; most steps in one frame ${maxSteps}; time dropped ${state.droppedSeconds.toFixed(3)} s`);
    line(`   last frame: prev and curr are ${(state.curr[0] - state.prev[0]).toFixed(6)} s apart, alpha ${state.alpha.toFixed(3)}; altitude ${state.curr[1].toFixed(1)} ft`);
    if (!(state.totalSteps > 0) || !(state.alpha >= 0 && state.alpha < 1)) fail("loop did not step");
    await client.request({ type: "pause" });
    await sleep(500);
    const paused = await client.request({ type: "tick", now: performance.now() / 1e3 });
    await client.request({ type: "resume" });
    const first = await client.request({ type: "tick", now: performance.now() / 1e3 });
    await sleep(50);
    const second = await client.request({ type: "tick", now: performance.now() / 1e3 });
    line(`   paused 0.5 s: steps while paused ${paused.steps}; first frame after resume ${first.steps} steps (no catch-up); a frame 50 ms later ${second.steps} steps`);
    if (paused.steps !== 0 || first.steps !== 0) fail("pause/resume caught up");
    line(`   page hidden/shown events during this section: ${hiddenEvents}; events from the Worker: ${workerEvents}`);
    document.removeEventListener("visibilitychange", onVis);
    await client.request({ type: "dispose" });
  } catch (e) {
    fail(`loop: ${errText(e)}`);
  }
  worker.terminate();
  line(`JSBSim log records received on the main thread: ${logs.length}`);
  line(`RESULT ${name}: ${ok ? "all sections finished, lines met" : "FAILED (see above)"}`);
  line();
  return ok;
}
async function main() {
  const params = new URLSearchParams(location.search);
  const asked = params.get("build");
  line("FDM JSBSim baseline: device test");
  line(`page build ${V}; ${define_BUILD_INFO_default.jsbsim} (${define_BUILD_INFO_default.commit.slice(0, 8)}), unpatched; ${define_BUILD_INFO_default.emscripten}`);
  line(`date ${(/* @__PURE__ */ new Date()).toISOString()}`);
  line(`user agent: ${navigator.userAgent}`);
  line(`screen ${screen.width}x${screen.height} @${devicePixelRatio}; cores ${navigator.hardwareConcurrency}; standalone app: ${navigator.standalone === true ? "yes" : "no"}`);
  line(`timer resolution (performance.now): ${timerResolutionMs().toFixed(3)} ms; cross-origin isolated: ${String(self.crossOriginIsolated)}`);
  let variants = asked === "weh" ? ["weh"] : asked === "jseh" ? ["jseh"] : ["weh", "jseh"];
  if (!asked && marker.get() === "weh") {
    line("NOTE: the previous load of this page stopped while starting the -fwasm-exceptions build. Running -fexceptions only (fallback).");
    variants = ["jseh"];
    marker.set(null);
  }
  line(`builds in this run: ${variants.map((v) => VARIANT_NAME[v]).join(", ")}`);
  line();
  const shared = { dataPack: await fetchBytes("data.pack"), fixPack: await fetchBytes("fix.pack") };
  const results = {};
  for (const v of variants) {
    if (v === "weh") marker.set("weh");
    try {
      results[v] = await runVariant(v, shared);
    } catch (e) {
      results[v] = false;
      line(`  ** FAILED: build ${VARIANT_NAME[v]} stopped: ${errText(e)}`);
      line();
    }
    marker.set(null);
  }
  line("SUMMARY");
  for (const v of variants) line(`  ${VARIANT_NAME[v]}: ${results[v] ? "PASS" : "FAIL"}`);
  line(`  uncaught errors: ${uncaught}`);
  line("DONE");
  status(Object.values(results).every(Boolean) && uncaught === 0 ? "DONE. Tap Copy results." : "DONE, with failures. Tap Copy results.");
}
var copyButton = document.getElementById("copy");
copyButton.onclick = async () => {
  const text = lines.join("\n");
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  copyButton.textContent = "Copied";
};
for (const [id, build] of [["both", ""], ["weh", "weh"], ["jseh", "jseh"]]) {
  document.getElementById(id).onclick = () => {
    const target = location.pathname + (build ? `?build=${build}` : "");
    if (target === location.pathname + location.search) location.reload();
    else location.assign(target);
  };
}
main().catch((e) => {
  line(`** FAILED: the page stopped: ${errText(e)}`);
  line("DONE");
  status("Stopped with an error. Tap Copy results.");
}).finally(() => {
  copyButton.disabled = false;
});
