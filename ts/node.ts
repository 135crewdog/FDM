// Node-only helpers (tests and tools): load a committed WebAssembly build and copy folders from disk into it.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { type FdmFactory, type FdmModule, type FdmModuleOptions, loadFdmModule } from "./core.ts";
import { type FileSet, writeFiles } from "./files.ts";

export const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
export type Variant = "weh" | "jseh";
export const VARIANTS: Variant[] = ["weh", "jseh"];

/** Loads dist-wasm/fdm-<variant>. */
export async function loadVariant(variant: Variant, options: FdmModuleOptions = {}): Promise<FdmModule> {
  const dir = join(REPO_ROOT, "dist-wasm");
  const factory = (await import(pathToFileURL(join(dir, `fdm-${variant}.mjs`)).href)).default as FdmFactory;
  return loadFdmModule(factory, { ...options, wasmBinary: readFileSync(join(dir, `fdm-${variant}.wasm`)) });
}

/** Reads a folder from disk into a FileSet (paths relative to the folder, "/" separators). */
export function readDir(dir: string, prefix = "", into: FileSet = new Map()): FileSet {
  for (const name of readdirSync(dir).sort()) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) readDir(full, `${prefix}${name}/`, into);
    else into.set(`${prefix}${name}`, readFileSync(full));
  }
  return into;
}

/** Copies a folder from disk to `mountPoint` inside the module. */
export function mountDir(module: FdmModule, dir: string, mountPoint: string): void {
  writeFiles(module, mountPoint, readDir(dir));
}

/** Copies jsbsim-data/ to /data: the layout every test uses. */
export function mountJsbsimData(module: FdmModule): void {
  mountDir(module, join(REPO_ROOT, "jsbsim-data"), "/data");
}
