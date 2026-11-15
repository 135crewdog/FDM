// Diagnostic (not a gate): WebAssembly side of divergence_737.py.
// usage: JSBSIM_BIN=build/wasm-bin-unpatched JSBSIM_VARIANT=jsbsim-weh npx tsx tests/gates/diag/divergence_737.mts
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { ROOT_DIR, createSim, describeBuild } from "../../../src/wasm.ts";
const HERE = new URL(".", import.meta.url).pathname;
const G = JSON.parse(readFileSync(join(HERE, "../gates.json"), "utf8"));
const P: string[] = JSON.parse(readFileSync(join(HERE, "divergence_737_props.json"), "utf8"));
const sim = await createSim();
sim.setDebugLevel(0); sim.dt = 1 / 120; sim.loadModel("737"); sim.loadIC("reset00", true);
for (const [p, v] of Object.entries(G.scenarios.hard.ic)) sim.setProperty(p, v as number);
sim.setProperty("simulation/integrator/rate/rotational", 1); sim.runIC();
const rows = [P.map((p) => sim.getProperty(p))];
for (let k = 0; k < 120 * 8; k++) { sim.run(); rows.push(P.map((p) => sim.getProperty(p))); }
mkdirSync(join(ROOT_DIR, "out/gates/diag"), { recursive: true });
writeFileSync(join(ROOT_DIR, "out/gates/diag/737-hard-120.wasm.json"), JSON.stringify(rows));
console.log("wrote", rows.length, "rows;", describeBuild());
