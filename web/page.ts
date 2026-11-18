// iPhone test page (criterion 9). Runs the same core on the main thread and in a Web Worker.
// Everything it prints goes into one block of text that the user copies back.
import { type BenchResult, benchSteps, runCycles } from "../ts/bench.ts";
import { StepResult } from "../ts/codes.ts";
import { Fdm, type FdmFactory, type FdmModule, loadFdmModule } from "../ts/core.ts";
import { readPack, writeFiles } from "../ts/files.ts";
import { WorkerClient } from "../ts/worker-handler.ts";

declare const __BUILD_ID__: string;
declare const __BUILD_INFO__: {
  jsbsim: string; commit: string; emscripten: string; memoryBytes: number;
  files: Record<string, { bytes: number; sha256: string }>;
};

type Variant = "weh" | "jseh";
const VARIANT_NAME: Record<Variant, string> = { weh: "-fwasm-exceptions", jseh: "-fexceptions" };
const V = __BUILD_ID__;
const asset = (name: string): string => new URL(`${name}?v=${V}`, location.href).href;
const FIX_PATHS = { aircraft: "/fix/aircraft", engine: "engine", systems: "systems" };
const DTS: [string, number][] = [["1/120", 1 / 120], ["1/240", 1 / 240], ["1/480", 1 / 480], ["1/1000", 1 / 1000]];

const out = document.getElementById("out") as HTMLPreElement;
const statusEl = document.getElementById("status") as HTMLElement;
const lines: string[] = [];
function line(text = ""): void {
  lines.push(text);
  out.textContent = lines.join("\n");
}
function status(text: string): void {
  statusEl.textContent = text;
}
const sleep = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms));
const nextFrame = (): Promise<number> => new Promise((r) => requestAnimationFrame(r));
const errText = (e: unknown): string => (e instanceof Error ? `${e.name}: ${e.message}` : String(e));
const oneLine = (s: string): string => s.replace(/\s+/g, " ").trim();

let uncaught = 0;
window.addEventListener("error", (e) => {
  uncaught++;
  line(`UNCAUGHT ERROR: ${e.message} (${e.filename}:${e.lineno})`);
});
window.addEventListener("unhandledrejection", (e) => {
  uncaught++;
  line(`UNHANDLED REJECTION: ${errText(e.reason)}`);
});

/** The marker that lets a reload fall back to -fexceptions if -fwasm-exceptions killed the page at startup. */
const marker = {
  get(): string | null {
    try {
      return sessionStorage.getItem("fdm-starting");
    } catch {
      return null;
    }
  },
  set(v: string | null): void {
    try {
      if (v === null) sessionStorage.removeItem("fdm-starting");
      else sessionStorage.setItem("fdm-starting", v);
    } catch {
      /* private mode: no marker */
    }
  },
};

function timerResolutionMs(): number {
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

async function fetchBytes(name: string): Promise<Uint8Array> {
  const res = await fetch(asset(name));
  if (!res.ok) throw new Error(`cannot fetch ${name}: ${res.status}`);
  return new Uint8Array(await res.arrayBuffer());
}

interface Shared { dataPack: Uint8Array; fixPack: Uint8Array }

function newWorker(): { worker: Worker; client: WorkerClient } {
  const worker = new Worker(asset("worker.js"), { type: "module" });
  const client = new WorkerClient((message, transfer) => worker.postMessage(message, transfer ?? []));
  worker.onmessage = (e) => client.receive(e.data);
  worker.onerror = (e) => client.failAll(`worker error: ${e.message}`);
  return { worker, client };
}

function fmtBench(r: BenchResult): string {
  return `${r.usPerStep.toFixed(1)}`;
}

/** Runs every section for one build. Returns true when the build meets the page's lines. */
async function runVariant(variant: Variant, shared: Shared): Promise<boolean> {
  const name = VARIANT_NAME[variant];
  let ok = true;
  const fail = (what: string): void => {
    ok = false;
    line(`  ** FAILED: ${what}`);
  };
  line(`===== Build ${name} (fdm-${variant}) =====`);
  const info = __BUILD_INFO__.files[`fdm-${variant}.wasm`];
  line(`wasm ${info.bytes} bytes, sha256 ${info.sha256.slice(0, 16)}...`);

  // --- 1. start: main thread and Worker ---------------------------------------------------------------
  status(`${name}: loading`);
  let t0 = performance.now();
  const wasmBinary = await fetchBytes(`fdm-${variant}.wasm`);
  const tFetch = performance.now() - t0;
  t0 = performance.now();
  const logs: string[] = [];
  const factory = (await import(asset(`fdm-${variant}.mjs`))).default as FdmFactory;
  const module: FdmModule = await loadFdmModule(factory, { wasmBinary, onLog: (r) => logs.push(`${r.levelName}: ${r.text}`) });
  writeFiles(module, "/data", readPack(shared.dataPack));
  writeFiles(module, "/fix", readPack(shared.fixPack));
  line(`1. Start. Main thread: ${module.version()}; fixed memory ${module.memoryBytes() / 1048576} MiB; wasm download ${tFetch.toFixed(0)} ms, module + files ${(performance.now() - t0).toFixed(0)} ms`);
  t0 = performance.now();
  const { worker, client } = newWorker();
  let workerEvents = 0;
  client.onEvent = () => workerEvents++;
  const init = await client.request({ type: "init", moduleUrl: asset(`fdm-${variant}.mjs`), wasmBinary: wasmBinary.slice(), packs: [["/data", shared.dataPack], ["/fix", shared.fixPack]] });
  line(`   Worker: ${init.version}; fixed memory ${init.memoryBytes / 1048576} MiB; start ${(performance.now() - t0).toFixed(0)} ms`);
  marker.set(null); // this build started: no fallback needed on the next load

  // --- 2. a broken aircraft is caught and shown -------------------------------------------------------
  status(`${name}: broken aircraft`);
  line("2. Broken aircraft (malformed XML), caught and shown:");
  {
    const f = Fdm.create(module, { paths: FIX_PATHS });
    let caught: unknown;
    try {
      f.loadModel("broken_xml");
    } catch (e) {
      caught = e;
    } finally {
      f.dispose();
    }
    const isError = caught instanceof Error;
    const msg = isError ? oneLine((caught as Error).message) : String(caught);
    line(`   main thread: ${isError ? `Error (${(caught as Error).name})` : "NOT an Error"}: ${msg}`);
    if (!isError || !/XML parse error/.test(msg)) fail("main thread: no Error carrying JSBSim's message");
    const w = await client.request({ type: "tryload", model: "broken_xml", paths: FIX_PATHS });
    line(`   Worker: ${w.loaded ? "LOADED?!" : `${w.isError ? `Error (${w.errorName})` : "NOT an Error"}: ${oneLine(w.message)}`}`);
    if (w.loaded || !w.isError || !/XML parse error/.test(w.message)) fail("Worker: no Error carrying JSBSim's message");
    // The module still works afterwards.
    const g = Fdm.create(module);
    g.loadModel("c172x");
    g.loadIC("reset01");
    g.runIC();
    const r = g.step(120);
    line(`   afterwards a good aircraft loads and flies 120 steps on the main thread: ${r === StepResult.OK ? "yes" : `NO (result ${r})`}`);
    if (r !== StepResult.OK) fail("good aircraft after the broken one");
    g.dispose();
  }

  // --- 3. timing ------------------------------------------------------------------------------------------
  line("3. Time per step, microseconds (c172x airborne; median of 5 fresh instances x 3000 single steps after 300 warm-up steps;");
  line("   one call into WebAssembly per step, 16 outputs read per step; '20 forces' = 20 force magnitudes written every step):");
  line("   dt      | Worker: no forces | Worker: 20 forces | main: no forces | main: 20 forces");
  let cells = 0;
  for (const [label, dt] of DTS) {
    const row: string[] = [];
    for (const where of ["worker", "main"] as const) {
      for (const forces of [0, 20] as const) {
        status(`${name}: timing dt ${label}, ${where}, ${forces} forces`);
        await sleep(0);
        const options = { dt, forces, fixtureAircraftPath: "/fix/aircraft" };
        try {
          const r: BenchResult = where === "worker" ? (await client.request({ type: "bench", options })).result : benchSteps(module, options);
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
    // Extra, for information: all 140 values of the 20 forces written every step, at 1/120 s.
    const options = { dt: 1 / 120, forces: 140 as const, fixtureAircraftPath: "/fix/aircraft" };
    const w: BenchResult = (await client.request({ type: "bench", options })).result;
    const m = benchSteps(module, options);
    line(`   extra, dt 1/120, 20 forces with all 140 values written: Worker ${fmtBench(w)}, main ${fmtBench(m)}; end of last run: ${m.endAltitudeFt.toFixed(0)} ft, ${m.endAirspeedKt.toFixed(0)} kt`);
  }

  // --- 4. memory: create and destroy ------------------------------------------------------------------
  status(`${name}: create/destroy`);
  line("4. Memory. One instance created, loaded, stepped 100 times and destroyed, 20 times in the same module:");
  for (const where of ["Worker", "main thread"] as const) {
    try {
      const c = where === "Worker" ? await client.request({ type: "cycles", count: 20, model: "c172x", ic: "reset01", steps: 100 }) : runCycles(module, 20, "c172x", "reset01", 100);
      const h: number[] = c.heap;
      line(`   ${where}: 20 of 20 done; C heap in use after cycle 1: ${h[0]}, cycle 2: ${h[1]}, cycle 20: ${h[19]} bytes (growth from 2 to 20: ${h[19] - h[1]}); heap top ${(c.heapTop / 1048576).toFixed(2)} MiB of ${c.memoryBytes / 1048576}`);
      if (h.length !== 20) fail(`${where}: cycles incomplete`);
    } catch (e) {
      fail(`${where}: create/destroy cycles: ${errText(e)}`);
    }
  }
  // 20 fresh WebAssembly modules (each with its own fixed memory), then 20 fresh Workers.
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

  // --- 5. the loop in the Worker, driven by the display's frames -----------------------------------------
  status(`${name}: loop`);
  line("5. Fixed-step loop in the Worker (1/120 s), driven by display frames for 2 s:");
  try {
    let hiddenEvents = 0;
    const onVis = (): void => {
      hiddenEvents++;
      void client.request({ type: document.hidden ? "pause" : "resume" });
    };
    document.addEventListener("visibilitychange", onVis);
    await client.request({ type: "create", model: "c172x", ic: "reset01", outputs: ["simulation/sim-time-sec", "position/h-sl-ft", "attitude/theta-rad"] });
    const start = performance.now();
    let frames = 0, state: any, maxSteps = 0;
    while (performance.now() - start < 2000) {
      // A frame, or 250 ms if the page is hidden and frames have stopped.
      const now = await Promise.race([nextFrame(), sleep(250).then(() => performance.now())]);
      state = await client.request({ type: "tick", now: now / 1000 });
      frames++;
      maxSteps = Math.max(maxSteps, state.steps);
    }
    const wall = (performance.now() - start) / 1000;
    line(`   ${frames} frames in ${wall.toFixed(2)} s (${(frames / wall).toFixed(0)} per s); ${state.totalSteps} steps; sim time ${state.simTime.toFixed(3)} s; most steps in one frame ${maxSteps}; time dropped ${state.droppedSeconds.toFixed(3)} s`);
    line(`   last frame: prev and curr are ${(state.curr[0] - state.prev[0]).toFixed(6)} s apart, alpha ${state.alpha.toFixed(3)}; altitude ${state.curr[1].toFixed(1)} ft`);
    if (!(state.totalSteps > 0) || !(state.alpha >= 0 && state.alpha < 1)) fail("loop did not step");
    // Pause as the page does when hidden, wait, resume: no catch-up.
    await client.request({ type: "pause" });
    await sleep(500);
    const paused = await client.request({ type: "tick", now: performance.now() / 1000 });
    await client.request({ type: "resume" });
    const first = await client.request({ type: "tick", now: performance.now() / 1000 });
    await sleep(50);
    const second = await client.request({ type: "tick", now: performance.now() / 1000 });
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

async function main(): Promise<void> {
  const params = new URLSearchParams(location.search);
  const asked = params.get("build");
  line("FDM JSBSim baseline: device test");
  line(`page build ${V}; ${__BUILD_INFO__.jsbsim} (${__BUILD_INFO__.commit.slice(0, 8)}), unpatched; ${__BUILD_INFO__.emscripten}`);
  line(`date ${new Date().toISOString()}`);
  line(`user agent: ${navigator.userAgent}`);
  line(`screen ${screen.width}x${screen.height} @${devicePixelRatio}; cores ${navigator.hardwareConcurrency}; standalone app: ${(navigator as any).standalone === true ? "yes" : "no"}`);
  line(`timer resolution (performance.now): ${timerResolutionMs().toFixed(3)} ms; cross-origin isolated: ${String(self.crossOriginIsolated)}`);

  // Which builds to run. If the last load died while starting -fwasm-exceptions, skip it this time.
  let variants: Variant[] = asked === "weh" ? ["weh"] : asked === "jseh" ? ["jseh"] : ["weh", "jseh"];
  if (!asked && marker.get() === "weh") {
    line("NOTE: the previous load of this page stopped while starting the -fwasm-exceptions build. Running -fexceptions only (fallback).");
    variants = ["jseh"];
    marker.set(null);
  }
  line(`builds in this run: ${variants.map((v) => VARIANT_NAME[v]).join(", ")}`);
  line();

  const shared: Shared = { dataPack: await fetchBytes("data.pack"), fixPack: await fetchBytes("fix.pack") };
  const results: Record<string, boolean> = {};
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

const copyButton = document.getElementById("copy") as HTMLButtonElement;
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
for (const [id, build] of [["both", ""], ["weh", "weh"], ["jseh", "jseh"]] as const) {
  (document.getElementById(id) as HTMLButtonElement).onclick = () => {
    const target = location.pathname + (build ? `?build=${build}` : "");
    if (target === location.pathname + location.search) location.reload();
    else location.assign(target);
  };
}

main()
  .catch((e) => {
    line(`** FAILED: the page stopped: ${errText(e)}`);
    line("DONE");
    status("Stopped with an error. Tap Copy results.");
  })
  .finally(() => {
    copyButton.disabled = false;
  });
