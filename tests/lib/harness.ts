// Shared by the test files: load the WebAssembly builds with the data mounted, and write result files.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import type { FdmModule, LogRecord } from "../../ts/core.ts";
import { REPO_ROOT, type Variant, loadVariant, mountDir, mountJsbsimData } from "../../ts/node.ts";
import { prepareFixtures } from "./fixtures.ts";

export const RESULTS_DIR = join(REPO_ROOT, "results");

export interface Loaded {
  variant: Variant;
  module: FdmModule;
  logs: LogRecord[];
}

/** A fresh module with jsbsim-data at /data and the fixtures at /fix. */
export async function loadWithData(variant: Variant): Promise<Loaded> {
  const logs: LogRecord[] = [];
  const module = await loadVariant(variant, { onLog: (r) => logs.push(r) });
  mountJsbsimData(module);
  mountDir(module, prepareFixtures(), "/fix");
  return { variant, module, logs };
}

/** Collects lines and writes them to results/<name>.txt; also echoes to the console. */
export class Report {
  lines: string[] = [];
  name: string;
  constructor(name: string) {
    this.name = name;
  }
  line(text = ""): void {
    this.lines.push(text);
    console.log(text);
  }
  save(): void {
    mkdirSync(RESULTS_DIR, { recursive: true });
    writeFileSync(join(RESULTS_DIR, `${this.name}.txt`), `${this.lines.join("\n")}\n`);
  }
}
