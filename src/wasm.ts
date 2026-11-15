// Small helpers to run JSBSim-WASM headless in Node.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { createRequire } from "node:module";
import { JSBSimSdk } from "@0x62/jsbsim-wasm";

const require = createRequire(import.meta.url);
export const DATA = new URL("../jsbsim-data/", import.meta.url).pathname;

/** wasm memory of the most recently created module (to decode C++ exceptions). */
export let wasmMemory: WebAssembly.Memory | undefined;

export async function createSdk(): Promise<JSBSimSdk> {
  const modPath = require.resolve("@0x62/jsbsim-wasm/wasm/module");
  const wasmPath = require.resolve("@0x62/jsbsim-wasm/wasm/binary");
  const factory = (await import(modPath)).default;
  const wasmBytes = readFileSync(wasmPath);
  // Same factory as the package uses; we only add an instantiateWasm hook so we can see memory.
  const moduleFactory = (opts?: Record<string, unknown>) =>
    factory({
      ...opts,
      instantiateWasm(imports: WebAssembly.Imports, done: (i: WebAssembly.Instance, m: WebAssembly.Module) => void) {
        WebAssembly.instantiate(wasmBytes, imports).then(({ instance, module }) => {
          wasmMemory = Object.values(instance.exports).find((x) => x instanceof WebAssembly.Memory) as WebAssembly.Memory;
          done(instance, module);
        });
        return {};
      },
    });
  return JSBSimSdk.create({ moduleFactory, log: { console: !!process.env.JSBSIM_LOG, stripAnsi: true } });
}

/**
 * The package lets C++ exceptions escape as a bare number (pointer to the thrown object).
 * For std::runtime_error-derived exceptions (JSBSim's BaseException) libc++ stores
 * [vptr][const char* msg] — read the message from wasm memory. Best effort.
 */
export function describeError(e: unknown): string {
  if (typeof e === "number" && wasmMemory) {
    try {
      const u32 = new Uint32Array(wasmMemory.buffer);
      const msgPtr = u32[(e + 4) >> 2];
      const u8 = new Uint8Array(wasmMemory.buffer);
      let end = msgPtr;
      while (u8[end] !== 0 && end - msgPtr < 2000) end++;
      const text = new TextDecoder().decode(u8.subarray(msgPtr, end));
      return `C++ exception (ptr ${e}): ${text}`;
    } catch { /* fallthrough */ }
  }
  return e instanceof Error ? `${e.name}: ${e.message}` : `non-Error thrown: ${String(e)}`;
}

/** Copy a host directory into MEMFS at `dest` (relative to the runtime root). */
export function copyTree(sdk: JSBSimSdk, hostDir: string, dest: string): void {
  const walk = (d: string) => {
    for (const name of readdirSync(d)) {
      const p = join(d, name);
      if (statSync(p).isDirectory()) walk(p);
      else sdk.writeDataFile(join(dest, relative(hostDir, p)), readFileSync(p));
    }
  };
  walk(hostDir);
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
] as const;

export function sample(sdk: JSBSimSdk, props: readonly string[] = LOG_PROPS): number[] {
  return props.map((p) => sdk.getPropertyValue(p));
}

export function toCsv(props: readonly string[], rows: number[][]): string {
  return props.join(",") + "\n" + rows.map((r) => r.map((v) => v.toPrecision(17)).join(",")).join("\n") + "\n";
}
