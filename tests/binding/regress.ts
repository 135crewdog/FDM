// Regression tests for the binding defects found by the independent review (REVIEW-codex-02.md).
// Each check is a permanent test built from Codex's probe (tests/review/binding_probe.ts).
// usage: JSBSIM_VARIANT=jsbsim-weh npx tsx tests/binding/regress.ts     (exit code 1 if any check fails)
//
// Rule being tested: every failure of a public call arrives as a JSBSimError carrying JSBSim's own message.
// Nothing else may be thrown (no raw WebAssembly.Exception, no number), and nothing may fail silently.
import { createSim, JSBSimError } from "../../src/wasm.ts";
import type { JSBSim } from "../../src/jsbsim.ts";

const variant = process.env.JSBSIM_VARIANT ?? "jsbsim-weh";
let failed = 0, passed = 0;
function report(name: string, ok: boolean, detail: string) {
  ok ? passed++ : failed++;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  [" + detail + "]" : ""}`);
}
const short = (s: string) => (s.length > 110 ? s.slice(0, 110) + "..." : s);
/** The call must throw a JSBSimError whose message matches `re` (default: any non-empty, decoded message). */
function mustThrow(name: string, f: () => unknown, re?: RegExp) {
  try {
    const r = f();
    report(name, false, `no error; returned ${String(r)}`);
  } catch (e) {
    if (!(e instanceof JSBSimError)) return report(name, false, `threw ${e instanceof Error ? e.name : "a non-Error (" + Object.prototype.toString.call(e) + ")"} instead of JSBSimError`);
    const undecoded = /unknown C\+\+ exception|empty message/.test(e.message);
    const ok = !undecoded && (re ? re.test(e.message) : e.message.length > 0);
    report(name, ok, short(e.message));
  }
}
/** The call must not throw, and `cond` must hold for its result. */
function mustWork<T>(name: string, f: () => T, cond: (r: T) => boolean = () => true) {
  try {
    const r = f();
    report(name, cond(r), short(typeof r === "object" ? JSON.stringify(r) : String(r)));
  } catch (e) {
    report(name, false, `threw ${e instanceof Error ? e.name + ": " + short(e.message) : "a non-Error"}`);
  }
}

console.log(`# Binding regression tests, variant ${variant}`);
const sim: JSBSim = await createSim({ variant: variant as "jsbsim" | "jsbsim-weh" });
sim.setDebugLevel(0);
sim.loadModel("c172x");
sim.setProperty("review/a", 12);
sim.setProperty("review/b", 34);

console.log("## 1. Every C++ exception becomes a JSBSimError with JSBSim's message");
mustThrow("hasProperty(malformed path)", () => sim.hasProperty("review/bad["));
mustThrow("getProperty(malformed path): message decoded (std::string throw)", () => sim.getProperty("review/bad["));
mustThrow("setProperty(malformed path)", () => sim.setProperty("review/bad[", 1));
mustThrow("handle(malformed path)", () => sim.handle("review/bad["));
mustThrow("handle(missing property)", () => sim.handle("review/does-not-exist"), /does-not-exist/);
mustThrow("bindInputs([malformed path])", () => sim.bindInputs(["review/bad["]));
mustThrow("bindOutputs([missing property])", () => sim.bindOutputs(["review/does-not-exist"]), /does-not-exist/);
mustWork("hasProperty(existing) is true", () => sim.hasProperty("review/a"), (r) => r === true);
mustWork("hasProperty(missing) is false", () => sim.hasProperty("review/nope"), (r) => r === false);
mustThrow("loadModel(missing aircraft)", () => { const s = sim; s.reset(); s.setDebugLevel(0); s.loadModel("no_such_aircraft"); });
sim.reset(); sim.setDebugLevel(0); sim.loadModel("c172x");
sim.setProperty("review/a", 12); sim.setProperty("review/b", 34);
mustWork("the same instance still flies after the errors", () => { sim.runIC(); return sim.runSteps(10); }, (r) => r === 10);

mustThrow("loadIC(missing file)", () => sim.loadIC("no_such_reset_file"));
mustWork("loadIC(reset00) then runIC", () => { sim.loadIC("reset00"); sim.runIC(); return sim.getProperty("ic/h-agl-ft"); }, (r) => Number.isFinite(r));
console.log("## 2. Writes to read-only properties fail");
mustThrow("setProperty(read-only simulation/sim-time-sec)", () => sim.setProperty("simulation/sim-time-sec", 1234), /sim-time-sec/);
mustWork("read-only value unchanged", () => sim.getProperty("simulation/sim-time-sec"), (r) => r !== 1234);
const hTime = sim.handle("simulation/sim-time-sec");
mustThrow("set(handle of read-only property)", () => sim.set(hTime, 1234), /sim-time-sec/);
mustThrow("bindInputs([read-only property])", () => sim.bindInputs(["simulation/sim-time-sec"]), /sim-time-sec/);
mustWork("bindOutputs([read-only property]) is allowed", () => { sim.bindOutputs(["simulation/sim-time-sec"]); return sim.outputs.length; }, (r) => r === 1);

console.log("## 3. Handles must be integers in range");
const a = sim.handle("review/a"), b = sim.handle("review/b");
mustWork("valid handle round trip", () => { sim.set(a, 41); return sim.get(a); }, (r) => r === 41);
for (const [label, h] of [["-1", -1], ["1e10", 1e10], ["0.9", 0.9], ["NaN", NaN], ["2**32 + valid", 2 ** 32 + a], ["Infinity", Infinity], ["valid + 0.5", a + 0.5]] as const) {
  mustThrow(`get(${label})`, () => sim.get(h), /handle/);
  mustThrow(`set(${label})`, () => sim.set(h, 99), /handle/);
}
mustWork("review/a not changed by the rejected writes", () => sim.getProperty("review/a"), (r) => r === 41);
mustThrow("bindInputs([valid, NaN])", () => sim.bindInputs([a, NaN]), /handle/);
mustThrow("bindOutputs([0.9])", () => sim.bindOutputs([0.9]), /handle/);

console.log("## 4. Bulk exchange, and reset() clears it and invalidates old handles");
mustWork("bulk exchange works", () => {
  sim.bindInputs([a, b]); sim.bindOutputs([a, b]);
  sim.inputs.set([56, 78]); sim.applyInputs(); sim.readOutputs();
  return [...sim.outputs];
}, (r) => r[0] === 56 && r[1] === 78);
mustWork("a failed bind leaves the earlier binding intact", () => {
  try { sim.bindInputs([a, NaN]); } catch { /* expected */ }
  return sim.inputs.length;
}, (r) => r === 2);
mustWork("bulk views survive memory growth when re-read", () => {
  const before = sim.module.HEAPF64.buffer;
  try { sim.hasProperty("review/" + "x".repeat(before.byteLength * 2)); } catch { /* a long name may be refused; growth is the point */ }
  sim.inputs.set([90, 91]); sim.applyInputs(); sim.readOutputs();
  return { grew: sim.module.HEAPF64.buffer !== before, out: [...sim.outputs] };
}, (r) => r.out[0] === 90 && r.out[1] === 91);
sim.reset(); sim.setDebugLevel(0);
mustWork("after reset(): inputs and outputs have length 0", () => [sim.inputs.length, sim.outputs.length], (r) => r[0] === 0 && r[1] === 0);
sim.loadModel("f16");
mustThrow("old handle after reset(): get fails", () => sim.get(a), /handle/);
mustThrow("old handle after reset(): set fails", () => sim.set(a, 33), /handle/);
const fresh = sim.handle("ic/h-sl-ft");
mustWork("a new handle differs from every old handle", () => [a, b, fresh], (r) => r[2] !== r[0] && r[2] !== r[1]);
mustWork("old handle did not write the new property", () => { try { sim.set(a, 1234); } catch { /* expected */ } return sim.getProperty("ic/h-sl-ft"); }, (r) => r !== 1234);
mustThrow("bindInputs([old handle]) after reset()", () => sim.bindInputs([a]), /handle/);

console.log("## 5. Time step and integrator IDs are validated");
const dt0 = sim.dt;
sim.reset(); sim.setDebugLevel(0);
for (const [label, v] of [["0", 0], ["-0.01", -0.01], ["NaN", NaN], ["Infinity", Infinity]] as const)
  mustThrow(`dt = ${label}`, () => { sim.dt = v; }, /dt/);
mustWork("dt unchanged by the rejected values", () => sim.dt, (r) => r === dt0);
mustWork("dt = 1/480 before loading a model", () => { sim.dt = 1 / 480; return sim.dt; }, (r) => r === 1 / 480);
sim.loadModel("c172x");
mustThrow("dt changed after a model is loaded (FCS filters cached the old dt)", () => { sim.dt = 1 / 120; }, /before loading/);
mustWork("setDtAfterLoad() is the explicit way", () => { sim.setDtAfterLoad(1 / 240); return sim.dt; }, (r) => r === 1 / 240);
mustThrow("loadScript with a negative dt", () => { sim.reset(); sim.setDebugLevel(0); sim.loadScript("scripts/c1721.xml", -1); }, /dt/);
sim.reset(); sim.setDebugLevel(0); sim.loadModel("c172x");
for (const [label, s] of [
  ["rateRotational 12345", { rateRotational: 12345 }], ["rateRotational 2.5", { rateRotational: 2.5 }],
  ["rateRotational NaN", { rateRotational: NaN }], ["rateRotational -1", { rateRotational: -1 }],
  ["rateRotational 7 (Buss 2 is for attitude only)", { rateRotational: 7 }],
  ["rateTranslational 6 (Buss 1 is for attitude only)", { rateTranslational: 6 }],
  ["positionTranslational 8", { positionTranslational: 8 }], ["positionRotational 10", { positionRotational: 10 }],
] as const)
  mustThrow(`setIntegrators: ${label}`, () => sim.setIntegrators(s), /integrator/);
mustThrow("setProperty('simulation/integrator/rate/rotational', 12345)", () => sim.setProperty("simulation/integrator/rate/rotational", 12345), /integrator/);
mustWork("integrator unchanged by the rejected values", () => sim.getProperty("simulation/integrator/rate/rotational"), (r) => r === 1);
mustWork("valid integrators accepted (AB4 rates, Buss 2 attitude)", () => {
  sim.setIntegrators({ rateRotational: 5, positionRotational: 7 });
  return [sim.getProperty("simulation/integrator/rate/rotational"), sim.getProperty("simulation/integrator/position/rotational")];
}, (r) => r[0] === 5 && r[1] === 7);

// Patches 0002 and 0003 add settings. In the patched build they are validated like the others; in an unpatched build they do not exist.
if (sim.hasProperty("simulation/integrator/rate/rotational-on-contact")) {
  mustWork("implicit midpoint (10) accepted for the body rates; Euler (1) on contact", () => {
    sim.setIntegrators({ rateRotational: 10, rateRotationalOnContact: 1 });
    return [sim.getProperty("simulation/integrator/rate/rotational"), sim.getProperty("simulation/integrator/rate/rotational-on-contact")];
  }, (r) => r[0] === 10 && r[1] === 1);
  mustThrow("setIntegrators: rateTranslational 10 (midpoint is for the body rates only)", () => sim.setIntegrators({ rateTranslational: 10 }), /integrator/);
  mustThrow("setIntegrators: rateRotationalOnContact 7", () => sim.setIntegrators({ rateRotationalOnContact: 7 }), /integrator/);
  mustThrow("setProperty('simulation/integrator/rate/rotational-on-contact', -2)", () => sim.setProperty("simulation/integrator/rate/rotational-on-contact", -2), /integrator/);
  mustWork("switching off again (-1) and back to AB4, Buss 2", () => {
    sim.setIntegrators({ rateRotational: 5, rateRotationalOnContact: -1 });
    return [sim.getProperty("simulation/integrator/rate/rotational"), sim.getProperty("simulation/integrator/rate/rotational-on-contact")];
  }, (r) => r[0] === 5 && r[1] === -1);
} else {
  mustThrow("setIntegrators: rateRotational 10 in a build without patch 0002", () => sim.setIntegrators({ rateRotational: 10 }), /integrator/);
  mustThrow("setIntegrators: rateRotationalOnContact in a build without patch 0003", () => sim.setIntegrators({ rateRotationalOnContact: 1 }), /does not exist/);
}

console.log("## 6. Step counts are validated");
sim.runIC();
for (const [label, n] of [["NaN", NaN], ["-1", -1], ["2.5", 2.5], ["2**32", 2 ** 32]] as const) {
  mustThrow(`runSteps(${label})`, () => sim.runSteps(n), /step/);
  mustThrow(`step(${label})`, () => sim.step(n), /step/);
}
mustWork("runSteps(5) runs 5 steps", () => sim.runSteps(5), (r) => r === 5);

console.log("## 7. The 737 runs on a clean install (its socket input must not need the npm package 'ws')");
mustWork("737: load, runIC, 200 steps, finite", () => {
  sim.reset(); sim.setDebugLevel(0); sim.loadModel("737"); sim.runIC();
  const n = sim.runSteps(200);
  return { n, h: sim.getProperty("position/h-sl-ft") };
}, (r) => r.n === 200 && Number.isFinite(r.h));

console.log("## 8. Gaps found by the review of session 04 (REVIEW-codex-04.md)");
// 8a. A script's own time step is validated before anything is loaded.
const scriptWithDt = (dt: string) => `<runscript name="dt test"><use aircraft="c172x" initialize="reset00"/><run start="0" end="1" dt="${dt}"/></runscript>`;
for (const dt of ["-0.01", "0", "-0", "inf", "nan", ""]) {
  sim.reset(); sim.setDebugLevel(0);
  sim.writeFile("scripts/regress-dt.xml", scriptWithDt(dt));
  mustThrow(`loadScript: the script's own dt="${dt}" is rejected`, () => sim.loadScript("scripts/regress-dt.xml"), dt === "nan" || dt === "inf" || dt === "" ? undefined : /time step/);
  mustWork(`  ... and the simulation is not left with that step (dt="${dt}")`, () => sim.dt, (r) => r > 0 && Number.isFinite(r));
}
sim.reset(); sim.setDebugLevel(0);
sim.writeFile("scripts/regress-dt.xml", scriptWithDt("0.005"));
mustWork("loadScript: a script with a valid dt of its own still loads", () => { sim.loadScript("scripts/regress-dt.xml"); return sim.dt; }, (r) => r === 0.005);
sim.reset(); sim.setDebugLevel(0);
sim.writeFile("scripts/regress-dt.xml", scriptWithDt("-0.01"));
mustWork("loadScript: an explicit dt overrides a bad dt in the script", () => { sim.loadScript("scripts/regress-dt.xml", 1 / 240); return sim.dt; }, (r) => r === 1 / 240);

// 8b. setIntegrators reads each setting once, and applies everything or nothing.
sim.reset(); sim.setDebugLevel(0); sim.loadModel("c172x");
sim.setIntegrators({ rateRotational: 1, rateTranslational: 3 });
{
  let reads = 0;
  const changing = { rateRotational: 5, get rateTranslational() { reads++; return reads <= 3 ? 3 : 999; } };
  mustWork("setIntegrators: a setting is read exactly once (an object whose value changes between reads cannot half-apply)", () => {
    let threw = "";
    try { sim.setIntegrators(changing); } catch (e) { threw = String(e); }
    return { reads, threw, rate: sim.getProperty("simulation/integrator/rate/rotational"), trans: sim.getProperty("simulation/integrator/rate/translational") };
  }, (r) => r.reads === 1 && r.threw === "" && r.rate === 5 && r.trans === 3);
}
{
  // A failure injected at the second write: the first write must be undone.
  sim.setIntegrators({ rateRotational: 1, rateTranslational: 3, positionRotational: 1 });
  const real = sim.setProperty.bind(sim);
  let writes = 0;
  (sim as unknown as { setProperty: (n: string, v: number) => void }).setProperty = (n, v) => {
    if (++writes === 2) throw new JSBSimError("injected failure of the second write");
    real(n, v);
  };
  let threw = false;
  try { sim.setIntegrators({ rateRotational: 5, rateTranslational: 4, positionRotational: 7 }); } catch (e) { threw = e instanceof JSBSimError; }
  delete (sim as unknown as { setProperty?: unknown }).setProperty;
  mustWork("setIntegrators: when a later write fails, the earlier ones are undone (all or nothing)", () => ({
    threw, rate: sim.getProperty("simulation/integrator/rate/rotational"), trans: sim.getProperty("simulation/integrator/rate/translational"),
    att: sim.getProperty("simulation/integrator/position/rotational"),
  }), (r) => r.threw && r.rate === 1 && r.trans === 3 && r.att === 1);
}

// 8c. Status values of patch 0003 and the counters of patch 0002 are read-only; the switch's settings are validated.
if (sim.hasProperty("simulation/integrator/rate/rotational-on-contact")) {
  const R = "simulation/integrator/rate/", M = "simulation/integrator/midpoint/";
  const status = [R + "contact-active", R + "contact-switches", ...["steps", "newton-iterations", "max-newton-iterations", "split-steps",
    "rounding-exits", "euler-fallbacks", "not-converged", "singular-jacobian"].map((c) => M + c)];
  for (const p of status) {
    mustThrow(`setProperty(${p}) is refused (read-only)`, () => sim.setProperty(p, 77), /read-only/);
    mustWork(`  ... and its value is unchanged`, () => sim.getProperty(p), (r) => r === 0);
  }
  mustThrow("set(handle of contact-active) is refused", () => sim.set(sim.handle(R + "contact-active"), 1), /read-only/);
  mustThrow("bindInputs([contact-active]) is refused", () => sim.bindInputs([R + "contact-active"]), /read-only/);
  for (const [label, v] of [["-1", -1], ["NaN", NaN], ["Infinity", Infinity]] as const)
    mustThrow(`contact-hold-sec = ${label} is refused`, () => sim.setProperty(R + "contact-hold-sec", v), /contact-hold-sec/);
  mustWork("contact-hold-sec unchanged by the refused values", () => sim.getProperty(R + "contact-hold-sec"), (r) => r === 0);
  mustWork("contact-hold-sec = 0.1 is accepted", () => { sim.setProperty(R + "contact-hold-sec", 0.1); return sim.getProperty(R + "contact-hold-sec"); }, (r) => r === 0.1);
  for (const v of [99, -1, 2])
    mustThrow(`contact-release-mode = ${v} is refused`, () => sim.setProperty(R + "contact-release-mode", v), /contact-release-mode/);
  mustWork("contact-release-mode unchanged by the refused values", () => sim.getProperty(R + "contact-release-mode"), (r) => r === 1);
  mustWork("contact-release-mode = 0 and 1 are accepted", () => { sim.setProperty(R + "contact-release-mode", 0); const a0 = sim.getProperty(R + "contact-release-mode"); sim.setProperty(R + "contact-release-mode", 1); return [a0, sim.getProperty(R + "contact-release-mode")]; }, (r) => r[0] === 0 && r[1] === 1);
  mustWork("the status values still count: a c172x dropped onto its gear with Euler on contact switches scheme", () => {
    sim.reset(); sim.setDebugLevel(0); sim.dt = 1 / 480; sim.loadModel("c172x"); sim.loadIC("reset00");
    sim.setProperty("ic/h-agl-ft", 6);
    sim.setIntegrators({ rateRotational: 5, positionRotational: 7, rateRotationalOnContact: 1 });
    sim.runIC(); sim.runSteps(960);
    return { active: sim.getProperty(R + "contact-active"), switches: sim.getProperty(R + "contact-switches") };
  }, (r) => r.active === 1 && r.switches >= 1);
}

try { sim.delete(); } catch { /* the instance may be unusable after a raw exception in the old binding */ }
console.log(`# ${passed} passed, ${failed} failed (variant ${variant})`);
process.exit(failed ? 1 : 0);
