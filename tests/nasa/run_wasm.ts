// NASA check case 02 (tumbling brick) in our WebAssembly build, on JSBSim v1.3.3's own files (no changes).
// Optional args: rotational-rate integrator id (default JSBSim = 1, rectangular Euler; 5 = Adams-Bashforth 4),
// and step rate in Hz (default: the script's 100 Hz).
// Logs the same quantities as check_cases/NASA_EOM_2015/scripts/Atmos_02.xml, at 10 Hz.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createSim, copyTree, DATA, describeError } from "../../src/wasm.ts";

const cols: [string, string, string][] = JSON.parse(readFileSync(new URL("./columns.json", import.meta.url), "utf8"));
const conv = (kind: string, v: number) =>
  kind === "deg" ? v * (180.0 / Math.PI) : kind === "yaw" ? ((v + 180.0) % 360.0) - 180 : v;

const rateInt = process.argv[2] && process.argv[2] !== "1" ? process.argv[2] : undefined;
const hz = process.argv[3] ? Number(process.argv[3]) : undefined;
const outFile = `out/Atmos_02_wasm${rateInt ? `_rateint${rateInt}` : ""}${hz ? `_${hz}hz` : ""}.csv`;
const sim = await createSim({ dirs: [] });
copyTree(sim, DATA + "check_cases/NASA_EOM_2015/aircraft", "aircraft");
copyTree(sim, DATA + "check_cases/NASA_EOM_2015/scripts", "scripts");
sim.setDebugLevel(0);
const rows: string[] = [cols.map((c) => c[0]).join(",")];
const log = () => rows.push(cols.map(([, p, k]) => conv(k, sim.getProperty(p)).toPrecision(17)).join(","));
try {
  sim.loadScript("scripts/Atmos_02.xml", hz ? 1 / hz : 0);
  if (rateInt) sim.setIntegrators({ rateRotational: Number(rateInt) });
  sim.runIC();
  let k = 0;
  log();
  // log every 0.1 s of simulated time (the NASA data are at 0.1 s)
  let next = 0.1;
  while (sim.run()) { k++; if (sim.simTime >= next - 1e-9) { log(); next = Math.round(sim.simTime * 10 + 1) / 10; } }
} catch (e) {
  console.log("FAILED:", describeError(e));
  process.exitCode = 2;
}
mkdirSync("out", { recursive: true });
writeFileSync(outFile, rows.join("\n") + "\n");
console.log(`wrote ${outFile} (${rows.length - 1} rows)`);
