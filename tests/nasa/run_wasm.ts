// NASA check case 02 (tumbling brick) in the WebAssembly package.
// Optional arg: rotational-rate integrator id (default JSBSim = 1, rectangular Euler; 5 = Adams-Bashforth 4).
// Logs the same quantities as check_cases/NASA_EOM_2015/scripts/Atmos_02.xml, at 10 Hz.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createSdk, copyTree, DATA, describeError } from "../../src/wasm.ts";

const cols: [string, string, string][] = JSON.parse(readFileSync(new URL("./columns.json", import.meta.url), "utf8"));
const conv = (kind: string, v: number) =>
  kind === "deg" ? v * (180.0 / Math.PI) : kind === "yaw" ? ((v + 180.0) % 360.0) - 180 : v;

const rateInt = process.argv[2];
const outFile = rateInt ? `out/Atmos_02_wasm_rateint${rateInt}.csv` : "out/Atmos_02_wasm.csv";
const sdk = await createSdk();
copyTree(sdk, DATA + "nasa-run/aircraft", "aircraft");
copyTree(sdk, DATA + "nasa-run/scripts", "scripts");
sdk.setDebugLevel(0);
const rows: string[] = [cols.map((c) => c[0]).join(",")];
const log = () => rows.push(cols.map(([, p, k]) => conv(k, sdk.getPropertyValue(p)).toPrecision(17)).join(","));
try {
  if (!sdk.loadScript("scripts/Atmos_02.xml")) throw new Error("load failed");
  if (rateInt) sdk.setPropertyValue("simulation/integrator/rate/rotational", Number(rateInt));
  if (!sdk.runIc()) throw new Error("runIc failed");
  let k = 0;
  log();
  while (sdk.run()) { k++; if (k % 10 === 0) log(); }
} catch (e) {
  console.log("FAILED:", describeError(e));
  process.exitCode = 2;
}
mkdirSync("out", { recursive: true });
writeFileSync(outFile, rows.join("\n") + "\n");
console.log(`wrote ${outFile} (${rows.length - 1} rows)`);
