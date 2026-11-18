import { loadWithData } from "../lib/harness.ts";
import { type Scenario, ensembleScenarios, runNative, runWasmCpp } from "../lib/scenario.ts";
const { module } = await loadWithData("weh");
const cols = ["simulation/sim-time-sec", "moments/l-total-lbsft", "moments/l-aero-lbsft", "moments/l-prop-lbsft", "moments/l-gear-lbsft", "moments/l-external-lbsft", "moments/l-buoyancy-lbsft",
  "aero/qbar-psf", "aero/beta-rad", "aero/alpha-rad", "velocities/vt-fps", "velocities/u-aero-fps", "velocities/v-aero-fps", "velocities/w-aero-fps", "aero/bi2vel", "velocities/p-aero-rad_sec", "velocities/r-aero-rad_sec",
  "propulsion/engine[0]/thrust-lbs", "propulsion/engine[1]/thrust-lbs", "propulsion/engine[0]/engine-rpm", "propulsion/engine[0]/thrust-coefficient", "propulsion/engine[1]/thrust-coefficient", "propulsion/engine[0]/prop-induced-velocity_fps", "propulsion/engine[1]/prop-induced-velocity_fps", "propulsion/engine[0]/helical-tip-Mach", "fcs/left-aileron-pos-rad", "fcs/rudder-pos-rad", "fcs/aileron-cmd-norm", "ap/aileron_cmd", "attitude/phi-rad", "velocities/p-rad_sec", "accelerations/pdot-rad_sec2"];
for (const name of ["c3104"]) {
  const base: Scenario = { name: `diagb-${name}`, root: "@data", dt: 0, script: `scripts/${name}.xml`, outs: [], outGear: false, steps: 16 };
  // keep only columns that exist
  const probe = runNative([{ ...base, outs: ["simulation/sim-time-sec"] }])[0];
  const ok: string[] = [];
  for (const c of cols) { const r = runNative([{ ...base, name: "probe", outs: [c], steps: 0 }])[0]; if (r.meta.stage === "done") ok.push(c); else console.log("  (no property", c + ")"); }
  const sc = { ...base, outs: ok };
  const native = runNative([sc])[0], wasm = runWasmCpp(module, sc);
  const ens = runNative(ensembleScenarios(sc), "diag-ens2");
  const n = ok.length;
  for (const row of [12, 13, 14]) {
    console.log(`--- ${name} row ${row}`);
    for (let c = 0; c < n; c++) {
      const a = native.trace.data[row * n + c], b = wasm.trace.data[row * n + c];
      const members = ens.map((m) => (m.trace.data[row * n + c] - a).toExponential(1)).join(" ");
      console.log(`  ${ok[c].padEnd(46)} native ${a.toPrecision(12).padEnd(20)} wasm-native ${(b - a).toExponential(2).padStart(10)} | members-native: ${members}`);
    }
  }
}
