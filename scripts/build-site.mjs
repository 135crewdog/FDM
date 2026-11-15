// Build the static test page into ./site (git-ignored). Needs ./jsbsim-data (scripts/fetch-jsbsim-data.sh).
// Only the few JSBSim data files the page needs are copied, unmodified except where noted.
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync, copyFileSync } from "node:fs";
import { dirname, join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const SITE = join(ROOT, "site");
const DATA = join(ROOT, "jsbsim-data");
const PKG = join(ROOT, "node_modules/@0x62/jsbsim-wasm");
const pkgVersion = JSON.parse(readFileSync(join(PKG, "package.json"), "utf8")).version;
const jsbsimRef = readFileSync(join(DATA, "REF"), "utf8").trim();

rmSync(SITE, { recursive: true, force: true });
mkdirSync(SITE, { recursive: true });
copyFileSync(join(ROOT, "web/index.html"), join(SITE, "index.html"));
writeFileSync(join(SITE, "app.js"), readFileSync(join(ROOT, "web/app.js"), "utf8").replace("__PKG_VERSION__", pkgVersion));

// The npm package (MIT SDK + LGPL-2.1 WebAssembly build of JSBSim), as published.
const V = join(SITE, "vendor/jsbsim-wasm");
mkdirSync(join(V, "wasm"), { recursive: true });
for (const f of ["index.js", "wasm/jsbsim_wasm.mjs", "wasm/jsbsim_wasm.wasm"]) copyFileSync(join(PKG, "dist", f), join(V, f));
for (const f of ["LICENSE", "README.md", "package.json"]) copyFileSync(join(PKG, f), join(V, f));

const put = (rel, text) => { mkdirSync(dirname(join(SITE, "data", rel)), { recursive: true }); writeFileSync(join(SITE, "data", rel), text); };
const src = (rel) => readFileSync(join(DATA, rel), "utf8");

// Unmodified JSBSim files needed to load c172x.
for (const f of ["aircraft/c172x/c172x.xml", "aircraft/c172x/c172ap.xml", "aircraft/c172x/reset01.xml",
  "systems/GNCUtilities.xml", "systems/Autopilot.xml", "engine/eng_io320.xml", "engine/prop_75in2f.xml"]) put(f, src(f));

// Modified copies of c172x (GPL: modifications are stated in the file).
const c172x = src("aircraft/c172x/c172x.xml");
const AP_STUB = `
    <!-- autopilot removed; its outputs read by the flight controls are held at 0 (autopilot off) -->
    <system name="autopilot-stub">
      <property value="0"> ap/elevator_cmd </property>
      <property value="0"> ap/aileron_cmd </property>
      <property value="0"> ap/roll-cmd-norm-output </property>
    </system>
`;
const noap = c172x.replace(/\s*<system file="GNCUtilities"\/>\s*<system file="Autopilot">[\s\S]*?<\/system>\s*<autopilot file="c172ap"\/>/, AP_STUB);
if (noap === c172x) throw new Error("c172x autopilot block not found");
const note = (what) => `\n<!-- MODIFIED for the FDM repository's JSBSim-WASM test page (${new Date().toISOString().slice(0, 10)}):\n     ${what}\n     Original: JSBSim aircraft/c172x/c172x.xml at commit ${jsbsimRef}. -->\n`;
const withNote = (xml, what) => xml.replace(/(<\?xml[^>]*\?>)/, `$1${note(what)}`);
put("aircraft/c172x_noap/c172x_noap.xml", withNote(noap, "removed the GNCUtilities and Autopilot systems and the c172ap autopilot, and hold the three ap/* outputs the flight controls read at 0 (the removed files use property names where JSBSim first tries to parse a number, which needs C++ exceptions that this WASM build cannot catch)."));
put("aircraft/c172x_noap/reset01.xml", src("aircraft/c172x/reset01.xml"));
const forces = Array.from({ length: 20 }, (_, i) => `
    <force name="f${i}" frame="BODY">
      <location unit="IN"> <x> 43.2 </x> <y> 0 </y> <z> 59.4 </z> </location>
      <direction> <x> 0 </x> <y> 0 </y> <z> -1 </z> </direction>
    </force>`).join("");
put("aircraft/c172x_noap_ext20/c172x_noap_ext20.xml", withNote(noap.replace("</fdm_config>", `  <external_reactions>${forces}\n  </external_reactions>\n</fdm_config>`),
  "as c172x_noap, plus 20 external forces (external_reactions) controlled at run time through properties."));
put("aircraft/c172x_noap_ext20/reset01.xml", src("aircraft/c172x/reset01.xml"));

// Our own deliberately broken aircraft files.
put("aircraft/broken_xml/broken_xml.xml", `<?xml version="1.0"?>\n<fdm_config name="broken" version="2.0" release="ALPHA">\n  <metrics>\n    <wingarea unit="FT2"> 174 </wingarea>\n  <!-- metrics never closed, file truncated -->\n`);
put("aircraft/broken_value/broken_value.xml", `<?xml version="1.0"?>
<fdm_config name="broken_value" version="2.0" release="ALPHA">
  <metrics>
    <wingarea unit="FT2"> not-a-number </wingarea>
    <wingspan unit="FT"> 36 </wingspan>
    <chord unit="FT"> 4.9 </chord>
    <location name="AERORP" unit="IN"> <x> 43 </x> <y> 0 </y> <z> 59 </z> </location>
  </metrics>
  <mass_balance> <ixx unit="SLUG*FT2"> 948 </ixx> <iyy unit="SLUG*FT2"> 1346 </iyy> <izz unit="SLUG*FT2"> 1967 </izz>
    <emptywt unit="LBS"> 1500 </emptywt> <location name="CG" unit="IN"> <x> 41 </x> <y> 0 </y> <z> 36 </z> </location> </mass_balance>
  <ground_reactions/> <propulsion/> <flight_control name="none"/> <aerodynamics/>
</fdm_config>
`);

writeFileSync(join(SITE, "NOTICE.txt"), `This test page uses:

- @0x62/jsbsim-wasm ${pkgVersion} (https://www.npmjs.com/package/@0x62/jsbsim-wasm, source https://github.com/0x62/jsbsim-wasm).
  The SDK is MIT licensed (vendor/jsbsim-wasm/LICENSE). Its WebAssembly build (vendor/jsbsim-wasm/wasm/)
  contains JSBSim, licensed under the GNU Lesser General Public License v2.1.
  JSBSim source: https://github.com/JSBSim-Team/jsbsim (this build: commit 1a2e114d79af2430db02a4f7a4a85328cdc5d403
  plus the package's patches/jsbsim-emscripten-compat.patch).

- JSBSim aircraft/engine/systems data files under data/, from https://github.com/JSBSim-Team/jsbsim
  at commit ${jsbsimRef}, with their licence headers intact. c172x is GPL (see its <license> element).
  data/aircraft/c172x_noap* are modified copies; the change is described at the top of each file.
  data/aircraft/broken_* are our own deliberately broken test files.
`);
console.log(`site built in ${SITE} (package ${pkgVersion}, data ${jsbsimRef})`);
