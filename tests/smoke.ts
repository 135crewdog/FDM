// Quick smoke test of the build: version, load c172x, errors become Errors with messages.
import { createSim, describeError } from "../src/wasm.ts";
const sim = await createSim();
sim.setDebugLevel(0);
console.log("version:", sim.version);
for (const m of ["c172x", "f16", "no_such_aircraft"]) {
  try { sim.reset(); sim.loadModel(m); console.log(m, "loaded"); }
  catch (e) { console.log(m, "->", describeError(e)); }
}
sim.reset();
sim.loadScript("scripts/c1723.xml");
sim.runIC();
let n = 0; while (sim.run() && n < 1200) n++;
console.log("c1723 after", n, "steps: t =", sim.simTime.toFixed(3), "h =", sim.getProperty("position/h-sl-ft").toFixed(3));
try { sim.handle("no/such/prop"); } catch (e) { console.log("handle ->", describeError(e)); }
