// Node helpers for our WebAssembly JSBSim build: create an instance with the JSBSim data copied into
// its in-memory file system. The browser-safe wrapper is src/jsbsim.ts.
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { JSBSim, JSBSimError, type ModuleFactory, type Profile } from "./jsbsim.ts";

export { JSBSim, JSBSimError };
export const ROOT_DIR = new URL("../", import.meta.url).pathname;
/** JSBSim data root; JSBSIM_DATA overrides it (e.g. a modified copy under out/). */
export const DATA = process.env.JSBSIM_DATA ? resolve(process.env.JSBSIM_DATA) + "/" : new URL("../jsbsim-data/", import.meta.url).pathname;
/** Directory of the built files; JSBSIM_BIN overrides it (e.g. build/wasm-bin-unpatched/). */
export const BIN = process.env.JSBSIM_BIN ? resolve(process.env.JSBSIM_BIN) + "/" : new URL("../wasm/bin/", import.meta.url).pathname;

export type Variant = "jsbsim" | "jsbsim-weh";
const DATA_DIRS = ["aircraft", "engine", "systems", "scripts"];

/**
 * Create a JSBSim instance. By default copies aircraft/engine/systems/scripts into MEMFS.
 * Set JSBSIM_LOG=1 to echo JSBSim's console output.
 */
/** The variant createSim() uses when none is given: JSBSIM_VARIANT, else jsbsim-weh (-fwasm-exceptions, the default since the iPhone test in REPORT-02). */
export function currentVariant(): Variant {
  const v = process.env.JSBSIM_VARIANT ?? "jsbsim-weh";
  if (v !== "jsbsim" && v !== "jsbsim-weh") throw new Error(`JSBSIM_VARIANT must be jsbsim or jsbsim-weh, got ${v}`);
  return v;
}

/** One line that identifies the binary under test: variant, hash of the .wasm, build version, patches. */
export function describeBuild(variant: Variant = currentVariant()): string {
  const sha = createHash("sha256").update(readFileSync(join(BIN, `${variant}.wasm`))).digest("hex");
  const infoPath = join(BIN, "build-info.json");
  const info = existsSync(infoPath) ? JSON.parse(readFileSync(infoPath, "utf8")) : {};
  const patches = (info.patches ?? []).map((p: { file: string; sha256: string }) => `${p.file} ${p.sha256.slice(0, 12)}`).join(", ") || "none";
  return `wasm ${variant} sha256 ${sha.slice(0, 16)} (${info.buildVersion ?? "unknown build"}, patches: ${patches})`;
}

/** The profile createSim() uses when none is given: FDM_PROFILE, else "jsbsim". This Node helper serves the tests and
 *  the frozen gate runners, which compare with native JSBSim and set every integrator themselves, so it keeps
 *  JSBSim's own defaults. The game creates its simulation with JSBSim.create(), whose default is "fdm". */
export function currentProfile(): Profile {
  const p = process.env.FDM_PROFILE ?? "jsbsim";
  if (p !== "fdm" && p !== "jsbsim") throw new Error(`FDM_PROFILE must be fdm or jsbsim, got ${p}`);
  return p;
}

export async function createSim(opts: { variant?: Variant; dirs?: string[]; profile?: Profile } = {}): Promise<JSBSim> {
  const variant = opts.variant ?? currentVariant();
  const factory = (await import(join(BIN, `${variant}.mjs`))).default as ModuleFactory;
  const sim = await JSBSim.create({
    factory,
    profile: opts.profile ?? currentProfile(),
    moduleOptions: { wasmBinary: readFileSync(join(BIN, `${variant}.wasm`)) },
    echo: process.env.JSBSIM_LOG ? (l) => console.error(l) : undefined,
  });
  for (const d of opts.dirs ?? DATA_DIRS) copyTree(sim, join(DATA, d), d);
  return sim;
}

/** Copy a host directory into MEMFS at `dest` (relative to the JSBSim root). */
export function copyTree(sim: JSBSim, hostDir: string, dest: string): void {
  const walk = (d: string) => {
    for (const name of readdirSync(d)) {
      const p = join(d, name);
      if (statSync(p).isDirectory()) walk(p);
      else sim.writeFile(join(dest, relative(hostDir, p)), readFileSync(p));
    }
  };
  walk(hostDir);
}

export function describeError(e: unknown): string {
  return e instanceof Error ? `${e.name}: ${e.message}` : `non-Error thrown: ${String(e)}`;
}

export const LOG_PROPS = [
  "simulation/sim-time-sec",
  "position/h-sl-ft",
  "velocities/vtrue-kts",
  "aero/alpha-rad",
  "aero/beta-rad",
  "attitude/phi-rad",
  "attitude/theta-rad",
  "attitude/psi-rad",
  "velocities/p-rad_sec",
  "velocities/q-rad_sec",
  "velocities/r-rad_sec",
  "position/h-agl-ft",
  "gear/wow",
] as const;

export function sample(sim: JSBSim, props: readonly string[] = LOG_PROPS): number[] {
  return props.map((p) => sim.getProperty(p));
}

export function toCsv(props: readonly string[], rows: number[][]): string {
  return props.join(",") + "\n" + rows.map((r) => r.map((v) => v.toPrecision(17)).join(",")).join("\n") + "\n";
}
