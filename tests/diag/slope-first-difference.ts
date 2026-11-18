import { classA } from "../lib/compare.ts";
import { slopeGrid } from "../lib/grids.ts";
import { loadWithData } from "../lib/harness.ts";
import { STATE_COLUMNS, type Scenario, runNative, runWasmCpp } from "../lib/scenario.ts";
const extra = ["position/lat-geod-rad", "position/long-gc-rad", "position/geod-alt-ft", "position/radius-to-vehicle-ft", "gear/unit[0]/compression-ft", "gear/unit[1]/compression-ft", "gear/unit[2]/compression-ft", "forces/fbz-gear-lbs", "forces/fbx-gear-lbs", "forces/fbz-aero-lbs", "forces/fbz-prop-lbs", "accelerations/udot-ft_sec2", "accelerations/wdot-ft_sec2"];
const sc: Scenario = { name: "slope-rest-diag", root: "@data", dt: 1 / 120, model: "c172x", ic: "reset00", sets: [["fcs/left-brake-cmd-norm", 1], ["fcs/right-brake-cmd-norm", 1]], outs: [...STATE_COLUMNS, ...extra], outGear: true, steps: 1200, ground: slopeGrid(29.593978, -95.163839, "north", 5) };
const native = runNative([sc])[0];
const { module } = await loadWithData("weh");
const wasm = runWasmCpp(module, sc);
console.log(native.meta.stage, native.meta.message, wasm.meta.stage, wasm.meta.message);
const n = native.trace.columns.length;
const ulp = (x: number) => { const a = Math.abs(x); if (a === 0) return 5e-324; const b = new Float64Array([a]); const u = new BigUint64Array(b.buffer); u[0] += 1n; return b[0] - a; };
for (const row of [0, 1, 2, 3, 10, 100, 600, 1200]) {
  console.log(`--- row ${row}`);
  for (let c = 0; c < n; c++) {
    const a = native.trace.data[row * n + c], b = wasm.trace.data[row * n + c];
    if (a !== b) console.log(`  ${native.trace.columns[c].padEnd(34)} native ${a.toPrecision(17).padEnd(24)} d ${(b - a).toExponential(2).padStart(10)}  = ${((b - a) / ulp(a)).toFixed(1)} ulp`);
  }
}
// first row at which each column differs
console.log("--- first differing row per column");
for (let c = 0; c < n; c++) { let r = 0; while (r < native.trace.rows && native.trace.data[r * n + c] === wasm.trace.data[r * n + c]) r++; console.log(`  ${native.trace.columns[c].padEnd(34)} ${r < native.trace.rows ? r : "never"}`); }
