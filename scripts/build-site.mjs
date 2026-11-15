// Build the static iPhone test page into ./site (git-ignored), from web/, src/, wasm/bin/ and jsbsim-data/.
import { mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync, copyFileSync } from "node:fs";
import { join, relative } from "node:path";
import { build } from "esbuild";

const ROOT = new URL("..", import.meta.url).pathname;
const SITE = join(ROOT, "site");
const DATA = join(ROOT, "jsbsim-data");
const BIN = join(ROOT, "wasm/bin");
const info = JSON.parse(readFileSync(join(BIN, "build-info.json"), "utf8"));

rmSync(SITE, { recursive: true, force: true });
mkdirSync(SITE, { recursive: true });

// All aircraft/engine/systems files as one JSON bundle (path -> text).
const data = {};
const walk = (d) => {
  for (const name of readdirSync(d)) {
    const p = join(d, name);
    if (statSync(p).isDirectory()) walk(p);
    else data[relative(DATA, p)] = readFileSync(p, "utf8");
  }
};
for (const d of ["aircraft", "engine", "systems"]) walk(join(DATA, d));
writeFileSync(join(SITE, "data.json"), JSON.stringify(data));
const aircraft = readdirSync(join(DATA, "aircraft")).filter((d) => statSync(join(DATA, "aircraft", d)).isDirectory() && !/^c172p_ext\d+$/.test(d)).sort(); // skip test-generated (git-ignored) copies

const BUILD = { ...info, siteBuilt: new Date().toISOString(), aircraft };
await build({
  entryPoints: [join(ROOT, "web/app.ts")],
  bundle: true, format: "esm", target: "es2022", outfile: join(SITE, "app.js"),
  define: { BUILD: JSON.stringify(BUILD) },
  logLevel: "warning",
});
writeFileSync(join(SITE, "index.html"), readFileSync(join(ROOT, "web/index.html"), "utf8")
  .replaceAll("__BUILD_VERSION__", info.buildVersion).replaceAll("__BUILD_DATE__", info.buildDate)
  .replaceAll("__JSBSIM_TAG__", info.jsbsimTag));
for (const f of ["jsbsim.mjs", "jsbsim.wasm", "jsbsim-weh.mjs", "jsbsim-weh.wasm", "build-info.json"]) copyFileSync(join(BIN, f), join(SITE, f));
copyFileSync(join(DATA, "COPYING"), join(SITE, "COPYING.txt"));
writeFileSync(join(SITE, "NOTICE.txt"), `This test page runs our own WebAssembly build of JSBSim ${info.jsbsimTag}
(commit ${info.jsbsimCommit}, https://github.com/JSBSim-Team/jsbsim), compiled with Emscripten ${info.emscripten}.
JSBSim is licensed under the GNU Lesser General Public License v2.1 (COPYING.txt).
Build scripts and binding: https://github.com/135crewdog/FDM (wasm/, scripts/build-wasm.sh).
data.json holds JSBSim's aircraft, engine and systems files from ${info.jsbsimTag}, unmodified, with their licence headers.
The page adds in memory: an airborne f16 init file, c172x + 20 external forces, and two deliberately broken aircraft.
`);
console.log(`site built in ${SITE}: ${info.buildVersion}, ${Object.keys(data).length} data files, ${aircraft.length} aircraft`);
