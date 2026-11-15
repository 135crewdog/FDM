// NASA check case 02 (tumbling brick) in our WebAssembly build, on JSBSim v1.3.3's own files (no changes).
// Optional arg: rotational-rate integrator id (default JSBSim = 1, rectangular Euler; 5 = Adams-Bashforth 4).
// Logs the same quantities as check_cases/NASA_EOM_2015/scripts/Atmos_02.xml, at 10 Hz.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createSim, copyTree, DATA, describeError } from "../../src/wasm.ts";

const cols: [string, string, string][] = JSON.parse(readFileSync(new URL("./columns.json", import.meta.url), "utf8"));
const conv = (kind: string, v: number) =>
  kind === "deg" ? v * (180.0 / Math.PI) : kind === "yaw" ? ((v + 180.0) % 360.0) - 180 : v;

const rateInt = process.argv[2];
const outFile = rateInt ? `out/Atmos_02_wasm_rateint${rateInt}.csv` : "out/Atmos_02_wasm.csv";
const sim = await createSim({ dirs: [] });
copyTree(sim, DATA + "check_cases/NASA_EOM_2015/aircraft", "aircraft");
copyTree(sim, DATA + "check_cases/NASA_EOM_2015/scripts", "scripts");
sim.setDebugLevel(0);
const rows: string[] = [cols.map((c) => c[0]).join(",")];
const log = () => rows.push(cols.map(([, p, k]) => conv(k, sim.getProperty(p)).toPrecision(17)).join(","));
try {
  sim.loadScript("scripts/Atmos_02.xml");
  if (rateInt) sim.setIntegrators({ rateRotational: Number(rateInt) });
  sim.runIC();
  let k = 0;
  log();
  while (sim.run()) { k++; if (k % 10 === 0) log(); }
} catch (e) {
  console.log("FAILED:", describeError(e));
  process.exitCode = 2;
}
mkdirSync("out", { recursive: true });
writeFileSync(outFile, rows.join("\n") + "\n");
console.log(`wrote ${outFile} (${rows.length - 1} rows)`);
