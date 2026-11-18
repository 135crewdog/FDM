import { classS, compareTraces, describe, fmt, windowRows } from "../lib/compare.ts";
import { loadWithData } from "../lib/harness.ts";
import { STATE_COLUMNS, type Scenario, ensembleScenarios, headTrace, runNative, runWasmCpp } from "../lib/scenario.ts";
const { module } = await loadWithData("weh");
const ulp = (x: number) => { const a = Math.abs(x); if (a === 0) return 5e-324; const b = new Float64Array([a]); const u = new BigUint64Array(b.buffer); u[0] += 1n; return b[0] - a; };
// --- c310
const extra = ["propulsion/engine[0]/engine-rpm", "propulsion/engine[1]/engine-rpm", "propulsion/engine[0]/thrust-lbs", "propulsion/engine[1]/thrust-lbs", "propulsion/engine[0]/propeller-rpm", "propulsion/engine[0]/power-hp", "propulsion/engine[1]/power-hp", "moments/l-prop-lbsft", "moments/n-prop-lbsft", "moments/l-aero-lbsft", "moments/n-aero-lbsft", "moments/l-gear-lbsft", "forces/fbx-prop-lbs", "propulsion/engine[0]/advance-ratio", "propulsion/engine[1]/advance-ratio", "propulsion/engine[0]/map-inhg", "propulsion/engine[1]/map-inhg"];
for (const name of ["c3104", "c3105"]) {
  const sc: Scenario = { name: `diag-${name}`, root: "@data", dt: 0, script: `scripts/${name}.xml`, outs: [...STATE_COLUMNS, ...extra], outGear: true, steps: 130 };
  const native = runNative([sc])[0], wasm = runWasmCpp(module, sc);
  console.log(`===== ${name}: native ${native.meta.stage} ${native.meta.message}; wasm ${wasm.meta.stage}`);
  const n = native.trace.columns.length;
  console.log("first differing row per column (and the difference there):");
  for (let c = 0; c < n; c++) { let r = 0; while (r < native.trace.rows && native.trace.data[r * n + c] === wasm.trace.data[r * n + c]) r++; if (r < native.trace.rows) { const a = native.trace.data[r * n + c], b = wasm.trace.data[r * n + c]; console.log(`  ${native.trace.columns[c].padEnd(40)} row ${String(r).padStart(3)} native ${a.toPrecision(12).padEnd(20)} d ${(b - a).toExponential(2)} (${((b - a) / ulp(a)).toFixed(0)} ulp)`); } }
  const rows = windowRows(native.trace, { windowSeconds: 1 });
  const ev = name === "c3104" ? 13 : 31;
  for (const row of [ev - 1, ev, ev + 1, ev + 5]) {
    console.log(`--- row ${row}, t=${native.trace.data[row * n]}`);
    for (const col of ["propulsion/engine[0]/engine-rpm", "propulsion/engine[1]/engine-rpm", "propulsion/engine[0]/thrust-lbs", "propulsion/engine[1]/thrust-lbs", "moments/l-prop-lbsft", "moments/n-prop-lbsft", "moments/l-total-lbsft", "propulsion/engine[0]/advance-ratio", "propulsion/engine[1]/advance-ratio", "propulsion/engine[0]/power-hp"]) {
      const c = native.trace.columns.indexOf(col); const a = native.trace.data[row * n + c], b = wasm.trace.data[row * n + c];
      console.log(`  ${col.padEnd(40)} native ${a.toPrecision(15).padEnd(22)} wasm-native ${(b - a).toExponential(2)}`);
    }
  }
  // native ensemble: how much does native differ from itself after a one-last-digit nudge?
  const ens = runNative(ensembleScenarios({ ...sc, steps: rows - 1 }), "diag-ens");
  const eff = ens.filter((m) => m.trace.data.some((v, i) => i < n && v !== native.trace.data[i])).length;
  console.log(`native ensemble (start altitude +-1..4 last digits), first 1 s (${rows} rows), members with effect ${eff}:`);
  const nh = headTrace(native.trace, rows), wh = headTrace(wasm.trace, rows);
  for (const col of ["moments/l-total-lbsft", "moments/n-total-lbsft", "forces/fby-total-lbs", "velocities/p-rad_sec", "velocities/r-rad_sec", "velocities/v-fps", "attitude/phi-rad", "moments/l-prop-lbsft"]) {
    const c = nh.columns.indexOf(col);
    let dW = 0, S = 0;
    for (let r = 0; r < rows; r++) { dW = Math.max(dW, Math.abs(wh.data[r * n + c] - nh.data[r * n + c])); for (const m of ens) S = Math.max(S, Math.abs(m.trace.data[r * n + c] - nh.data[r * n + c])); }
    console.log(`  ${col.padEnd(28)} |wasm-native| ${fmt(dW)}   native ensemble spread ${fmt(S)}   ratio ${(dW / S).toFixed(2)}`);
  }
}
// --- mk82
{
  const sc: Scenario = { name: "diag-mk82", root: "@data", dt: 0, script: "scripts/mk82_script.xml", outs: STATE_COLUMNS, outGear: true, steps: 12000 };
  const native = runNative([sc])[0], wasm = runWasmCpp(module, sc);
  console.log("===== mk82_script");
  for (const [who, r] of [["native", native], ["wasm", wasm]] as const) console.log(`${who}: stage ${r.meta.stage}, steps ${r.meta.stepsDone}, endCode ${r.meta.endCode}, rows ${r.meta.rows}: ${r.meta.message.replace(/\s+/g, " ").slice(0, 300)}`);
  const n = native.trace.columns.length;
  const col = (t: typeof native.trace, row: number, name: string) => t.data[row * n + t.columns.indexOf(name)];
  const w1 = compareTraces(headTrace(native.trace, 51), headTrace(wasm.trace, 51), { tolerance: classS });
  console.log("first 1 s (51 rows), Class S (information):", describe(w1));
  const common = Math.min(native.trace.rows, wasm.trace.rows) - 1;
  for (const row of [0, 50, 500, 1000, 1500, 2000, 2100, 2200, 2230, 2240]) {
    if (row > common) continue;
    console.log(`  row ${row} t=${col(native.trace, row, "simulation/sim-time-sec").toFixed(2)}: native h-sl ${col(native.trace, row, "position/h-sl-ft").toExponential(6)} h-agl ${col(native.trace, row, "position/h-agl-ft").toExponential(4)} vt ${col(native.trace, row, "velocities/vtrue-kts").toExponential(4)} | wasm-native h-sl ${(col(wasm.trace, row, "position/h-sl-ft") - col(native.trace, row, "position/h-sl-ft")).toExponential(2)} q ${(col(wasm.trace, row, "velocities/q-rad_sec") - col(native.trace, row, "velocities/q-rad_sec")).toExponential(2)}`);
  }
  // last rows of each
  for (const [who, r] of [["native", native], ["wasm", wasm]] as const) { const row = r.trace.rows - 2; console.log(`  ${who} second-to-last row ${row}: t ${col(r.trace, row, "simulation/sim-time-sec").toFixed(2)} h-sl ${col(r.trace, row, "position/h-sl-ft").toExponential(4)} h-agl ${col(r.trace, row, "position/h-agl-ft").toExponential(4)} vt ${col(r.trace, row, "velocities/vtrue-kts").toExponential(4)} p ${col(r.trace, row, "velocities/p-rad_sec").toExponential(3)} q ${col(r.trace, row, "velocities/q-rad_sec").toExponential(3)}`); }
}
