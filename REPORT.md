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

---

## Part 3. Results

(Filled in as the work proceeds.)
