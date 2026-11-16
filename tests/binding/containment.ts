// Crash containment in the wrapper (session 05, step 5): tests.
// usage: JSBSIM_VARIANT=jsbsim-weh npx tsx tests/binding/containment.ts [unit] [crash]     (exit code 1 on a failure)
//   unit   every halt reason, what a halt leaves behind, and what happens when a step throws
//   crash  the 20 crash cases of G3d (gates-05.json), 5 runs each, stepped the way a game steps (16 steps per
//          frame through the bulk interface) with containment on, for the floor's integrators, c3-ab4 and
//          c2-mid, each with and without the strut limits of patch 0004, at 480, 960 and 1200 Hz
// Rule being tested: with containment on, no state that breaks a limit is ever published, the game is told why
// the simulation stopped, and nothing but a JSBSimError is ever thrown.
import { readFileSync } from "node:fs";
import { createSim, JSBSimError, describeBuild } from "../../src/wasm.ts";
import { CONTAINMENT_DEFAULTS, type JSBSim } from "../../src/jsbsim.ts";

const variant = process.env.JSBSIM_VARIANT ?? "jsbsim-weh";
const want = process.argv.slice(2).length ? process.argv.slice(2) : ["unit", "crash"];
let failed = 0, passed = 0;
function report(name: string, ok: boolean, detail = "") {
  ok ? passed++ : failed++;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  [" + detail + "]" : ""}`);
}
const short = (s: string) => (s.length > 120 ? s.slice(0, 120) + "..." : s);
console.log(`# Crash containment, ${describeBuild(variant as "jsbsim" | "jsbsim-weh")}`);
const sim: JSBSim = await createSim({ variant: variant as "jsbsim" | "jsbsim-weh" });
const fresh = (model: string, ic: string, hz: number, props: Record<string, number> = {}) => {
  sim.reset(); sim.setDebugLevel(0); sim.dt = 1 / hz; sim.loadModel(model); sim.loadIC(ic, true);
  for (const [p, v] of Object.entries(props)) sim.setProperty(p, v);
};

if (want.includes("unit")) {
  console.log("## 1. Off by default; on, a healthy simulation is not disturbed");
  fresh("c172x", "reset00", 480); sim.runIC();
  report("no halt before containment is switched on", sim.halted === null);
  sim.setContainment({});
  const n = sim.runSteps(960);
  report("c172x standing on its gear for 2 s with the default limits: 960 steps, not halted", n === 960 && sim.halted === null, `${n} steps`);
  fresh("c172x", "reset00", 480, { "ic/h-agl-ft": 3000, "ic/vc-kts": 90 }); sim.runIC();
  report("containment persists over reset(); c172x flying for 2 s: not halted", sim.runSteps(960) === 960 && sim.halted === null);

  console.log("## 2. Every reason halts, is reported, and refuses further steps");
  const cases: [string, string, Record<string, number>, object][] = [
    ["runaway-rate", "c172x rolling at 1 rad/s with a limit of 0.5 rad/s", { "ic/h-agl-ft": 3000, "ic/vc-kts": 90, "ic/p-rad_sec": 1 }, { maxBodyRateRadS: 0.5 }],
    ["below-surface", "c172x at 500 ft with the height limit at 1000 ft", { "ic/h-agl-ft": 500, "ic/vc-kts": 90 }, { minCgHeightAglFt: 1000 }],
    ["tipped-over", "c172x standing (0.6 deg nose up) with a tilt limit of 0.1 deg", {}, { maxTiltOnGroundDeg: 0.1 }],
    ["ground-force", "c172x standing (the ground carries 1 weight) with a limit of 0.5 weights", {}, { maxGroundForceWeights: 0.5 }],
  ];
  for (const [reason, what, ic, limits] of cases) {
    fresh("c172x", "reset00", 480, ic); sim.runIC();
    sim.setContainment(limits);
    sim.bindOutputs(["simulation/sim-time-sec", "position/h-agl-ft", "velocities/p-rad_sec"]);
    sim.readOutputs();
    const t0 = sim.outputs[0]!;
    const steps = sim.step(100);
    const h = sim.halted;
    report(`${reason}: ${what}`, h !== null && h.reason === reason && steps < 100, h ? `${h.reason} after ${steps} accepted steps: ${short(h.detail)}` : `not halted, ${steps} steps`);
    report(`  ... outputs hold the last accepted state (time ${t0} + ${steps} steps), not the refused one`, h !== null && Math.abs(sim.outputs[0]! - (t0 + steps / 480)) < 1e-9 && h.simTime > sim.outputs[0]!,
      `outputs time ${sim.outputs[0]}, refused step at ${h?.simTime}`);
    let threw = "";
    try { sim.run(); } catch (e) { threw = e instanceof JSBSimError ? e.message : "not a JSBSimError"; }
    report("  ... the next run() throws a JSBSimError that says the simulation is halted", /halted/.test(threw), short(threw));
    let threw2 = "";
    try { sim.step(1); } catch (e) { threw2 = e instanceof JSBSimError ? e.message : "not a JSBSimError"; }
    report("  ... and so does step()", /halted/.test(threw2));
    report("  ... properties can still be read (for drawing or logging)", Number.isFinite(sim.getProperty("position/h-agl-ft")));
  }
  sim.setContainment(null);
  fresh("c172x", "reset00", 480); sim.runIC();
  report("reset() clears the halt; with containment off the same start runs", sim.halted === null && sim.runSteps(100) === 100);
  let bad = "";
  try { sim.setContainment({ maxBodyRateRadS: "fast" as unknown as number }); } catch (e) { bad = e instanceof JSBSimError ? e.message : "not a JSBSimError"; }
  report("setContainment refuses a limit that is not a number", /maxBodyRateRadS/.test(bad), short(bad));
  let argErr = "";
  try { sim.runSteps(-1); } catch (e) { argErr = e instanceof JSBSimError ? e.message : "x"; }
  report("a bad argument to runSteps is an error of the call and halts nothing", /step/.test(argErr) && sim.halted === null && sim.runSteps(5) === 5);

  console.log("## 3. A step that throws halts the simulation (containment on or off)");
  // A script event writes an integrator id that JSBSim's own integration code refuses with an exception: the only
  // way past the binding's validation, and the same path a failed Newton solve of the midpoint scheme takes.
  const script = `<runscript name="throwing step"><use aircraft="c172x" initialize="reset00"/><run start="0" end="10" dt="0.002">
    <event name="bad integrator"><condition>simulation/sim-time-sec ge 0.1</condition><set name="simulation/integrator/rate/translational" value="7"/></event></run></runscript>`;
  for (const on of [false, true]) {
    sim.reset(); sim.setDebugLevel(0);
    sim.setContainment(on ? {} : null);
    sim.writeFile("scripts/containment-throw.xml", script);
    sim.loadScript("scripts/containment-throw.xml"); sim.runIC();
    sim.bindOutputs(["simulation/sim-time-sec", "position/h-agl-ft"]);
    let steps = 0, err = "", kind = "";
    try { for (let k = 0; k < 200; k++) { sim.step(1); steps++; } } catch (e) { kind = e instanceof JSBSimError ? "JSBSimError" : "other"; err = e instanceof Error ? e.message : String(e); }
    const h = sim.halted;
    report(`containment ${on ? "on" : "off"}: the throwing step arrives as a JSBSimError with JSBSim's message`, kind === "JSBSimError" && steps > 10 && steps < 200, `${steps} steps, then: ${short(err)}`);
    report("  ... and the simulation is halted with reason \"exception\"", h !== null && h.reason === "exception", h ? short(h.detail) : "not halted");
    report("  ... time inside JSBSim has moved on (the step is not rolled back), the outputs have not", h !== null && sim.getProperty("simulation/sim-time-sec") > sim.outputs[0]! + 1e-9,
      `JSBSim's time ${sim.getProperty("simulation/sim-time-sec")}, outputs' time ${sim.outputs[0]}`);
    let again = "";
    try { sim.run(); } catch (e) { again = e instanceof JSBSimError ? e.message : "not a JSBSimError"; }
    report("  ... stepping again is refused until reset()", /halted/.test(again), short(again));
    sim.reset(); sim.setDebugLevel(0); sim.dt = 1 / 480; sim.loadModel("c172x"); sim.runIC();
    report("  ... after reset() the instance flies again", sim.halted === null && sim.runSteps(10) === 10);
  }
  sim.setContainment(null);

  console.log("## 3b. The midpoint scheme's own failure: Newton's method does not converge");
  // Never seen with an aircraft. Forced here with a body that cannot exist (an inertia tensor that is almost
  // singular: Ixx = Iyy = Izz = 1, Ixy = 0.999999), tumbling, with scheme 10 at 1200 Hz.
  {
    const odd = `<fdm_config name="odd" version="2.0" release="BETA"><planet><rotation_rate>0</rotation_rate></planet>
<metrics><wingarea unit="FT2">1</wingarea><wingspan unit="FT">1</wingspan><chord unit="FT">1</chord></metrics>
<mass_balance><ixx unit="SLUG*FT2">1</ixx><iyy unit="SLUG*FT2">1</iyy><izz unit="SLUG*FT2">1</izz><ixy unit="SLUG*FT2">0.999999</ixy>
<emptywt unit="LBS">32.174049</emptywt></mass_balance><ground_reactions/><aerodynamics/></fdm_config>`;
    sim.reset(); sim.setDebugLevel(0); sim.dt = 1 / 1200;
    sim.writeFile("aircraft/odd/odd.xml", odd);
    sim.loadModel("odd");
    for (const [p, v] of [["ic/h-sl-ft", 100000], ["ic/p-rad_sec", 1], ["ic/q-rad_sec", 2], ["ic/r-rad_sec", 3]] as const) sim.setProperty(p, v);
    sim.setIntegrators({ rateRotational: 10, positionRotational: 7 });
    sim.runIC();
    sim.setContainment({});
    sim.bindOutputs(["simulation/sim-time-sec", "velocities/p-rad_sec", "velocities/q-rad_sec", "velocities/r-rad_sec"]);
    sim.readOutputs(); // the state at the start is the first accepted state
    let steps = 0, err = "", kind = "";
    try { for (let k = 0; k < 250; k++) { const n = sim.step(16); steps += n; if (sim.halted || n < 16) break; } } catch (e) { kind = e instanceof JSBSimError ? "JSBSimError" : "other"; err = e instanceof Error ? e.message : String(e); }
    const h = sim.halted;
    report("the simulation stops: either containment refuses a step first, or the Newton failure arrives as a JSBSimError", h !== null && (kind === "" || kind === "JSBSimError"),
      h ? `${h.reason} at t = ${h.simTime.toFixed(4)} s after ${steps} accepted steps: ${short(h.detail)}` : `not halted after ${steps} steps`);
    report("  ... the published rates are finite and inside the limits", [...sim.outputs].every(Number.isFinite) && Math.max(...[1, 2, 3].map((j) => Math.abs(sim.outputs[j]!))) <= CONTAINMENT_DEFAULTS.maxBodyRateRadS,
      `published p, q, r: ${[1, 2, 3].map((j) => sim.outputs[j]!.toFixed(3)).join(", ")}`);
    // The same without containment: the failure itself must arrive, as a JSBSimError, and halt.
    sim.setContainment(null);
    sim.reset(); sim.setDebugLevel(0); sim.dt = 1 / 1200; sim.loadModel("odd");
    for (const [p, v] of [["ic/h-sl-ft", 100000], ["ic/p-rad_sec", 1], ["ic/q-rad_sec", 2], ["ic/r-rad_sec", 3]] as const) sim.setProperty(p, v);
    sim.setIntegrators({ rateRotational: 10, positionRotational: 7 });
    sim.runIC();
    steps = 0; err = ""; kind = "";
    try { for (let k = 0; k < 4000; k++) { sim.run(); steps++; } } catch (e) { kind = e instanceof JSBSimError ? "JSBSimError" : "other"; err = e instanceof Error ? e.message : String(e); }
    report("without containment: Newton's failure arrives as a JSBSimError with the scheme's message", kind === "JSBSimError" && /Newton did not converge|singular Jacobian/.test(err), `${steps} steps, then: ${short(err)}`);
    report("  ... the simulation is halted (reason \"exception\") and the counter of the scheme says why", sim.halted?.reason === "exception" && sim.getProperty("simulation/integrator/midpoint/not-converged") + sim.getProperty("simulation/integrator/midpoint/singular-jacobian") >= 1,
      `not-converged ${sim.getProperty("simulation/integrator/midpoint/not-converged")}, singular ${sim.getProperty("simulation/integrator/midpoint/singular-jacobian")}`);
  }
}

if (want.includes("crash")) {
  console.log("## 4. The crash cases of G3d, stepped like a game (16 steps per frame), default limits");
  const G5 = JSON.parse(readFileSync(new URL("../gates/gates-05.json", import.meta.url).pathname, "utf8"));
  const CONFIGS = JSON.parse(readFileSync(new URL("../gates/configs.json", import.meta.url).pathname, "utf8"));
  const g3 = G5.G3d, L = CONTAINMENT_DEFAULTS;
  const outs = ["simulation/sim-time-sec", "velocities/p-rad_sec", "velocities/q-rad_sec", "velocities/r-rad_sec", "position/h-agl-ft", "attitude/phi-rad", "attitude/theta-rad",
    "forces/fbx-gear-lbs", "forces/fby-gear-lbs", "forces/fbz-gear-lbs", "inertia/weight-lbs", "velocities/u-fps", "velocities/v-fps", "velocities/w-fps"];
  const floorOnPatched = { "simulation/integrator/rate/rotational": 1, "simulation/integrator/position/rotational": 7 };
  const configs: [string, Record<string, number>][] = [];
  for (const [name, props] of [["floor", floorOnPatched], ["c3-ab4", CONFIGS["c3-ab4"].properties], ["c2-mid", CONFIGS["c2-mid"].properties]] as [string, Record<string, number>][]) {
    configs.push([name, props]);
    configs.push([name + " + strut limits", { ...props, "gear/strut-limits/enabled": 1 }]);
  }
  console.log("| configuration | step rate | runs | ran 15 s within the limits | halted: below surface | tipped over | ground force | runaway rate | non-finite | exception | a published state broke a limit | thrown past the wrapper |");
  console.log("|---|---|---|---|---|---|---|---|---|---|---|---|");
  for (const [name, props] of configs) {
    for (const hz of [480, 960, 1200]) {
      const count: Record<string, number> = { complete: 0, "below-surface": 0, "tipped-over": 0, "ground-force": 0, "runaway-rate": 0, "non-finite": 0, exception: 0 };
      let runs = 0, published = 0, escaped = 0;
      const examples: string[] = [];
      for (const model of Object.keys(g3.aircraft)) for (const sc of Object.keys(g3.scenarios)) for (let run = 0; run < g3.draws.length; run++) {
        runs++;
        try {
          sim.reset(); sim.setDebugLevel(0); sim.dt = 1 / hz; sim.loadModel(model); sim.loadIC(g3.aircraft[model], true);
          const ic: Record<string, number> = { ...g3.scenarios[sc].ic };
          (g3.perturbed_properties as string[]).forEach((p, j) => { ic[p] = ic[p]! + g3.draws[run][j]; });
          for (const [p, v] of Object.entries(ic)) sim.setProperty(p, v);
          for (const [p, v] of Object.entries(props)) sim.setProperty(p, v);
          sim.runIC();
          sim.setContainment({});
          sim.bindOutputs(outs);
          const frames = Math.round(g3.scenarios[sc].seconds * hz / 16);
          let contactEver = false;
          for (let f = 0; f < frames; f++) {
            let stepped = 0;
            try { stepped = sim.step(16); } catch (e) { if (!(e instanceof JSBSimError)) throw e; }
            // what the game would draw: it must be finite and inside every limit
            const o = sim.outputs;
            const force = Math.hypot(o[7]!, o[8]!, o[9]!) / o[10]!;
            const okPublished = [...o].every(Number.isFinite) && Math.max(Math.abs(o[1]!), Math.abs(o[2]!), Math.abs(o[3]!)) <= L.maxBodyRateRadS && o[4]! >= L.minCgHeightAglFt && force <= L.maxGroundForceWeights;
            if (force > 0) contactEver = true;
            if (!okPublished) { published++; if (examples.length < 3) examples.push(`${model} ${sc} ${run}: published state out of limits at t=${o[0]}`); break; }
            if (sim.halted || stepped < 16) break;
          }
          const h = sim.halted;
          count[h ? h.reason : "complete"]!++;
          void contactEver;
        } catch (e) {
          escaped++;
          if (examples.length < 3) examples.push(`${model} ${sc} ${run}: ${e instanceof Error ? e.name + ": " + short(e.message) : "non-Error"}`);
        }
      }
      console.log(`| ${name} | ${hz} Hz | ${runs} | ${count.complete} | ${count["below-surface"]} | ${count["tipped-over"]} | ${count["ground-force"]} | ${count["runaway-rate"]} | ${count["non-finite"]} | ${count.exception} | ${published} | ${escaped} |`);
      report(`${name}, ${hz} Hz: no published state broke a limit, nothing escaped the wrapper, every run ended complete or halted with a reason`,
        published === 0 && escaped === 0 && Object.values(count).reduce((a, b) => a + b, 0) === runs, examples.join("; "));
    }
  }
}
sim.delete();
console.log(`# ${passed} passed, ${failed} failed (variant ${variant})`);
process.exit(failed ? 1 : 0);
