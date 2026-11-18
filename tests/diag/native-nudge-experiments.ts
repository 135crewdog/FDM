import { fmt } from "../lib/compare.ts";
import { STATE_COLUMNS, type Scenario, ensembleScenarios, runNative } from "../lib/scenario.ts";
// A. c310: nudge the start heading by k * 2^-50 rad (one last digit of an angle near 2 pi). Native only.
for (const name of ["c3104", "c3105"]) {
  const sc: Scenario = { name: `conf-${name}`, root: "@data", dt: 0, script: `scripts/${name}.xml`, outs: [...STATE_COLUMNS, "ap/aileron_cmd", "fcs/left-aileron-pos-rad"], outGear: true, duration: 1 };
  const ks = [1, -1, 2, -2, 3, -3, 4, -4];
  const members = runNative(ks.map((k) => ({ ...sc, name: `${sc.name}-psi${k}`, adds: [["ic/psi-true-rad", k * 2 ** -50] as [string, number]] })), "conf");
  const base = runNative([sc], "conf")[0];
  const n = base.trace.columns.length, ci = (c: string) => base.trace.columns.indexOf(c);
  console.log(`== ${name}: native, start heading nudged by k * 2^-50 rad; rows ${base.trace.rows}`);
  console.log(`   unperturbed native psi at row 0: ${base.trace.data[ci("attitude/psi-rad")]}`);
  ks.forEach((k, i) => {
    const m = members[i].trace;
    let dl = 0, dn = 0, da = 0, row = -1;
    for (let r = 0; r < base.trace.rows; r++) {
      const d = Math.abs(m.data[r * n + ci("moments/l-total-lbsft")] - base.trace.data[r * n + ci("moments/l-total-lbsft")]);
      if (d > dl) { dl = d; row = r; }
      dn = Math.max(dn, Math.abs(m.data[r * n + ci("moments/n-total-lbsft")] - base.trace.data[r * n + ci("moments/n-total-lbsft")]));
      da = Math.max(da, Math.abs(m.data[r * n + ci("ap/aileron_cmd")] - base.trace.data[r * n + ci("ap/aileron_cmd")]));
    }
    console.log(`   k=${String(k).padStart(2)}: ${members[i].meta.stage}; psi at row 0 ${m.data[ci("attitude/psi-rad")].toPrecision(17)}; max |d l-total| ${fmt(dl)} at row ${row}; max |d n-total| ${fmt(dn)}; max |d ap/aileron_cmd| ${fmt(da)}`);
  });
}
// B. mk82: where do native runs with a one-last-digit altitude nudge go non-finite?
{
  const sc: Scenario = { name: "conf-mk82", root: "@data", dt: 0, script: "scripts/mk82_script.xml", outs: STATE_COLUMNS, outGear: true, steps: 12000 };
  const base = runNative([sc], "conf")[0];
  const members = runNative(ensembleScenarios(sc), "conf");
  console.log(`== mk82_script, native: unperturbed stops at step ${base.meta.stepsDone} (${base.meta.stage}, code ${base.meta.endCode})`);
  console.log(`   8 native runs with the start altitude nudged by +-1..4 last digits stop at steps: ${members.map((m) => m.meta.stepsDone).join(", ")}`);
  const n = base.trace.columns.length, q = base.trace.columns.indexOf("velocities/q-rad_sec"), t = 0;
  for (const lim of [10, 100, 1e6]) { let r = 0; while (r < base.trace.rows && Math.abs(base.trace.data[r * n + q]) < lim) r++; console.log(`   native pitch rate first exceeds ${lim} rad/s at step ${r} (t = ${base.trace.data[Math.min(r, base.trace.rows - 1) * n + t].toFixed(2)} s)`); }
}
