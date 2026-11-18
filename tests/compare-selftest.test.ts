// The comparator must refuse or fail deliberately bad traces, and pass good ones.
// Developed on synthetic traces only, before any real native-vs-wasm comparison (REPORT.md part 2).
import assert from "node:assert/strict";
import { test } from "node:test";

import { type Trace, bitEqual, classA, classB, classS, compareTraces } from "./lib/compare.ts";

const COLS = ["simulation/sim-time-sec", "position/h-sl-ft", "velocities/u-fps", "velocities/p-rad_sec", "attitude/psi-rad", "forces/fbz-total-lbs", "gear/unit[0]/WOW", "aero/alpha-rad", "position/ecef-x-ft", "attitude/phi-rad", "attitude/theta-rad", "velocities/vtrue-kts"];
const N = COLS.length;

function make(rows = 300, f?: (r: number, c: string, v: number) => number): Trace {
  const data = new Float64Array(rows * N);
  for (let r = 0; r < rows; r++) {
    const t = r / 120;
    const base: Record<string, number> = {
      "simulation/sim-time-sec": t, "position/h-sl-ft": 4000 + 3 * t, "velocities/u-fps": 150 + t,
      "velocities/p-rad_sec": 0.01 * Math.sin(t), "attitude/psi-rad": 3.0 + 0.05 * t, "forces/fbz-total-lbs": -2400 + 5 * t,
      "gear/unit[0]/WOW": r < 100 ? 1 : 0, "aero/alpha-rad": 0.05, "position/ecef-x-ft": 2.09e7 + 100 * t,
      "attitude/phi-rad": 0.1 * Math.sin(t), "attitude/theta-rad": 0.03, "velocities/vtrue-kts": 90 + t,
    };
    COLS.forEach((c, i) => { data[r * N + i] = f ? f(r, c, base[c]) : base[c]; });
  }
  return { columns: COLS.slice(), rows, data };
}
const A = { tolerance: classA };

test("identical traces pass and are bit-equal", () => {
  const r = compareTraces(make(), make(), A);
  assert.equal(r.refused, undefined);
  assert.equal(r.pass, true);
  assert.equal(bitEqual(make(), make()).equal, true);
});

test("a difference inside the tolerance passes; bitEqual still sees it", () => {
  const t = make(300, (r, c, v) => (c === "position/h-sl-ft" ? v + 5e-7 : c === "velocities/u-fps" ? v * (1 + 5e-10) : v));
  assert.equal(compareTraces(make(), t, A).pass, true);
  assert.equal(bitEqual(make(), t).equal, false);
});

for (const [name, col, bump] of [
  ["position over 1e-6 ft", "position/h-sl-ft", 2e-6],
  ["ECEF position over 1e-6 ft", "position/ecef-x-ft", 2e-6],
  ["speed over 1e-9 relative", "velocities/u-fps", 150 * 3e-9],
  ["rate over 1e-9 x floor 1e-3", "velocities/p-rad_sec", 2e-11],
  ["angle over 1e-9 relative", "attitude/psi-rad", 2e-8],
  ["force over 1e-9 relative", "forces/fbz-total-lbs", 1e-5],
  ["WOW differs", "gear/unit[0]/WOW", 1],
] as [string, string, number][]) {
  test(`fails: ${name}`, () => {
    const t = make(300, (r, c, v) => (c === col && r === 200 ? v + bump : v));
    const res = compareTraces(make(), t, A);
    assert.equal(res.refused, undefined);
    assert.equal(res.pass, false);
    const column = res.columns.find((x) => x.column === col)!;
    assert.equal(column.pass, false);
    assert.equal(column.firstRowOver, 200);
  });
}

test("Class S is 1000 times wider than Class A", () => {
  const t = make(300, (r, c, v) => (c === "position/h-sl-ft" ? v + 5e-4 : c === "velocities/u-fps" ? v * (1 + 5e-7) : v));
  assert.equal(compareTraces(make(), t, A).pass, false);
  assert.equal(compareTraces(make(), t, { tolerance: classS }).pass, true);
  const worse = make(300, (r, c, v) => (c === "position/h-sl-ft" ? v + 2e-3 : v));
  assert.equal(compareTraces(make(), worse, { tolerance: classS }).pass, false);
});

test("information-only columns are never judged", () => {
  const t = make(300, (r, c, v) => (c === "aero/alpha-rad" ? v + 1 : v));
  const res = compareTraces(make(), t, A);
  assert.equal(res.pass, true);
  assert.equal(res.columns.find((x) => x.column === "aero/alpha-rad")!.judged, false);
});

test("angles are compared wrapped", () => {
  const a = make(300, (r, c, v) => (c === "attitude/psi-rad" ? Math.PI - 1e-13 : v));
  const b = make(300, (r, c, v) => (c === "attitude/psi-rad" ? -Math.PI + 1e-13 : v));
  assert.equal(compareTraces(a, b, A).pass, true);
});

test("refuses: NaN, Inf, row count, columns, sim time, empty", () => {
  const nan = make(300, (r, c, v) => (c === "velocities/u-fps" && r === 250 ? NaN : v));
  assert.match(compareTraces(make(), nan, A).refused ?? "", /NaN or Inf/);
  assert.match(compareTraces(nan, make(), A).refused ?? "", /NaN or Inf/);
  assert.match(compareTraces(nan, nan, A).refused ?? "", /NaN or Inf/);
  const inf = make(300, (r, c, v) => (c === "aero/alpha-rad" && r === 3 ? Infinity : v));
  assert.match(compareTraces(make(), inf, A).refused ?? "", /NaN or Inf/);
  assert.match(compareTraces(make(300), make(299), A).refused ?? "", /row counts differ/);
  const cols = make();
  cols.columns[2] = "velocities/v-fps";
  assert.match(compareTraces(make(), cols, A).refused ?? "", /column lists differ/);
  const time = make(300, (r, c, v) => (c === "simulation/sim-time-sec" && r === 10 ? v + 1e-9 : v));
  assert.match(compareTraces(make(), time, A).refused ?? "", /sim time differs/);
  assert.match(compareTraces(make(0), make(0), A).refused ?? "", /empty/);
  const short = make();
  short.data = short.data.subarray(0, short.data.length - 5);
  assert.match(compareTraces(make(), short, A).refused ?? "", /data length/);
  assert.equal(compareTraces(make(), nan, A).pass, false);
});

test("NaN outside the judged window is still refused", () => {
  const nan = make(300, (r, c, v) => (c === "velocities/u-fps" && r === 290 ? NaN : v));
  assert.match(compareTraces(make(), nan, { tolerance: classA, windowSeconds: 1 }).refused ?? "", /NaN or Inf/);
});

test("the window limits what is judged", () => {
  const late = make(300, (r, c, v) => (c === "position/h-sl-ft" && r >= 200 ? v + 1 : v));
  assert.equal(compareTraces(make(), late, { tolerance: classA, windowSeconds: 1 }).pass, true);
  assert.equal(compareTraces(make(), late, { tolerance: classA, windowSeconds: 1 }).rowsJudged, 121);
  assert.equal(compareTraces(make(), late, { tolerance: classA, untilSimTime: 1.5 }).rowsJudged, 181);
  assert.equal(compareTraces(make(), late, A).pass, false);
  const early = make(300, (r, c, v) => (c === "position/h-sl-ft" && r === 120 ? v + 1 : v));
  assert.equal(compareTraces(make(), early, { tolerance: classA, windowSeconds: 1 }).pass, false);
});

test("Class B: caps, ensemble spread, refusals", () => {
  const native = make();
  const within = make(300, (r, c, v) => (c === "position/h-sl-ft" ? v + 0.5 : c === "attitude/phi-rad" ? v + 0.04 : v));
  assert.equal(classB(native, within, []).pass, true);
  const over = make(300, (r, c, v) => (c === "position/h-sl-ft" && r === 299 ? v + 2 : v));
  assert.equal(classB(native, over, []).pass, false);
  // An ensemble that itself spreads by 1 ft allows 3 ft.
  const member = make(300, (r, c, v) => (c === "position/h-sl-ft" ? v + 1 : v));
  const b = classB(native, over, [member]);
  assert.equal(b.pass, true);
  assert.equal(b.columns.find((x) => x.column === "position/h-sl-ft")!.allowed, 3);
  const wayOver = make(300, (r, c, v) => (c === "position/h-sl-ft" && r === 299 ? v + 4 : v));
  assert.equal(classB(native, wayOver, [member]).pass, false);
  const nan = make(300, (r, c, v) => (c === "velocities/u-fps" && r === 5 ? NaN : v));
  assert.ok(classB(native, nan, []).refused);
  assert.ok(classB(native, within, [nan]).refused);
  // The window: a late difference is not judged when the run is cut at 1.5 s.
  assert.equal(classB(native, over, [], 1.5).pass, true);
});
