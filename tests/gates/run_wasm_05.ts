// Session 05 gates (GATES-05.md), measurements in our WebAssembly build. The procedures are in sim05.ts.
// usage: JSBSIM_VARIANT=<variant> [JSBSIM_BIN=<dir>] tsx tests/gates/run_wasm_05.ts <config> <hz> <part> [--models a,b]
//   part: landing | g8 | crash | probe | fast
// Output: out/gates05/<config>/<hz>/wasm/<run>.f64 + .json (raw rows). They are measured afterwards by
//   evaluate_05.py measure <dir> <prefix> <tag>   (tests/gates/run-05.sh does both).
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { BIN, ROOT_DIR, createSim, currentVariant, describeBuild } from "../../src/wasm.ts";
import { CONFIGS, G5, crash, fastFlight, forcedProbe, heliLanding, landing, releaseProbe, type Cfg } from "./sim05.ts";

const argv = process.argv.slice(2);
let models: string[] | null = null;
const mi = argv.indexOf("--models");
if (mi >= 0) { models = argv[mi + 1]!.split(","); argv.splice(mi, 2); }
const [name, hzArg, part] = argv as [string, string, string];
const hz = Number(hzArg);
const cfg: Cfg = CONFIGS[name];
if (!cfg) throw new Error(`unknown configuration ${name}`);
const reference = name.startsWith("ref05-");
const variant = currentVariant();
const infoPath = join(BIN, "build-info.json");
const info = existsSync(infoPath) ? JSON.parse(readFileSync(infoPath, "utf8")) : {};
if ((info.patchSet ?? "unknown") !== cfg.source) throw new Error(`configuration ${name} needs the '${cfg.source}' WebAssembly build, but ${BIN} is '${info.patchSet}'`);
const out = join(ROOT_DIR, "out/gates05", name, String(hz), "wasm");
mkdirSync(out, { recursive: true });
writeFileSync(join(out, "info.json"), JSON.stringify({ config: name, hz, properties: cfg.properties, build: describeBuild(variant), patchSet: info.patchSet, patches: info.patches ?? [] }, null, 1));
console.log(`# session 05 gates, wasm, ${name} at ${hz} Hz, ${part}${models ? " " + models.join(",") : ""}: ${describeBuild(variant)}`);

const sim = await createSim({ variant });
type Job = [string, (path: string) => void];
const jobs: Job[] = [];
const casesFor = (m: string): string[] => G5.G2d.cases_by_aircraft?.[m] ?? G5.G2d.cases;
if (part === "landing") {
  for (const m of models ?? G5.G2d.aircraft) for (const c of casesFor(m))
    jobs.push([`landing-${m}-${c}`, (p) => (m === "ah1s" ? heliLanding(sim, c, hz, cfg, p) : landing(sim, m, c, hz, cfg, p))]);
} else if (part === "g8") {
  for (const m of models ?? G5.G8.aircraft) for (const c of G5.G8.cases) jobs.push([`g8-${m}-${c}`, (p) => landing(sim, m, c, hz, cfg, p)]);
  if (!reference && !models) jobs.push(["g8-release", (p) => releaseProbe(sim, hz, cfg, p)]);
} else if (part === "crash") {
  for (const m of models ?? Object.keys(G5.G3d.aircraft)) for (const sc of Object.keys(G5.G3d.scenarios)) for (let run = 0; run < G5.G3d.draws.length; run++)
    jobs.push([`crash-${m}-${sc}-${run}`, (p) => crash(sim, m, sc, run, hz, cfg, p)]);
} else if (part === "probe") {
  for (const c of Object.keys(G5.G7.probe_cases)) for (const where of G5.G7.where) jobs.push([`probe-${c}-${where}`, (p) => forcedProbe(sim, c, where, hz, cfg, p)]);
} else if (part === "fast") {
  for (const m of models ?? Object.keys(G5.G7.fast_points)) jobs.push([`fast-${m}`, (p) => fastFlight(sim, m, hz, cfg, p)]);
} else throw new Error(`unknown part ${part}`);

for (const [stem, fn] of jobs) {
  let status = "ok";
  try { fn(join(out, `${stem}.f64`)); } catch (e) {
    // recorded; the judge counts it as a failure
    status = "error";
    writeFileSync(join(out, `${stem}.json`), JSON.stringify({ file: stem, kind: "error", error: e instanceof Error ? `${e.name}: ${e.message}` : String(e) }));
  }
  console.log(stem, status);
}
sim.delete();
