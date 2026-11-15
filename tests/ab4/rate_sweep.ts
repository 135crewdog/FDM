// Test 5b: does the AB4 rotational-rate integrator stay finite at higher simulation rates?
// usage: JSBSIM_VARIANT=jsbsim-weh tsx tests/ab4/rate_sweep.ts scripts/f16_test.xml
// Two different events are reported separately (the session 02 version mixed them up):
//   "rates > 1e6":  first time any body rate exceeds 1e6 rad/s in magnitude (a runaway; still finite)
//   "first NaN":    first time any monitored value is NaN or infinite
// The run continues after a runaway until the first non-finite value (or the end of the script).
// dt is given to loadScript, so it is set before the aircraft is loaded.
import { createSim, currentVariant, describeBuild, describeError } from "../../src/wasm.ts";

const script = process.argv[2] ?? "scripts/f16_test.xml";
const sim = await createSim();
const P = ["position/h-agl-ft", "velocities/vtrue-kts", "velocities/p-rad_sec", "velocities/q-rad_sec", "velocities/r-rad_sec", "attitude/phi-rad", "attitude/theta-rad",
  "velocities/u-fps", "velocities/v-fps", "velocities/w-fps", "position/h-sl-ft"];
console.log(`${script}: rate integrator default (1) vs AB4 (5) at several step sizes [${describeBuild(currentVariant())}]`);
console.log(`${"rate".padEnd(8)} ${"integ".padEnd(7)} ${"rates > 1e6 at t".padStart(16)} ${"first NaN at t".padStart(14)} ${"max|pqr| before".padStart(15)} ${"end h-agl ft".padStart(13)} ${"end kts".padStart(10)} ${"end phi".padStart(9)} ${"end theta".padStart(10)} ${"us/step".padStart(8)}`);
for (const hz of [120, 240, 480, 1000]) {
  for (const integ of [1, 5]) {
    sim.reset(); sim.setDebugLevel(0);
    let line = `${(hz + " Hz").padEnd(8)} ${(integ === 5 ? "AB4" : "default").padEnd(7)} `;
    try {
      sim.loadScript(script, 1 / hz);
      sim.setIntegrators({ rateRotational: integ });
      sim.runIC();
      const hs = P.map((p) => sim.handle(p));
      let runaway: number | undefined, nan: number | undefined, maxw = 0, n = 0;
      const t0 = performance.now();
      while (sim.run()) {
        n++;
        const v = hs.map((h) => sim.get(h));
        if (!v.every(Number.isFinite)) { nan = sim.simTime; break; }
        const w = Math.max(Math.abs(v[2]), Math.abs(v[3]), Math.abs(v[4]));
        if (w > 1e6 && runaway === undefined) runaway = sim.simTime;
        if (runaway === undefined) maxw = Math.max(maxw, w);
      }
      const us = ((performance.now() - t0) * 1000) / n;
      const v = hs.map((h) => sim.get(h));
      const f = (x: number, d: number) => (Number.isFinite(x) ? x.toFixed(d) : String(x));
      line += `${(runaway === undefined ? "never" : runaway.toFixed(3)).padStart(16)} ${(nan === undefined ? "never" : nan.toFixed(3)).padStart(14)} ${maxw.toExponential(2).padStart(15)} ${f(v[0], 2).padStart(13)} ${f(v[1], 2).padStart(10)} ${f(v[5], 3).padStart(9)} ${f(v[6], 3).padStart(10)} ${us.toFixed(1).padStart(8)}`;
    } catch (e) { line += "FAILED: " + describeError(e); }
    console.log(line);
  }
}
