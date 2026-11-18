// Builds the iPhone test page into test-page/ (committed; this folder is what gets copied to main).
//   page.js, worker.js      bundles of web/page.ts and ts/worker.ts
//   fdm-*.mjs, fdm-*.wasm   the committed binaries from dist-wasm/, unchanged
//   data.pack               the upstream files the page needs: aircraft/c172x, engine/, systems/
//   fix.pack                test fixtures: aircraft/c172x_ext20 (c172x + 20 forces), aircraft/broken_xml
// The build id is a hash of everything the page is made of; every asset URL carries it (?v=...), so a stale
// cached file cannot be mixed with a new one.
import { createHash } from "node:crypto";
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import * as esbuild from "esbuild";

import { prepareFixtures } from "../tests/lib/fixtures.ts";
import { buildPack } from "../ts/files.ts";
import { readDir } from "../ts/node.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "test-page");
const dist = join(root, "dist-wasm");
const info = JSON.parse(readFileSync(join(dist, "build-info.json"), "utf8"));

// Packs.
const data = readDir(join(root, "jsbsim-data", "aircraft", "c172x"), "aircraft/c172x/");
readDir(join(root, "jsbsim-data", "engine"), "engine/", data);
readDir(join(root, "jsbsim-data", "systems"), "systems/", data);
const fixDir = prepareFixtures();
const fix = readDir(join(fixDir, "aircraft", "c172x_ext20"), "aircraft/c172x_ext20/");
readDir(join(fixDir, "aircraft", "broken_xml"), "aircraft/broken_xml/", fix);
const dataPack = buildPack(data), fixPack = buildPack(fix);

const binaries = ["fdm-weh.mjs", "fdm-weh.wasm", "fdm-jseh.mjs", "fdm-jseh.wasm"];
const files = Object.fromEntries(Object.values(info.variants).flatMap((v) => Object.entries(v.files)));
const buildInfo = {
  jsbsim: `JSBSim ${info.jsbsim.tag}`, commit: info.jsbsim.commit,
  emscripten: `Emscripten ${info.emscripten.version}`, memoryBytes: info.memory.fixed_bytes, files,
};

// First pass with a placeholder id, to hash the bundles themselves; second pass with the real id.
async function bundle(id) {
  const common = { bundle: true, format: "esm", target: ["es2020", "safari15"], minify: false, write: false, logLevel: "warning",
    define: { __BUILD_ID__: JSON.stringify(id), __BUILD_INFO__: JSON.stringify(buildInfo) } };
  const page = await esbuild.build({ ...common, entryPoints: [join(root, "web", "page.ts")] });
  const worker = await esbuild.build({ ...common, entryPoints: [join(root, "ts", "worker.ts")] });
  return { page: page.outputFiles[0].contents, worker: worker.outputFiles[0].contents };
}
const draft = await bundle("0000000000");
const hash = createHash("sha256");
for (const part of [draft.page, draft.worker, dataPack, fixPack, readFileSync(join(root, "web", "index.html")), ...binaries.map((b) => readFileSync(join(dist, b)))]) hash.update(part);
const id = hash.digest("hex").slice(0, 10);
const final = await bundle(id);

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
writeFileSync(join(out, "page.js"), final.page);
writeFileSync(join(out, "worker.js"), final.worker);
writeFileSync(join(out, "data.pack"), dataPack);
writeFileSync(join(out, "fix.pack"), fixPack);
for (const b of binaries) cpSync(join(dist, b), join(out, b));
cpSync(join(dist, "build-info.json"), join(out, "build-info.json"));
// The date shown on the page is the date of the pinned JSBSim build inputs' newest commit time, not "now",
// so the same inputs always give the same page.
const date = new Date(info.source_date_epoch * 1000).toISOString().slice(0, 10);
const html = readFileSync(join(root, "web", "index.html"), "utf8")
  .replaceAll("__BUILD_ID__", id).replaceAll("__BUILD_DATE__", `binaries of ${date}`).replaceAll("__JSBSIM_TAG__", info.jsbsim.tag);
writeFileSync(join(out, "index.html"), html);
writeFileSync(join(out, "build-id.txt"), `${id}\n`);
// GitHub Pages: no Jekyll processing.
writeFileSync(join(out, ".nojekyll"), "");
console.log(`test-page/ built: id ${id}; data.pack ${dataPack.length} bytes (${data.size} files), fix.pack ${fixPack.length} bytes (${fix.size} files), page.js ${final.page.length}, worker.js ${final.worker.length}`);
