// JSBSim WASM iPhone test. Plain ES module, no build step.
import { JSBSimSdk } from "./vendor/jsbsim-wasm/index.js";

const out = document.getElementById("out");
const statusEl = document.getElementById("status");
const lines = [];
const log = (s = "") => { lines.push(s); out.textContent = lines.join("\n"); };
const status = (s) => { statusEl.textContent = s; };
const tick = () => new Promise((r) => setTimeout(r, 0));

const MODULE_URL = new URL("./vendor/jsbsim-wasm/wasm/jsbsim_wasm.mjs", import.meta.url).href;
const WASM_URL = new URL("./vendor/jsbsim-wasm/wasm/jsbsim_wasm.wasm", import.meta.url).href;
const DATA = new URL("./data/", import.meta.url).href;
const FILES = [
  "aircraft/c172x/c172x.xml", "aircraft/c172x/c172ap.xml", "aircraft/c172x/reset01.xml",
  "aircraft/c172x_noap/c172x_noap.xml", "aircraft/c172x_noap/reset01.xml",
  "aircraft/c172x_noap_ext20/c172x_noap_ext20.xml", "aircraft/c172x_noap_ext20/reset01.xml",
  "aircraft/broken_xml/broken_xml.xml", "aircraft/broken_value/broken_value.xml",
  "systems/GNCUtilities.xml", "systems/Autopilot.xml",
  "engine/eng_io320.xml", "engine/prop_75in2f.xml",
];

let factory, wasmModule, fileData, memory, banner = "";

async function newSdk() {
  // Same factory as the package; we compile the wasm once and keep a handle on memory
  // so a C++ exception (which the package lets escape as a bare number) can be decoded.
  const moduleFactory = (opts) => factory({
    ...opts,
    instantiateWasm(imports, done) {
      WebAssembly.instantiate(wasmModule, imports).then((instance) => {
        memory = Object.values(instance.exports).find((x) => x instanceof WebAssembly.Memory);
        done(instance, wasmModule);
      });
      return {};
    },
  });
  const sdk = await JSBSimSdk.create({ moduleFactory, log: { console: false, stripAnsi: true,
    onStdout: (e) => { if (!banner && /Flight Dynamics Model/.test(e.message)) banner = e.message.trim(); } } });
  for (const [p, text] of fileData) sdk.writeDataFile(p, text);
  sdk.setDebugLevel(0);
  return sdk;
}

function describe(e) {
  if (typeof e === "number") {
    let msg = "(could not decode)";
    try {
      const u32 = new Uint32Array(memory.buffer), u8 = new Uint8Array(memory.buffer);
      const p = u32[(e + 4) >> 2]; let end = p;
      while (u8[end] !== 0 && end - p < 2000) end++;
      msg = new TextDecoder().decode(u8.subarray(p, end));
    } catch { /* ignore */ }
    return `uncaught C++ exception; JS received a bare number (${e}). Decoded message: ${msg.trim()}`;
  }
  return e && e.message ? `${e.name}: ${e.message}` : String(e);
}

function script(aircraft) {
  return `<?xml version="1.0"?>
<runscript name="timing ${aircraft}">
  <use aircraft="${aircraft}" initialize="reset01"/>
  <run start="0.0" end="100000" dt="0.008333333333333333"/>
</runscript>`;
}

// Deterministic force schedule (same as tests/extforce/schedule.ts)
function tri(k, period, phase) { const x = ((k + phase) % period) / period; return x < 0.5 ? 4 * x - 1 : 3 - 4 * x; }
function forceAt(i, k) {
  return [43.2 + 20 * tri(k, 700, 37 * i), 30 * tri(k, 900, 53 * i), 59.4 + 10 * tri(k, 500, 11 * i),
    0.3 * tri(k, 400, 7 * i), 0.2 * tri(k, 300, 13 * i), -1, 4 + 3 * tri(k, 250, 29 * i)];
}
const SUFFIX = ["location-x-in", "location-y-in", "location-z-in", "x", "y", "z", "magnitude"];
const NAMES = Array.from({ length: 20 }, (_, i) => SUFFIX.map((s) => `external_reactions/f${i}/${s}`));

function timerResolution() {
  let min = Infinity, a = performance.now();
  for (let i = 0; i < 200; i++) { let b; do { b = performance.now(); } while (b === a); min = Math.min(min, b - a); a = b; }
  return min;
}

async function timeCase(label, aircraft, dt, forces, steps = 3000, warmup = 300) {
  const sdk = await newSdk();
  sdk.writeDataFile(`scripts/t_${aircraft}.xml`, script(aircraft));
  if (!sdk.loadScript(`scripts/t_${aircraft}.xml`, dt) || !sdk.runIc()) throw new Error("load failed");
  const step = (k) => {
    if (forces) for (let i = 0; i < 20; i++) { const v = forceAt(i, k); for (let j = 0; j < 7; j++) sdk.setPropertyValue(NAMES[i][j], v[j]); }
    return sdk.run();
  };
  for (let k = 0; k < warmup; k++) step(k);
  const per = new Float64Array(steps);
  const t0 = performance.now();
  for (let k = 0; k < steps; k++) { const a = performance.now(); step(warmup + k); per[k] = performance.now() - a; }
  const total = performance.now() - t0;
  const sorted = Array.from(per).sort((a, b) => a - b);
  // Worst block of 25 consecutive steps, per step (less affected by coarse timers).
  let worstBlock = 0;
  for (let k = 0; k + 25 <= steps; k += 25) { let s = 0; for (let j = k; j < k + 25; j++) s += per[j]; worstBlock = Math.max(worstBlock, s / 25); }
  const alt = sdk.getPropertyValue("position/h-sl-ft"), kts = sdk.getPropertyValue("velocities/vtrue-kts");
  const ok = Number.isFinite(alt) && Number.isFinite(kts);
  const us = (ms) => (ms * 1000).toFixed(1).padStart(7);
  log(`${label.padEnd(30)} dt=1/${Math.round(1 / dt)}`.padEnd(42) +
    ` avg ${us(total / steps)} us  p99 ${us(sorted[Math.floor(steps * 0.99)])} us  worst ${us(sorted[steps - 1])} us  worst-25-block ${us(worstBlock)} us/step` +
    `  (${steps} steps; ${(steps * dt).toFixed(1)} s sim in ${total.toFixed(0)} ms; end alt ${alt.toFixed(0)} ft ${kts.toFixed(0)} kt${ok ? "" : " NOT FINITE"})`);
  await tick();
}

async function tryLoad(label, model) {
  const sdk = await newSdk();
  let result;
  try { result = `loadModel returned ${sdk.loadModel(model)}`; } catch (e) { result = `THREW: ${describe(e)}`; }
  log(`${label}: ${result}`);
  // Is the same instance still usable afterwards?
  try {
    sdk.writeDataFile("scripts/after.xml", script("c172x_noap"));
    const ok = sdk.loadScript("scripts/after.xml") && sdk.runIc();
    let n = 0; for (; n < 120 && sdk.run(); n++);
    log(`  same instance afterwards: load ${ok ? "ok" : "returned false"}, ran ${n} steps, alt ${sdk.getPropertyValue("position/h-sl-ft").toFixed(1)} ft`);
  } catch (e) { log(`  same instance afterwards: THREW: ${describe(e)}`); }
  await tick();
}

async function main() {
  lines.length = 0;
  document.getElementById("copy").disabled = true;
  document.getElementById("rerun").disabled = true;
  log(`JSBSim WASM test page — ${new Date().toISOString()}`);
  log(`User agent: ${navigator.userAgent}`);
  log(`Screen: ${screen.width}x${screen.height} @${devicePixelRatio}x; cores: ${navigator.hardwareConcurrency ?? "?"}; standalone PWA: ${matchMedia("(display-mode: standalone)").matches}`);
  log(`Timer resolution (performance.now): ${(timerResolution() * 1000).toFixed(1)} us`);
  try {
    status("Loading package…");
    const t0 = performance.now();
    factory = (await import(MODULE_URL)).default;
    wasmModule = await WebAssembly.compileStreaming(fetch(WASM_URL)).catch(async () => WebAssembly.compile(await (await fetch(WASM_URL)).arrayBuffer()));
    fileData = await Promise.all(FILES.map(async (f) => [f, await (await fetch(DATA + f)).text()]));
    await newSdk();
    log(`Package @0x62/jsbsim-wasm@__PKG_VERSION__ loaded in ${(performance.now() - t0).toFixed(0)} ms; JSBSim banner: "${banner}"`);
    log("");
    log("1) Load the unmodified c172x");
    await tryLoad("c172x", "c172x");
    log("");
    log("2) Deliberately broken aircraft files (error must be caught, page must keep working)");
    await tryLoad("broken_xml (malformed XML)", "broken_xml");
    await tryLoad("broken_value (text where a number is needed)", "broken_value");
    await tryLoad("missing aircraft", "does_not_exist");
    log("");
    log("3) Time per JSBSim step, as fast as possible, after 300 warm-up steps");
    log("   Aircraft: c172x_noap = c172x with its autopilot/guidance systems removed (they do not load in this package).");
    log("   Starts in the air (c172x reset01). 'p99'/'worst' are single steps, limited by the timer resolution above;\n   'worst-25-block' = slowest run of 25 consecutive steps, per step.");
    for (const [label, ac, forces] of [["c172x_noap", "c172x_noap", false], ["c172x_noap + 20 forces updated", "c172x_noap_ext20", true]]) {
      for (const dt of [1 / 120, 1 / 480, 1 / 1000]) {
        status(`Timing ${label} dt=1/${Math.round(1 / dt)}…`);
        await timeCase(label, ac, dt, forces);
      }
    }
    log("   (20 forces updated = 20 x 7 setPropertyValue calls by name before every step)");
    log("");
    log("Done. Page still responsive.");
    status("Done.");
  } catch (e) {
    log(`FATAL: ${describe(e)}`);
    status("Failed — see results.");
  }
  document.getElementById("copy").disabled = false;
  document.getElementById("rerun").disabled = false;
}

document.getElementById("copy").addEventListener("click", async () => {
  const text = lines.join("\n");
  try { await navigator.clipboard.writeText(text); status("Copied."); }
  catch {
    const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta);
    ta.select(); document.execCommand("copy"); ta.remove(); status("Copied (fallback).");
  }
});
document.getElementById("rerun").addEventListener("click", main);
window.addEventListener("error", (e) => log(`window error: ${e.message}`));
window.addEventListener("unhandledrejection", (e) => log(`unhandled rejection: ${describe(e.reason)}`));
main();
