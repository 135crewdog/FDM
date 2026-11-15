// Test 5b: does the AB4 rotational-rate integrator stay finite at higher simulation rates?
// usage: tsx tests/ab4/rate_sweep.ts scripts/f16_test.xml
import { createSim, describeError } from "../../src/wasm.ts";

const script = process.argv[2] ?? "scripts/f16_test.xml";
const sim = await createSim();
const P = ["position/h-agl-ft", "velocities/vtrue-kts", "velocities/p-rad_sec", "velocities/q-rad_sec", "velocities/r-rad_sec", "attitude/phi-rad", "attitude/theta-rad"];
console.log(`${script}: rate integrator default (1) vs AB4 (5) at several step sizes`);
console.log(`${"rate".padEnd(8)} ${"integ".padEnd(6)} ${"first non-finite t".padStart(18)} ${"max|pqr| rad/s".padStart(15)} ${"end h-agl ft".padStart(13)} ${"end kts".padStart(10)} ${"end phi".padStart(9)} ${"end theta".padStart(10)} ${"us/step".padStart(8)}`);
for (const hz of [120, 240, 480, 1000]) {
  for (const integ of [1, 5]) {
    sim.reset(); sim.setDebugLevel(0);
    let line = `${(hz + " Hz").padEnd(8)} ${(integ === 5 ? "AB4" : "default").padEnd(6)} `;
    try {
      sim.loadScript(script, 1 / hz);
      sim.setIntegrators({ rateRotational: integ });
      sim.runIC();
      const hs = P.map((p) => sim.handle(p));
      let bad: number | undefined, maxw = 0, n = 0;
      const t0 = performance.now();
      while (sim.run()) {
        n++;
        const w = Math.max(Math.abs(sim.get(hs[2])), Math.abs(sim.get(hs[3])), Math.abs(sim.get(hs[4])));
        if (!(w < 1e6) && bad === undefined) { bad = sim.simTime; break; }
        maxw = Math.max(maxw, w);
      }
      const us = ((performance.now() - t0) * 1000) / n;
      const v = hs.map((h) => sim.get(h));
      line += `${(bad === undefined ? "none" : bad.toFixed(3)).padStart(18)} ${maxw.toExponential(2).padStart(15)} ${v[0].toFixed(2).padStart(13)} ${v[1].toFixed(2).padStart(10)} ${v[5].toFixed(3).padStart(9)} ${v[6].toFixed(3).padStart(10)} ${us.toFixed(1).padStart(8)}`;
    } catch (e) { line += "FAILED: " + describeError(e); }
    console.log(line);
  }
}
