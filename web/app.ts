// iPhone test page for our own WebAssembly build of JSBSim (session 02).
// Bundled by scripts/build-site.mjs (esbuild) into site/app.js. Shares code with the Node tests.
import { JSBSim, JSBSimError, type ModuleFactory } from "../src/jsbsim.ts";
import { tryLoad, withForces, timingScript, timeRun, type ForceMethod } from "../src/checks.ts";

declare const BUILD: {
  buildVersion: string; buildDate: string; jsbsimTag: string; jsbsimCommit: string; emscripten: string;
  siteBuilt: string; aircraft: string[];
};

const out = document.getElementById("out")!;
const statusEl = document.getElementById("status")!;
const lines: string[] = [];
const log = (s = "") => { lines.push(s); out.textContent = lines.join("\n"); };
const status = (s: string) => { statusEl.textContent = s; };
const tick = () => new Promise((r) => setTimeout(r, 0));
const describe = (e: unknown) => (e instanceof Error ? `${e.name}: ${e.message}` : `non-Error thrown: ${String(e)}`);
const V = encodeURIComponent(BUILD.buildVersion);

let dataFiles: Record<string, string> | undefined;
async function getData() {
  if (!dataFiles) dataFiles = await (await fetch(`data.json?v=${V}`)).json();
  return dataFiles!;
}

const VARIANTS = {
  "jsbsim": "-fexceptions (default)",
  "jsbsim-weh": "-fwasm-exceptions",
} as const;
type Variant = keyof typeof VARIANTS;

async function createSim(variant: Variant): Promise<JSBSim> {
  const url = new URL(`./${variant}.mjs?v=${V}`, location.href).href; // a variable, so the bundler leaves it alone
  const factory = (await import(url)).default as ModuleFactory;
  const sim = await JSBSim.create({
    factory,
    moduleOptions: { locateFile: (p: string) => `${p}?v=${V}` },
  });
  const data = await getData();
  for (const [p, text] of Object.entries(data)) sim.writeFile(p, text);
  // Our additions (in memory only; JSBSim's files are not changed):
  // an airborne initial condition for the f16 (its only init file starts on the runway),
  // and copies of c172x / f16 with 20 runtime external forces.
  sim.writeFile("aircraft/f16/fdm_air01.xml", `<?xml version="1.0"?>
<initialize name="fdm_air01">
  <vt unit="KTS"> 400.0 </vt> <latitude unit="DEG"> 47.0 </latitude> <longitude unit="DEG"> 122.0 </longitude>
  <phi unit="DEG"> 0.0 </phi> <theta unit="DEG"> 2.0 </theta> <psi unit="DEG"> 0.0 </psi>
  <altitude unit="FT"> 10000.0 </altitude> <running> -1 </running>
</initialize>`);
  sim.writeFile("aircraft/c172x_ext20/c172x_ext20.xml", withForces(data["aircraft/c172x/c172x.xml"], 20));
  sim.writeFile("aircraft/c172x_ext20/reset01.xml", data["aircraft/c172x/reset01.xml"]);
  for (const f of ["c172ap.xml"]) sim.writeFile(`aircraft/c172x_ext20/${f}`, data[`aircraft/c172x/${f}`]);
  sim.writeFile("aircraft/broken_xml/broken_xml.xml", `<?xml version="1.0"?>\n<fdm_config name="broken" version="2.0" release="ALPHA">\n  <metrics>\n    <wingarea unit="FT2"> 174 </wingarea>\n`);
  sim.writeFile("aircraft/broken_value/broken_value.xml", data["aircraft/c172x/c172x.xml"].replace(/<wingarea unit="FT2">[^<]*<\/wingarea>/, '<wingarea unit="FT2"> not-a-number </wingarea>'));
  for (const [name, ac, init] of [["c172x", "c172x", "reset01"], ["f16", "f16", "fdm_air01"], ["c172x_ext20", "c172x_ext20", "reset01"]])
    sim.writeFile(`scripts/t_${name}.xml`, timingScript(ac, init, 1 / 120));
  return sim;
}

function timerResolution(): number {
  let min = Infinity, a = performance.now();
  for (let i = 0; i < 200; i++) { let b; do { b = performance.now(); } while (b === a); min = Math.min(min, b - a); a = b; }
  return min;
}

let running = false;
async function run(variant: Variant) {
  if (running) return;
  running = true;
  for (const b of document.querySelectorAll("button")) (b as HTMLButtonElement).disabled = true;
  lines.length = 0;
  log(`FDM JSBSim WebAssembly test — build ${BUILD.buildVersion} (built ${BUILD.buildDate})`);
  log(`Variant: ${variant}.wasm, ${VARIANTS[variant]}; JSBSim ${BUILD.jsbsimTag} (${BUILD.jsbsimCommit.slice(0, 10)}); Emscripten ${BUILD.emscripten}`);
  log(`Run at ${new Date().toISOString()}`);
  log(`User agent: ${navigator.userAgent}`);
  log(`Screen: ${screen.width}x${screen.height} @${devicePixelRatio}x; cores: ${navigator.hardwareConcurrency ?? "?"}; standalone PWA: ${matchMedia("(display-mode: standalone)").matches}`);
  log(`Timer resolution (performance.now): ${(timerResolution() * 1000).toFixed(1)} us`);
  try {
    status("Loading…");
    let t0 = performance.now();
    await getData();
    const tData = performance.now() - t0;
    t0 = performance.now();
    let sim = await createSim(variant);
    log(`Data (${Object.keys(dataFiles!).length} files) ${tData.toFixed(0)} ms; module + files into memory ${(performance.now() - t0).toFixed(0)} ms; JSBSim reports: ${sim.version}`);

    log("");
    log(`1) Load matrix: loadModel on every aircraft folder (${BUILD.aircraft.length}). Native JSBSim 1.3.3 loads all but LM and blank.`);
    let nOk = 0;
    for (const name of BUILD.aircraft) {
      status(`Loading ${name}…`);
      const r = tryLoad(sim, name);
      if (r.ok) nOk++;
      log(`   ${r.ok ? "ok  " : "FAIL"} ${name.padEnd(16)} ${r.ms.toFixed(0).padStart(5)} ms${r.ok ? "" : "  " + r.msg.slice(0, 160)}`);
      if (!r.clean) sim = await createSim(variant);
      if (BUILD.aircraft.indexOf(name) % 8 === 7) await tick();
    }
    const expected = BUILD.aircraft.filter((n) => n !== "LM" && n !== "blank").length;
    log(`   ${nOk}/${BUILD.aircraft.length} load (expected ${expected}): ${nOk === expected ? "PASS" : "DIFFERENT FROM NATIVE"}`);

    log("");
    log("2) Errors are JavaScript Errors with JSBSim's message, and the instance keeps working");
    for (const [label, model] of [["malformed XML", "broken_xml"], ["text where a number belongs", "broken_value"], ["missing aircraft", "does_not_exist"]]) {
      const r = tryLoad(sim, model);
      log(`   ${label}: ${r.ok ? "loaded (unexpected)" : (r.clean ? "JSBSimError: " : "") + r.msg.slice(0, 200)}`);
    }
    try {
      sim.reset(); sim.setDebugLevel(0); sim.loadScript("scripts/t_c172x.xml"); sim.runIC();
      const n = sim.runSteps(120);
      log(`   afterwards, same instance: c172x ran ${n} steps, alt ${sim.getProperty("position/h-sl-ft").toFixed(1)} ft`);
    } catch (e) { log(`   afterwards: ${describe(e)}`); }
    await tick();

    log("");
    log("3) Time per step (3000 steps after 300 warm-up; whole batch timed). Unmodified c172x (reset01, in the air)");
    log("   and f16 (our airborne init file: 10000 ft, 400 kt, engine running).");
    const us = (x: number) => x.toFixed(1).padStart(6);
    for (const [label, script] of [["c172x", "scripts/t_c172x.xml"], ["f16", "scripts/t_f16.xml"]]) {
      for (const dt of [1 / 120, 1 / 480, 1 / 1000]) {
        status(`Timing ${label} 1/${Math.round(1 / dt)}…`);
        const r = timeRun(sim, script, label, dt, "none");
        log(`   ${label.padEnd(6)} dt=1/${String(Math.round(1 / dt)).padEnd(5)} ${us(r.usPerStep)} us/step  (${r.totalMs.toFixed(0)} ms for ${(r.steps * dt).toFixed(1)} s sim; end ${r.altFt.toFixed(0)} ft ${r.kts.toFixed(0)} kt${Number.isFinite(r.altFt) ? "" : " NOT FINITE"})`);
        await tick();
      }
    }

    log("");
    log("4) 20 external forces (c172x + 20 runtime forces), 7 values each written before every step:");
    log("   none = forces defined but not updated; name = 140 setProperty by name; handle = 140 writes by cached handle;");
    log("   bulk = one Float64Array of 140 values per step.");
    const methods: ForceMethod[] = ["none", "name", "handle", "bulk"];
    for (const dt of [1 / 120, 1 / 480, 1 / 1000]) {
      const parts: string[] = [];
      const ends: string[] = [];
      for (const m of methods) {
        status(`Forces ${m} 1/${Math.round(1 / dt)}…`);
        const r = timeRun(sim, "scripts/t_c172x_ext20.xml", "c172x_ext20", dt, m);
        parts.push(`${m} ${us(r.usPerStep)}`);
        if (m !== "none") ends.push(`${r.altFt.toFixed(6)}/${r.kts.toFixed(6)}`);
        await tick();
      }
      const same = ends.every((e) => e === ends[0]);
      log(`   dt=1/${String(Math.round(1 / dt)).padEnd(5)} ${parts.join("  ")}  us/step   (name/handle/bulk same end state: ${same ? "yes" : "NO " + ends.join(" ")})`);
    }
    log("");
    log("Done. Page still responsive.");
    status("Done. Tap 'Copy results' and paste them back.");
    sim.delete();
  } catch (e) {
    log(`FATAL: ${describe(e)}${e instanceof JSBSimError ? "" : " (not a JSBSimError)"}`);
    status("Failed — see results.");
  }
  for (const b of document.querySelectorAll("button")) (b as HTMLButtonElement).disabled = false;
  running = false;
}

document.getElementById("version")!.textContent = `Build ${BUILD.buildVersion} · built ${BUILD.buildDate}`;
document.getElementById("copy")!.addEventListener("click", async () => {
  const text = lines.join("\n");
  try { await navigator.clipboard.writeText(text); status("Copied."); }
  catch {
    const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta);
    ta.select(); document.execCommand("copy"); ta.remove(); status("Copied (fallback).");
  }
});
document.getElementById("run-js")!.addEventListener("click", () => run("jsbsim"));
document.getElementById("run-weh")!.addEventListener("click", () => run("jsbsim-weh"));
window.addEventListener("error", (e) => log(`window error: ${e.message}`));
window.addEventListener("unhandledrejection", (e) => log(`unhandled rejection: ${describe(e.reason)}`));
run("jsbsim");
