# Report: FDM2 01 Work, JSBSim baseline

Branch `baseline/jsbsim`, started 2026-11-18 from `main` at `361cb26`.

**Session goal** (from `prompts/01-jsbsim-baseline.md`): an upstream-physics JSBSim WebAssembly core plus a thin
host layer, on a new branch `baseline/jsbsim` created from `main`. The host layer (wrapper, ground hook, loop) is
not a physics change. Attempt 1's build files are not reused.

This file is written in three parts, in this order:
1. **Done means**: the prompt's list, copied word for word.
2. **Frozen thresholds**: every pass/fail line, committed before any build or run.
3. **Results**: filled in as the work proceeds. Nothing in parts 1 and 2 is edited after a result exists. If a
   line turns out to be wrong, it stays, the result stays, and a new line is added and marked **added**.

**Evidence labels** (CLAUDE.md rule 4):
- **Verified:** checked against an answer we did not produce (native build of upstream code, NASA data, upstream
  source, the user's device).
- **Supported:** our own test shows it.
- **Reasoned:** not tested; the test that would settle it is named.

---

## Part 1. Done means (verbatim from the prompt)

1. **Pin and build.**
   - Pin a JSBSim commit: v1.3.3, or a later one that includes PR #1504. Record the reason. Pin Emscripten.
   - Exceptions on for all code (including expat): a `-fwasm-exceptions` build plus an `-fexceptions` fallback
     build (Safari 26.0 bug, see `RESEARCH.md`).
   - `-O3`, no fast-math, fixed memory size.
   - The build stops on any error. Commit the binaries and a build-info file (versions, flags, hashes).
   - Commit the JSBSim data at that commit under `jsbsim-data/`.
2. **Answer key.** Native JSBSim built from the same commit, with the same wrapper C++.
3. **Wrapper (C++ + TypeScript).**
   - One new instance per load (issue #1506).
   - `Setdt` before load. dt and integrator settings are checked and enforced after scripts, reset and initial
     conditions.
   - Cached property handles plus a bulk in/out `Float64Array`.
   - Validated writes: read-only, NaN, int.
   - Errors become a JavaScript `Error` with JSBSim's message.
   - JSBSim's logger is routed to JavaScript.
   - Crash and terminate are reported as events.
4. **Ground hook.** A C++ `FGGroundCallback` reading a height grid we supply (height, normal, contact point),
   re-installed after each load. Tested on flat ground and on a slope, against native running the same C++.
5. **Loop.**
   - Fixed-step accumulator, 1/120 s by default, with a catch-up cap.
   - Pause when the page is hidden; no catch-up afterwards.
   - Expose the previous and current state for interpolation.
   - The same core runs in a Worker (the game path) and in headless Node (tests).
6. **Load test.** Every aircraft that loads natively also loads in WebAssembly (table of results).
7. **Parity.** Step-by-step against native on:
   - c1723 (c172x);
   - one f16 script;
   - NASA check cases 01, 02 and one more that applies.

   Turbulence off. Thresholds written down before the run.
8. **External forces.** Set from TypeScript every step and compared with native. Measure the cost of 20 forces
   through the bulk path.
9. **iPhone page.**
   - User agent.
   - Batched timing at 1/120, 1/240, 1/480 and 1/1000 s, in the Worker and on the main thread.
   - With and without 20 forces.
   - A broken aircraft caught and shown.
   - One instance created and destroyed 20 times (memory check).
   - I paste the results back.
10. **Finish.** Tag `jsbsim-baseline-v1`, or record the commit in `PLAN.md` if the tag push is refused. Write
    `prompts/02-yasim-baseline.md`, update `PLAN.md` and `prompts/README.md`, push.

**Out of scope:** integrator tuning, physics patches, wing-strip forces, real terrain data, rendering.

### User decision added before any work (2026-11-18, in the planning chat)

Upstream JSBSim ships only NASA check case 02 (see "What planning found"). The user chose the widest parity set:
- all 63 upstream scripts in `scripts/`, plus NASA case 02 as shipped;
- NASA cases 01 and 03 written by this session as test fixtures from NASA's published definitions, kept under
  `tests/`, never in `jsbsim-data/`.

This widens criterion 7; it does not replace any line of it.

### What planning found (read-only research, before any work)

| Finding | Evidence | Label | Effect |
|---|---|---|---|
| PR #1504 (Emscripten portability) is commit `4e695159`, an ancestor of tag v1.3.3; it first shipped in v1.3.2. `RESEARCH.md` says it merged after v1.3.3; that line is wrong. | `git merge-base --is-ancestor 4e695159 v1.3.3` = yes; `git tag --contains` = v1.3.2, v1.3.3 | Verified (upstream history) | Pin v1.3.3. |
| Commits on upstream master after the v1.3.3 fork point change no physics (expat 2.8.5, FlightGear UDP output, table-axis validation, docs, coverage build). | `git log --stat v1.3.3..master -- src` | Verified (upstream history) | Nothing gained from a later pin. |
| Emscripten 7.0.0 was released 2026-11-06 (new major version, libc++ 23). 6.0.13 (2026-10-19) built v1.3.3 unpatched in attempt 1 and ran on the user's Safari 27.2. | emsdk release list; attempt 1 `REPORT-02` | Verified (release list); Supported (attempt 1) | Pin Emscripten 6.0.13. |
| Upstream has only NASA case 02 (`check_cases/NASA_EOM_2015`: `brick.xml`, `reset_Atmos_02.xml`, `Atmos_02.xml`), at the tag and on master. | `git ls-tree` | Verified (upstream tree) | User decision above. |
| Attempt 1's native answer key was the Python module, not the wasm binding's C++. | `archive/attempt-1` `scripts/build-native.sh` | Verified (archive) | Native key here is built from the same host C++. |
| In attempt 1, wasm and native start altitude differed by 7.5e-9 ft; `c1723` differed by up to 0.24 ft and 0.015 rad after the ground roll; `f16_test` agreed to 7.6e-4 ft until it hit the ground inverted at about 128 s. | attempt 1 `results/02-test2-parity.txt` | Supported (attempt 1) | Informs the thresholds below. |
| p51d, f104 and Camel write 0 to the integrator properties from their own crash-detect systems. | upstream aircraft data | Verified (upstream data) | Integrator settings are enforced after load and `RunIC`; while stepping, a change is reported, not undone. |

---

## Part 2. Frozen thresholds (committed before any build or run)

### Pins
- JSBSim: tag **v1.3.3**, commit `66f7fafc07fe13e7ede9db20873030fed2881713`. Reason: latest release; includes
  PR #1504; later master commits change no physics.
- Emscripten: **6.0.13**. Reason: see the table above.
- No source patch to JSBSim. If the pinned source does not build or load unpatched, the session stops and reports.

### How traces are compared
- A trace is one row per step, row 0 taken after `RunIC`, each row the listed properties as 64-bit floats.
- The comparator refuses (a failure, not a pass) on: different column lists, different row counts, any NaN or
  Inf in either trace, or sim time differing by more than 1e-12 s on any row.
- Angle differences are wrapped into (−π, π].
- "Peak" is the largest |native value| of that column inside the judged window.

**Judged columns** (every scenario unless stated):

| Group | Properties | Class A tolerance |
|---|---|---|
| Positions | `position/ecef-x-ft`, `ecef-y-ft`, `ecef-z-ft`, `position/h-sl-ft`, `position/h-agl-ft` | 1e-6 ft |
| Speeds | `velocities/u-fps`, `v-fps`, `w-fps`, `velocities/vtrue-kts` | 1e-9 × max(peak, 1) |
| Rates | `velocities/p-rad_sec`, `q-rad_sec`, `r-rad_sec` | 1e-9 × max(peak, 1e-3) |
| Angles | `attitude/phi-rad`, `theta-rad`, `psi-rad` | 1e-9 × max(peak, 1e-3) |
| Forces, moments | `forces/fbx-total-lbs`, `fby-`, `fbz-`; `moments/l-total-lbsft`, `m-`, `n-` | 1e-9 × max(peak, 1) |
| Contact | `gear/unit[k]/WOW` and `contact/unit[k]/WOW` for every unit the aircraft has | equal |

Recorded for information only, never judged: `aero/alpha-rad`, `aero/beta-rad` (ill-conditioned at standstill).

### Class A, rounding level (tolerances in the table above)
Applies to the **whole run** of:
- NASA check case 02 as shipped (30 s, dt 0.01);
- this session's fixtures for NASA cases 01 and 03 (30 s, dt 0.01);
- the external-forces run (criterion 8), which also judges `forces/fb{x,y,z}-external-lbs` and
  `moments/{l,m,n}-external-lbsft` in the forces group;
- the slope-rest ground run (criterion 4).

Applies to the **first 1 s** (rows with sim time − start time ≤ 1 s) of `scripts/c1723.xml` and
`scripts/f16_test.xml`.

### Class S, script sweep
For each of the other upstream scripts in `jsbsim-data/scripts/`: the **first 1 s**, same columns, tolerances
1000 times wider than Class A (positions 1e-3 ft; the rest 1e-6 × max(peak, floor)).
- Each script runs at its own `<run dt>` with the upstream default ground callback.
- A script that fails natively (at load, at `RunIC`, or at step N) must fail at the same stage and step in wasm.
  That counts as a pass for parity and is listed.
- Before the sweep runs, the data is searched for random elements (`<noise>`, random functions, turbulence and
  random seeds). The list of affected aircraft, scripts and properties is committed first. Properties fed
  directly by a random element are not judged. A script whose judged state depends on random draws is reported as
  "not comparable (RNG)" and is not a pass or a fail.
- Turbulence off is read back in every run: `atmosphere/turbulence/milspec/severity` = 0 and
  `atmosphere/turb-north-fps`, `turb-east-fps`, `turb-down-fps`, `atmosphere/p-turb-rad_sec`, `q-`, `r-` exactly 0
  on every row. A script that turns turbulence on is listed under "not comparable (RNG)".
- Whole-run differences of these scripts are reported for information only.

### Class B, sensitive scripts, whole run
Applies to `scripts/c1723.xml` (200 s) and `scripts/f16_test.xml` (rows with sim time ≤ 120 s; attempt 1 saw it
hit the ground inverted at about 128 s).
- Judged properties and caps: `position/h-sl-ft` 1 ft; `attitude/phi-rad`, `theta-rad`, `psi-rad` 0.05 rad;
  `velocities/vtrue-kts` 1 kt.
- Native ensemble: 8 native runs with `ic/h-sl-ft` moved by k × 2⁻²⁸ ft (one unit in the last place of an
  Earth-radius-sized coordinate), k = ±1, ±2, ±3, ±4, before `RunIC`. Spread S = the largest
  |member − unperturbed native| over all rows and members, per property.
- Pass, per property: largest |wasm − native| over all rows ≤ max(cap, 3 × S).
- The ensemble shows sensitivity only. It is not evidence that the build is correct.

### Exact checks (bit for bit)
- `-fwasm-exceptions` trace = `-fexceptions` trace, on every scenario in this report.
- TypeScript-driven wasm trace = wasm trace from the C++ scenario runner inside the same binary, on: NASA 02,
  the external-forces run, the slope-rest run, the first 10 s of c1723.
- Native: a constant-height grid in our ground hook = upstream's `FGDefaultGroundCallback` at the same height, on
  c172x (first 30 s of c1723, which covers rest and ground roll) and on NASA 02.
- Every scenario run twice on the same build gives the same trace.

### Ground hook (criterion 4), other lines
- Constant-slope grids, one rising to the north and one rising to the east, with different numbers of rows and
  columns. At 20 sample points each, our hook's output is compared with a separate calculation that does not
  share its code (surface points placed with `FGLocation`, normal from the cross product of two tangents):
  height within 1e-6 ft, contact point within 1e-6 ft per ECEF coordinate, normal within 1e-6 per component.
  The normal is unit length within 1e-12 and points up (positive along local up).
- After each load, the hook's call counter increases during the next step (proves ours is the one installed).
- A native build with assertions on runs the ground scenarios with no assertion failure.
- Slope-rest run: c172x on a 5° slope, brakes on, 10 s at 1/120 s: wasm against native, Class A.
- Whether the aircraft stays put on the slope is reported for information; it is upstream physics.

### Load test (criterion 6)
- "Loads" means: on a fresh instance, `LoadModel(<folder name>)` returns true and throws nothing.
- Pass: for all 61 folders under `jsbsim-data/aircraft/`, the wasm result equals the native result, in both wasm
  builds. Every native failure is listed with JSBSim's message.
- Information only: `RunIC` plus 10 steps for each aircraft that loads.

### Build (criterion 1)
- Every compiled file of JSBSim, expat and the host has `-O3`, the build's exception flag, and no
  `-ffast-math` / `-Ofast` (checked from `compile_commands.json`).
- Memory growth is off; the fixed size is recorded with the measured peak that justifies it.
- A deliberately broken source file makes the build script exit non-zero and leaves `dist-wasm/` unchanged.
- The committed binaries' sha256 match `build-info.json`.
- Two clean builds are compared; identical hashes are hoped for, and any difference is reported (not pass/fail).
- `jsbsim-data/` folders have the same git tree ids as the pinned upstream commit.

### Wrapper (criterion 3)
Each of these has a test that must pass in both wasm builds and natively where it applies:
- a second load on one instance is refused;
- dt set before load equals `GetDeltaT()` after load and after `RunIC`; a script loaded with a host dt runs at
  the host dt; integrator settings equal the configured ones after load and `RunIC`;
- writing a read-only property, a NaN, or a non-integer to an integer property is refused with a distinct
  status, and the property keeps its value;
- an unknown property name is an error and creates nothing;
- a malformed aircraft file produces a JavaScript `Error` whose message contains JSBSim's text;
- at least one JSBSim log record reaches the JavaScript log callback during a load;
- script end, `simulation/terminate` and a non-finite state each produce their event.

### Loop (criterion 5)
With a fake clock:
- 1 s of frames at 60 Hz gives exactly 120 steps at 1/120 s;
- one 10 s frame gives no more than the cap, and the dropped time is counted;
- pause, 10 s pass, resume: 0 catch-up steps;
- `prev` and `curr` are the states before and after the last step, and 0 ≤ alpha < 1;
- the same handler code passes the same test in Node directly and inside a `worker_threads` Worker.

### External forces (criterion 8)
- Class A parity as stated above. Timings are information only.

### iPhone page (criterion 9)
Passes when, on the user's iPhone, in both builds:
- every section finishes with no uncaught error;
- the broken aircraft shows an `Error` carrying JSBSim's message;
- 20 create/destroy cycles complete in the Worker and on the main thread;
- every timing cell (4 step sizes × Worker/main × 0/20 forces) reports a number.

Timings and memory figures are information only. Before the user is asked, the committed page must pass the same
lines in headless Chromium here.

### If a line fails
The result is kept and reported with evidence, no threshold is edited, and the session stops for the user.

### Added lines

Nothing above this heading has been changed since the first commit of this file (`31ec289`).

#### Added 2026-11-18, after the slope-rest Class A line failed, with the user's agreement: Class N

Committed before any further parity run. Reason: Class A (and Class S) ask forces and speeds to agree more
closely than a last-digit position difference allows once a gear spring is in the loop (part 3, "The failed
line"). The failed line and its result stay.

**Class N (noise-relative), for runs that touch the ground.**
- *Applies to* every judged run in which any wheel or contact flag is 1 on any judged row of the native trace:
  the slope-rest run, the first 1 s of `c1723` and of `f16_test`, and each such script in the sweep. Runs that
  never touch the ground keep their frozen class only.
- *Native ensemble* (the one frozen for Class B): 8 native runs with `ic/h-sl-ft` moved by k × 2⁻²⁸ ft,
  k = ±1, ±2, ±3, ±4, before `RunIC`. A member whose row 0 is bit-identical to the unperturbed native run had no
  effect. If fewer than 4 members differ from it, the line is **refused** (a failure, not a pass).
- *Pass, per judged column:* largest |wasm − native| over the judged rows ≤ max(F, 3 × S), where F is that run's
  frozen allowance (Class A, or Class S in the sweep) and S is the largest |member − native| over the judged rows
  and all members.
- *Not widened:* position columns keep F only (1e-6 ft; 1e-3 ft in the sweep). Contact flags must be equal.
- Angles are wrapped. The comparator's refusals (column lists, row counts, NaN or Inf, sim time) apply to every
  trace, the members included.
- *Reporting:* for each such run both results are shown: the frozen class (which may fail) and Class N.
- *What counts from here:* a ground-contact run meets its criterion on Class N. If Class N fails or is refused,
  or any other frozen line fails, the result is kept and the session stops again.

What this line is and is not:
- For the slope-rest run it was written after that run's wasm-native difference had been seen, but before any
  ensemble had been run. For every other run it was written before the run.
- The ensemble shows how large a difference one last digit makes in native itself. A pass says the wasm-native
  difference is of that size. It is not proof that the build is correct. The independent evidence is the
  position agreement, the bit-for-bit checks, and the airborne Class A runs.

---

## Part 3. Results

**Status: stopped a second time, at criterion 7, on 2026-11-18.** Three scripts of the 59-script sweep fail a
frozen line. The runs the prompt names (c1723, f16_test, NASA 01, 02, 03) all meet their lines. Waiting for the
user's decision. Criteria 8, 9 and 10 have not been run.

| Criterion | State |
|---|---|
| 1 Pin and build | done, except committing the binaries |
| 2 Answer key | done |
| 3 Wrapper | done, all lines pass |
| 4 Ground hook | done; one frozen line failed and is kept; the run passes the added Class N |
| 5 Loop | done, all lines pass (browser Worker itself: criterion 9) |
| 6 Load test | done, passes |
| 7 Parity | named runs pass; sweep: 56 of 59 meet their line, **3 fail** (below) |
| 8, 9, 10 | not started |

### Second stop: three sweep scripts fail a frozen line (criterion 7)

Raw output: `results/parity.txt`, `results/parity-sweep.md`, `results/parity-detail.txt`. Diagnosis:
`results/diag-sweep-failures.txt`, `results/diag-c3104-roll-moment.txt`,
`results/diag-native-nudge-experiments.txt` (scripts in `tests/diag/`).

| Script | Frozen line that failed | What was measured |
|---|---|---|
| `c3104` (c310, airborne in the first second) | Class S, first 1 s | roll moment differs by 7.1e-2 lb·ft at row 13 (allowed 2.2e-3); yaw moment 7.0e-3 (allowed 9.4e-6); roll rate, yaw rate, bank, side speed, side force follow. Positions agree to 9e-9 ft. |
| `c3105` (c310, airborne in the first second) | Class S, first 1 s | the same pattern at row 31: roll moment 6.9e-2 lb·ft, yaw moment 6.8e-3 |
| `mk82_script` (mk82 bomb) | "fails at the same stage and step" | both sides stop with a non-finite state, native at step 2242, wasm at step 2308 (both wasm builds). The first second agrees to 1.1e-13 (inside Class S). |

Both wasm builds give identical traces in all three. **Supported.**

**Cause of the c310 failures, traced and then reproduced in native alone.**
- Both scripts start heading exactly north. After `RunIC`, native reports the heading as 6.283185307179586
  (2π minus one last digit); wasm reports 8e-16. It is the same heading within one last digit, on either side of
  the 0 / 2π seam. The comparator wraps angles, so the heading column itself passes.
- At 0.25 s the script switches the c310 autopilot's heading hold on. At that step `ap/aileron_cmd` is
  −0.00250 in native and 0.000001 in wasm, the aileron differs by 7.9e-4 rad, and the aerodynamic roll moment by
  7.1e-2 lb·ft. Every other part of the roll moment (propeller, gear, external) is identical at that step.
- Native-only experiment: the same script with native's start heading moved by one last digit (k × 2⁻⁵⁰ rad).
  For k = +1 native reports 8.4e-16 instead of 2π, and it differs from unperturbed native by 7.12e-2 lb·ft at
  row 13 (`c3104`) and 6.94e-2 at row 31 (`c3105`): the same numbers as wasm against native.
- So the upstream c310 autopilot answers a last-digit change of heading across north with a different aileron
  command, in native itself. **Supported** (native against native). Not a difference between the builds.
- The frozen 8-run altitude ensemble does not show it in `c3104` (spread 6e-11 lb·ft): moving the altitude does
  not move the heading across the seam there. In `c3105` it does for some members (spread 3.5e-2).

**Cause of the mk82 failure.**
- The bomb's pitch rate grows without limit in native: over 10 rad/s at 41.5 s, over 1e6 rad/s at 43.8 s, still
  2100 ft above the ground, then the state becomes non-finite. This is upstream physics at JSBSim's default
  settings. **Supported.**
- Native-only experiment: the 8 native runs with the start altitude moved by one to four last digits stop at
  steps 2404, 2200, 2199, 2280, 2199, 2240, 2330, 2201 (unperturbed: 2242). Wasm's 2308 is inside that range.
  The step at which a blown-up state turns into NaN is decided by last digits. **Supported.**
- The frozen rule ("same stage and step") was written wrongly for a failure of this kind. It stays, and the
  result stays FAIL.

**What these three results do and do not show.** They do not show a difference in how the two builds compute:
in each case native differs from itself by the same amount after a one-last-digit change. They do show that
"step-by-step parity" cannot be held to a fixed small number for a model that has a discontinuity (a heading
seam, a blow-up) inside the judged rows.

### Criterion 7: the runs the prompt names (all meet their lines)

| Run | Line | Result |
|---|---|---|
| NASA 02 (as shipped), 3000 steps at 0.01 s | Class A, whole run | **pass**: largest difference 2.2e-16 rad (allowed 1.2e-9) |
| NASA 01 (project fixture) | Class A, whole run | **pass**: largest difference 4.3e-19 rad |
| NASA 03 (project fixture) | Class A, whole run | **pass**: largest difference 8.9e-16 rad |
| c1723, first 1 s | frozen Class A | FAIL (ground contact: yaw moment 6.3e-6 lb·ft, allowed 6.3e-9); kept |
| c1723, first 1 s | Class N (added) | **pass**: closest column at 0.24 of its allowance |
| c1723, whole run (200 s) | Class B | **pass**: altitude 0.238 ft (cap 1), bank 0.0153 rad and heading 0.0146 rad (cap 0.05), pitch 0.0012 rad, airspeed 0.050 kt (cap 1) |
| f16_test, first 1 s | frozen Class A | FAIL (ground contact: yaw moment 2.5e-2 lb·ft); kept |
| f16_test, first 1 s | Class N (added) | **pass**: closest column at 0.36 of its allowance |
| f16_test, to sim time 120 s | Class B | **pass**: altitude 6.0e-4 ft, attitude 5.9e-8 rad, airspeed 3.6e-6 kt |
| all five | bit-for-bit checks | **pass**: wasm-EH = JS-EH; each side run twice identical; TypeScript-driven = C++ runner on NASA 02 and on the first 10 s of c1723 |
| all five | turbulence read back | off on every row |

All **Supported** (wasm against the native answer key built from the same host C++).

For c1723 the native ensemble spreads as much as wasm differs (altitude 0.265 ft against 0.238 ft): the 200 s
differences are the size that one last digit makes in native itself. Attempt 1 measured 0.24 ft and 0.015 rad.

**Are the fixtures for cases 01 and 03 the NASA cases?** Information only (part 2). Our native run against
NASA's published results (`tests/reference/nasa/`, 301 points each):
- Case 01: altitude within 4.5e-4 to 1.6e-3 ft of each NASA simulation; NASA's simulations differ from each other
  by 2.1e-3 ft. Angles and rates agree to 5e-8 deg or better. **Verified** (NASA data): the fixture is case 01.
- Case 03: rates within 0.011 to 0.095 deg/s of each NASA simulation (NASA's own spread 0.017 to 0.074 deg/s);
  Euler angles within 0.08 to 0.65 deg (NASA's own spread 0.34 to 0.65 deg); altitude within 1.6e-3 ft.
  **Verified** (NASA data), as closely as NASA's simulations agree with each other.
- Case 02 (JSBSim's own file) for scale: rates differ from NASA by 0.12 to 0.45 deg/s, 100 times NASA's own
  spread. That is JSBSim's default rotational integrator at dt 0.01 s, the same figure attempt 1 measured. It is
  upstream physics and not a baseline matter.

### Criterion 7: the script sweep

**Correction to what I told the user.** `jsbsim-data/scripts/` holds 63 files, not 63 scripts: 61 `.xml` and 2
`.kml`. Three of the `.xml` files are helper files with no `<runscript>` (`kml_output`, `plotfile`,
`unitconversions`). So there are 58 scripts. All 61 `.xml` files were run; the sweep is the 59 other than
c1723 and f16_test.

| Outcome | Count |
|---|---|
| Runs, and meets its line in the first second | 52 |
| of these: no ground contact, frozen Class S passes | 25 |
| of these: ground contact, judged on Class N (16 of them fail the frozen Class S; kept in the table) | 27 |
| Fails in native and fails the same way in wasm (the 3 helper files at load; `737_cruise_steady_turn_simplex` at step 12: "No property simulation/do_simplex_trim") | 4 |
| Not comparable (RNG) | 0 |
| **Fails a frozen line** (`c3104`, `c3105`, `mk82_script`) | **3** |

- Every script: wasm-EH = JS-EH bit for bit; each side run twice identical; turbulence off on every row.
- Random elements were listed and committed before the sweep (`tests/rng-elements.md`, commit `c39c942`).
- Table per script: `results/parity-sweep.md`. All **Supported.**

### The first failed line (criterion 4, slope-rest run, Class A), and Class N on the same run

Raw output: `results/ground.txt`, `results/diag-slope-first-difference.txt`. Test: `tests/ground.test.ts`.

Run: c172x on a 5° slope rising north, brakes on, 1200 steps at 1/120 s. Read back from the run: the ground under
the start point tilts 5° (4.83° from the geocentric vertical, which differs from the true vertical by 0.17° at
this latitude), the aircraft starts in the middle of the grid, all three wheels are on the ground at 10 s, pitch
is 7.1°, and it moves 0.012 ft in the last 5 s.

| Group | Largest wasm − native difference | Class A allowance | Frozen Class A | Native ensemble spread S | Class N (added) |
|---|---|---|---|---|---|
| Positions (5 columns) | 1.4e-8 ft | 1e-6 ft | pass | 3.0e-8 ft | pass (not widened) |
| Contact flags (6 columns) | 0 | equal | pass | 0 | pass |
| Heading `psi` | 1.8e-11 rad | 6.3e-9 rad | pass | 4.1e-11 rad | pass |
| Speeds u, v, w, vtrue | 6.5e-8 ft/s | 1e-9 ft/s | **FAIL** | 1.0e-7 ft/s | pass |
| Rates p, q, r | 1.2e-8 rad/s | 3e-11 to 1.7e-10 rad/s | **FAIL** | 1.8e-8 rad/s | pass |
| Angles `phi`, `theta` | 2.6e-9 rad | 9e-12 to 1.3e-10 rad | **FAIL** | 5.3e-9 rad | pass |
| Forces | 1.3e-4 lb | 1.5e-7 to 2.7e-6 lb | **FAIL** | 1.7e-4 lb | pass |
| Moments | 2.9e-4 lb·ft | 9.5e-8 to 2.3e-6 lb·ft | **FAIL** | 3.4e-4 lb·ft | pass |

Both wasm builds give the same numbers. Class N's closest column is the yaw moment at 0.41 of its allowance.
**Supported.**

The ensemble answers the question left open at the first stop: native with its start altitude moved by one last
digit differs from itself by as much as wasm differs from native, in every group. **Supported.**

The exact checks on the same run all pass (**Supported**): `-fwasm-exceptions` = `-fexceptions` bit for bit;
TypeScript-driven = C++ runner bit for bit; each side run twice gives the same trace; the assert-enabled native
build runs it with no assertion and gives the release build's trace.

**Cause, as traced** (flat ground, same aircraft, gear compression and gear force recorded):
- At row 0 (after `RunIC`) the two builds differ only at rounding level: longitude by 1 unit in the last place,
  ECEF x by 4.2e-9 ft, forces by 1 to 300 units in the last place.
- At row 1 the altitude differs by 3.7e-9 ft: exactly one unit in the last place of a number the size of the
  Earth's radius (2⁻²⁸ ft).
- At row 2 the right main gear's compression differs by 3.26e-9 ft and the gear force by 1.76e-5 lb. The c172x
  main gear spring is 5400 lb/ft, and 3.26e-9 ft × 5400 lb/ft = 1.76e-5 lb.

The frozen line was written wrongly by this session: on the ground it asks forces and speeds to agree more
closely than the position limit in the same line allows through a spring. It stays as written, with its FAIL.

### Results by criterion

**1. Pin and build: done except committing the binaries.**
- JSBSim v1.3.3 `66f7fafc`, unpatched (the build script refuses a clone with local changes). Emscripten 6.0.13.
  **Verified** (upstream tag; emcc version string).
- `jsbsim-data/` has the same git tree ids as upstream for all five folders and `COPYING`
  (`scripts/check-data.sh`, also `--committed`). **Verified** (upstream tree ids).
- Flags, read from `compile_commands.json` by `scripts/check-flags.mjs`: every one of 113 files (JSBSim, expat,
  MSIS, host) has `-O3`, the exception flag, `-ffp-contract=off`, no fast-math, in both wasm builds; the same for
  the two native builds. **Supported.**
- Fixed memory **16 MiB**, growth off. Reason: loading all 61 aircraft twice in one module takes the heap to
  3.34 MiB (`results/load-test.txt`); the test runner's longest trace needs about 7 MiB more. Whether this size
  suits the iPhone is criterion 9. Stack 1 MiB, as attempt 1 used; its depth of use was not measured
  (**Reasoned**; the test that would settle it: fill the stack with a pattern and read the high-water mark).
- A deliberately broken source file: `build.sh` exits 1 and leaves `dist-wasm/` unchanged
  (`results/build-selftest.txt`). **Supported.**
- A clean build in another folder gives byte-identical `fdm-weh.wasm`, `fdm-weh.mjs`, `fdm-jseh.wasm`,
  `fdm-jseh.mjs` (same file). **Supported.** The native answer key is not byte-identical between folders (not
  shipped; not investigated).
- Current binaries (not yet committed): `fdm-weh.wasm` 1,734,938 bytes `ab2357c8…`, `fdm-jseh.wasm` 2,236,922
  bytes `5631da24…`.

**2. Answer key: done.** `build/native/fdm_native` is built by the same `CMakeLists.txt` from the same `host/`
files with g++ 13.3, including the scenario runner. **Supported.**

**3. Wrapper: all frozen lines pass.**
- Native: `fdm_native --selftest`, 41 checks pass. Both wasm builds: `tests/wrapper.test.ts`, 22 tests pass.
  **Supported.**
- 20 create/load/step/destroy cycles: heap in use is 21,888 bytes after every cycle, growth 0
  (`results/wrapper-memory.txt`). **Supported.**
- The assert-enabled native build stops in the deliberate "non-finite state" check on an upstream assertion
  (`FGTable.cpp:650`, a table lookup fed NaN). Every check before it passes. That check needs NaN, so it cannot
  run with assertions on.

**4. Ground hook: one frozen line failed (above) and the run passes the added Class N; the other lines pass.**
- Flat grid = upstream default callback, bit for bit, natively, on the first 30 s of c1723 (3601 rows, rest and
  ground roll to 53 kt) and on NASA 02 (3001 rows). **Verified** (against upstream's own callback).
- Slope grids against the separate calculation, 20 points each, both directions, 5 × 9 grid: height within
  1.4e-14 ft, contact identical, normal within 1.7e-9, unit length within 2.2e-16, pointing up. **Supported.**
- The hook's call counter rises after load, after `RunIC` and after one step (26, 51, 63). **Supported.**
- Assert-enabled native build: the ground scenarios run with no assertion failure. **Supported.**

**5. Loop: all frozen lines pass.** `tests/loop.test.ts`, 10 tests: 120 steps for 1 s at 60 Hz; a 10 s frame
gives 8 steps and counts 9.93 s dropped; pause, 10 s, resume gives 0 catch-up steps; `prev`/`curr`/`alpha`; the
same handler passes the same protocol test in Node directly and in a `worker_threads` Worker, in both builds.
**Supported.** Running in a real browser Worker is not tested yet (criterion 9).

**6. Load test: passes.** `results/load-test.txt`, table `results/load-table.md`.
- 61 folders. 59 load natively, in wasm-EH and in JS-EH. The same 2 fail on all three with the same message:
  `LM` (the folder has no `LM.xml`) and `blank` (a template: "No metrics element was found"). No mismatch.
  **Supported**; attempt 1 found the same two.
- Information: 7 that load cannot run `RunIC` plus 10 steps with default initial conditions, identically on all
  three: `L17`, `Pterosaur`, `dr1`, `f104`, `fokker100`, `fokker50` (a property the aircraft file expects from
  FlightGear does not exist) and `ZLT-NT` (non-finite after 1 step).

**Comparator self-test:** 17 tests on synthetic traces pass (`tests/compare-selftest.test.ts`), written and run
before any native-against-wasm comparison; the Class N test was added with the Class N line. **Supported.**

### Mistakes made by this session so far (kept on record)

1. **Slope grid in the wrong place.** The first slope-rest run was not on a slope: c172x's start latitude in
   `reset00.xml` is geocentric, the grid uses geodetic latitude, so the grid was centred about 10 nm south and
   the aircraft stood on the grid's flat clamped edge. An information line (pitch 0.6° on a "5° slope") showed
   it. The grid position was corrected, and the test now reads back the ground tilt and grid position under the
   aircraft. The first run also failed Class A, in the same way.
2. **An extra check with a wrong limit.** A check I added (not a frozen line) compared the hook's output in wasm
   with native at 1e-12 relative. It failed at 1.5e-11: a last-digit difference in latitude moves the point by
   about 1e-11 of a grid cell. It now uses the frozen hook limits (1e-6 ft, 1e-6); the measured differences are
   3.5e-10 ft in height, 2.5e-16 in the normal and 4.2e-9 ft in the contact point.
3. **Two wrong expectations in my loop test** (not frozen lines): I assumed the start altitude reads exactly
   4000 ft (it reads 4000.016) and that the untrimmed aircraft descends in the first second (it climbs 7.6 ft).
   Both were sanity checks on the test itself and were corrected to "close to 4000 ft".
4. **Property rule.** The wrapper first refused properties that have never been written (for example
   `external_reactions/f00/magnitude`), treating them as folders. JSBSim creates some inputs that way. Fixed: only
   a node with children is a folder; a native and a wasm test cover it.
5. **Three frozen lines written wrongly** (all kept, with their results): Class A for ground contact (first
   stop); and, in the sweep, Class S for a model with a discontinuity inside the judged second, and "same step"
   for a script that ends in a numerical blow-up (second stop).
6. **Script count.** I told the user there are 63 scripts. There are 63 files, of which 58 are scripts.
