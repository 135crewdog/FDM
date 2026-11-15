// Browser-safe checks shared by the Node tests and the iPhone page.
import { JSBSim, JSBSimError } from "./jsbsim.ts";

export interface LoadResult {
  name: string; ok: boolean; ms: number; msg: string;
  /** false if the failure was not a JSBSimError (e.g. a WebAssembly trap): the module should be replaced. */
  clean: boolean;
}

/** Try loadModel(name) on a fresh FGFDMExec. Never throws. */
export function tryLoad(sim: JSBSim, name: string): LoadResult {
  const t0 = performance.now();
  try {
    sim.reset();
    sim.setDebugLevel(0);
    sim.loadModel(name);
    return { name, ok: true, ms: performance.now() - t0, msg: "", clean: true };
  } catch (e) {
    const msg = e instanceof Error ? e.message : `non-Error thrown: ${String(e)}`;
    const clean = e instanceof JSBSimError;
    return { name, ok: false, ms: performance.now() - t0, msg: (clean ? "" : "NOT A JSBSimError: ") + msg.replace(/\s+/g, " ").trim(), clean };
  }
}

// ---- 20 runtime external forces (wing-strip stand-in) ----

/** Add N runtime-controllable BODY-frame external forces to an aircraft file. */
export function withForces(xml: string, n: number): string {
  const forces = Array.from({ length: n }, (_, i) => `
    <force name="f${i}" frame="BODY">
      <location unit="IN"> <x> 43.2 </x> <y> 0 </y> <z> 59.4 </z> </location>
      <direction> <x> 0 </x> <y> 0 </y> <z> -1 </z> </direction>
    </force>`).join("");
  if (/<external_reactions>/.test(xml)) throw new Error("aircraft already has external_reactions");
  return xml.replace("</fdm_config>", `  <external_reactions>${forces}\n  </external_reactions>\n</fdm_config>`);
}

// Deterministic force schedule, same as tests/extforce/schedule.{ts,py}.
export function tri(k: number, period: number, phase: number): number {
  const x = ((k + phase) % period) / period;
  return x < 0.5 ? 4 * x - 1 : 3 - 4 * x;
}
export function forceAt(i: number, k: number): number[] {
  return [43.2 + 20 * tri(k, 700, 37 * i), 30 * tri(k, 900, 53 * i), 59.4 + 10 * tri(k, 500, 11 * i),
    0.3 * tri(k, 400, 7 * i), 0.2 * tri(k, 300, 13 * i), -1, 40 + 30 * tri(k, 250, 29 * i)];
}
export const FORCE_SUFFIX = ["location-x-in", "location-y-in", "location-z-in", "x", "y", "z", "magnitude"];
export const forceNames = (n: number) =>
  Array.from({ length: n }, (_, i) => FORCE_SUFFIX.map((s) => `external_reactions/f${i}/${s}`));

export type ForceMethod = "none" | "name" | "handle" | "bulk";

/** A minimal script: aircraft + init file, run "forever" at dt. */
export function timingScript(aircraft: string, init: string, dt: number): string {
  return `<?xml version="1.0"?>
<runscript name="timing ${aircraft}">
  <use aircraft="${aircraft}" initialize="${init}"/>
  <run start="0.0" end="100000" dt="${dt}"/>
</runscript>`;
}

export interface TimingResult {
  aircraft: string; dt: number; method: ForceMethod; steps: number; usPerStep: number; totalMs: number;
  altFt: number; kts: number;
}

/**
 * Load `scripts/<scriptName>` (already written), run warm-up steps, then time `steps` steps.
 * With forces (n > 0) the schedule is written every step by name, by handle, or as one bulk array.
 * Timing is over the whole batch (Safari's timer resolution is 1 ms; single steps cannot be timed).
 */
export function timeRun(sim: JSBSim, scriptPath: string, aircraft: string, dt: number, method: ForceMethod,
  nForces = 20, steps = 3000, warmup = 300): TimingResult {
  sim.reset();
  sim.setDebugLevel(0);
  sim.loadScript(scriptPath, dt);
  sim.runIC();
  const names = forceNames(nForces);
  let stepFn: (k: number) => void;
  if (method === "none") {
    stepFn = () => { sim.run(); };
  } else if (method === "name") {
    stepFn = (k) => {
      for (let i = 0; i < nForces; i++) { const v = forceAt(i, k); v[6] *= 0.1; for (let j = 0; j < 7; j++) sim.setProperty(names[i][j], v[j]); }
      sim.run();
    };
  } else if (method === "handle") {
    const hs = names.map((row) => row.map((n) => sim.handle(n)));
    stepFn = (k) => {
      for (let i = 0; i < nForces; i++) { const v = forceAt(i, k); v[6] *= 0.1; for (let j = 0; j < 7; j++) sim.set(hs[i][j], v[j]); }
      sim.run();
    };
  } else {
    sim.bindInputs(names.flat());
    sim.bindOutputs([]);
    stepFn = (k) => {
      const inp = sim.inputs;
      for (let i = 0; i < nForces; i++) { const v = forceAt(i, k); v[6] *= 0.1; for (let j = 0; j < 7; j++) inp[i * 7 + j] = v[j]; }
      sim.step(1);
    };
  }
  for (let k = 0; k < warmup; k++) stepFn(k);
  const t0 = performance.now();
  for (let k = 0; k < steps; k++) stepFn(warmup + k);
  const totalMs = performance.now() - t0;
  return {
    aircraft, dt, method, steps, usPerStep: (totalMs * 1000) / steps, totalMs,
    altFt: sim.getProperty("position/h-sl-ft"), kts: sim.getProperty("velocities/vtrue-kts"),
  };
}
