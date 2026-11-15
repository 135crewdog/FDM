# Session 02: our own WebAssembly build of JSBSim v1.3.3

Date: 2026-11-15. Raw outputs: `results/02-*.txt`. How to rebuild and rerun: `CLAUDE.md`.

> **Later work:** the defects listed under "Review outcome" were fixed in session 03, and the floor and the first
> integrator candidate were tested against written gates. See `REPORT-03.md` and `GATES.md`.

## Summary

> **Correction after independent review (Codex, 2026-11-15; `REVIEW-codex-02.md`).** The AB4 recommendation
> below was **wrong** and is withdrawn. AB4 also fails at 480 and 1000 Hz on other aircraft (737 and AH-1S hard
> landings), and resting aircraft never settle with AB4 even at 1000 Hz. Claude re-ran these cases in native JSBSim
> and got the same numbers. The integrator is **undecided**; see "Review outcome" below. The build itself, the
> load matrix, native parity in controlled flight and the `-fwasm-exceptions` choice stand.

**Recommendation: our build is ready to be the FDM core.** The integrator choice is still open. How strong each
finding is (Verified, Supported or Reasoned) is listed in the **Evidence ledger** after the review outcome:

1. Use the `-fwasm-exceptions` build. It is now the default (`wasm/bin/jsbsim-weh.*`).
2. ~~Run AB4 only at 480 Hz or faster.~~ **Withdrawn.** Keep JSBSim's default (Euler) body-rate integrator until a
   candidate passes the gates in "Review outcome".
3. Use cached handles or the bulk array for the wing-strip forces.
4. Fix the binding and test-harness defects found in review before phase 2 builds on them.

On the iPhone, the `-fwasm-exceptions` build runs the unmodified c172x at 8–13 µs per step and the f16 at about
10.5 µs. 20 forces by handle or bulk add about 3 µs. At 1000 Hz that is about 1% of one core.

- **Built here, no patches.** JSBSim v1.3.3 compiles with Emscripten 6.0.13 as it is. Exception support is
  on for all code, including libJSBSim and expat. A full build takes about 45 s.
- **Every aircraft that loads natively loads in ours:** 59 of 61, the same 59 as native `jsbsim==1.3.3`.
  That includes c172x, f16 and the other 20 that failed in the `@0x62` package. LM and blank fail in both.
- **Errors are now JavaScript `Error`s with JSBSim's message**, for example `JSBSimError: loadModel(broken_value):
  Expecting a numeric attribute value, but got: not-a-number`. The instance keeps working afterwards.
- **Same results as native:**
  - Bit-identical on the NASA brick, and on forces and moments set from JavaScript.
  - Rounding-level on c1721 and T38.
  - c1723 and f16_test drift further apart. Native drifts the same way against itself when its starting altitude
    is moved by 1e-8 ft. That shows the scripts are sensitive, but it does **not prove** our build has no small
    error (corrected after review). Codex's new controlled-flight comparisons (c172x and f16, Euler and AB4) agree
    with native to 4e-9 ft.
- **Fast property access works.** Writing 140 values (20 forces × 7) per step costs:

  | Method | Cost per step |
  |---|---|
  | by name | 247 µs |
  | cached handle | 6.3 µs |
  | one bulk array | 4.8 µs |

  End states are identical with all three methods.
- **AB4's body rates are very close to NASA's** (within 2–6e-5 deg/s of three NASA sims at 100 Hz, about 1e-6 at
  480–1000 Hz). The default integrator is about 100× outside NASA's spread at 100 Hz, and still 10× outside at
  1000 Hz. Corrected after review: the ratio used below is a distance, not a "within the spread" test, and
  attitude errors remain about 0.01–0.1° because attitude still uses Euler.
- **AB4 fails on the ground.** At 120 and 240 Hz it runs away (rates above 1e6 rad/s, then NaN) when the f16
  hits the ground inverted. At 120 Hz it makes the f16's body rates jitter 36× more while taxiing. Native JSBSim
  does exactly the same, so this is JSBSim's AB4, not our build. **Withdrawn after review:** the original claim
  "at 480 and 1000 Hz both problems go away" was based on one crash and one taxi and is wrong (see "Review
  outcome").
  - The taxi chatter has a known cause. JSBSim's friction solver assumes Euler. It was made integrator-aware in
    2010, and that code was lost in a 2011 refactor.
  - Options for phase 2 are listed in the section "Why AB4 misbehaves on the ground".
- **`-fwasm-exceptions` is the default now.** Results are bit-identical to `-fexceptions`, and the file is smaller
  (1.69 MB against 2.15 MB).
  - Speed: **about 2× faster on the iPhone** (c172x 7.7 µs per step at 1000 Hz, against 16.3), and 1.2–1.8× in
    Node and desktop Chromium.
  - Aircraft load about 3× faster.
  - No failures on any platform. End states are identical.
  - `-fexceptions` is kept in `wasm/bin/` for comparison.

## Review outcome (Codex, 2026-11-15)

An independent review by Codex is in `REVIEW-codex-02.md`. Its tests are in `tests/review/` and its raw results
in `results/review-codex-02/`. Its verdict: **keep the build; do not adopt the integrator plan.**

Claude re-ran the decisive cases in native JSBSim 1.3.3 and checked the binding defects. Every one reproduced
exactly:

| Case (native JSBSim 1.3.3) | AB4 | Euler (default) |
|---|---|---|
| c172x resting on its gear, 1000 Hz, peak body rate in the last 10 of 60 s | 0.008 rad/s (never settles) | 4.4e-9 rad/s |
| 737 hard landing (40 ft, 30 ft/s down), 480 Hz | runaway at 7.18 s, NaN at 7.19 s | not run here (Codex: finite) |
| 737 hard landing, 1000 Hz | runaway at 5.41 s, NaN at 5.42 s | finite for 15 s |
| AH-1S hard landing, 1000 Hz | runaway at 5.85 s, NaN at 5.86 s | finite for 15 s |

**Corrections to this report** (each also marked where it occurs):

1. "AB4 is fine at 480 Hz or faster" is **wrong**. It rested on one crash (f16) and one taxi. Five aircraft never
   settle at rest with AB4, even at 1000 Hz, and the 737 and AH-1S hard landings blow up at 480 and 1000 Hz.
2. The "first non-finite" times in Test 5 were the times the rates passed 1e6 rad/s. The first actual NaN comes
   a few steps later.
3. The 1e-8 ft nudge test shows the scripts are sensitive. It is **not proof** that our build is free of small
   errors.
4. "Restoring the 2010 friction fix changes nothing under Euler" is **wrong**. The fix also covers translation,
   whose default integrator is AB2.
5. The 2011 history is more detailed:
   - `e67c5e42` (17 July 2011) moved the integrator-aware code and disabled it.
   - `85b3a574` (24 July) re-enabled friction with the Euler-only form.
   - `40279c20` (14 August) deleted the already-disabled code.
   The conclusion stands: the fix was lost, not replaced.
6. The NASA ratio is a distance measure, not a "within the spread" test. AB4 rates fall outside NASA's pointwise
   min/max envelope at about half the samples, by tiny amounts.
7. `gear/wow` counts only wheel (BOGEY) contacts, so the ground/air split in Test 5 can label wingtip or tail
   contact as airborne.
8. The f16 crash NaN is not "stiff springs". In Codex's test, removing only the friction on the STRUCTURE contact
   points (from just before impact) kept both the 120 and 240 Hz runs finite. Friction contributes to the
   runaway. The exact first invalid operation is still unknown.

**Defects found in our code (to fix at the start of phase 2):**

- Binding:
  - `hasProperty` (and the unguarded `get`, `readOutputs` and `bindList` paths) can throw a raw WebAssembly
    exception instead of a `JSBSimError`.
  - Bad property paths give "unknown C++ exception": JSBSim throws `std::string`, which our guard does not decode.
  - Writes to read-only properties report success.
  - `reset()` leaves the old bulk-array lengths and values.
  - Handles given as `NaN`, fractions or values ≥ 2³² silently become handle 0.
  - Invalid integrator IDs and a zero dt are accepted silently.
- Test harness:
  - `tests/parity/compare.py` truncates to the shorter log and ignores NaN. It reported zero difference for a NaN
    log.
  - Since the default build changed, `scripts/run-tests.sh` compares the default build with itself in Tests 2
    and 3. The saved results predate that change and are valid; **re-runs are not**.
  - Benchmarks compare different states, and the "no external forces" case actually has one force.
- Build and runtime:
  - `scripts/build-wasm.sh` applies patches only on a fresh clone, so a new patch could be silently skipped.
  - The 737 needs the npm package `ws` (socket input), which is not in `package.json`.
  - Changing dt after loading a model does not re-time its control-system filters. Set dt before loading.
- Data hygiene (found by Claude afterwards): native runs wrote output files into `jsbsim-data/`, and four were
  committed (`JSBout172B.csv`, two `initfile.*.xml`, `check_cases/NASA_EOM_2015/Atmos_02_JSBSim.csv`). They have
  been removed and git-ignored. All of JSBSim's v1.3.3 data files were compared byte for byte with upstream and
  are unchanged.

**New candidate from the review:** JSBSim's built-in Buss 2 quaternion attitude integrator
(`simulation/integrator/position/rotational = 7`), combined with AB4 or AB2 body rates, cut the NASA attitude
error from about 0.02° to 2e-5–9e-5° at 480 Hz. It does nothing for the ground problem, and AB2 rates still
mismatch the friction solver.

**The integrator decision is open.**

- Euler body rates are robust on the ground, but far from NASA's answers in the air.
- AB4 is accurate in the air, but fails on the ground.

Candidates for phase 2:

1. Restore the 2010 integrator-aware friction.
2. Implicit-midpoint body rates (PteroLabs fork).
3. Switch integrators on contact. This must detect every contact type, not `gear/wow`.
4. Add Buss 2 attitude to whichever survives.

Every candidate must pass gates written down **before** testing. Codex proposes these in its "Tests to add":

- 60 s at rest on c172x, f16, c310, AH-1S and 737, with body rates below 1e-6 rad/s in the last 10 s;
- hard landings and attitude sweeps with every state finite;
- NASA full state, with rate error below 2e-6 deg/s and attitude error below 1e-3° at 480 Hz or faster;
- rigid-body energy and momentum checks;
- a ground energy balance.

**What the next reviewer should check first:** the phase 2 integrator decision against the gates above, and the
binding and harness fixes.

## Evidence ledger

Every finding carries one of three labels (rule in `CLAUDE.md`):

- **Verified:** checked against an answer we did not produce, such as native JSBSim, NASA's data, JSBSim's
  source or history, or the user's own devices.
- **Supported:** our own test shows it, but there is no outside answer key.
- **Reasoned:** an explanation or inference that has not been tested. Treat it as a guess until a test exists.

| # | Finding | Label | Evidence |
|---|---|---|---|
| 1 | 59/61 aircraft load, the same set as native | Verified | Test 1, against native jsbsim 1.3.3 |
| 2 | Errors arrive as `JSBSimError` with JSBSim's message; the instance survives | Verified | Test 1 and page section 2, on 3 platforms including the user's iPhone and Mac |
| 3 | Bit-identical to native on the NASA brick and on external forces | Verified | Tests 3 and 4, step-by-step comparison with native |
| 4 | c1721 and T38 match native at rounding level | Verified | Test 2 |
| 5 | c1723 and f16_test differences come from script sensitivity, not our build | Supported (sensitivity); not proven (no build error) | Native against itself with +1e-8 ft diverges the same way (Test 2). Review: a small systematic error could also grow smoothly. Codex's controlled flights agree with native to 4e-9 ft (Verified), which strengthens confidence in the build, but the c1723 divergence is not located. |
| 6 | The 1-ulp seed comes from ECEF-to-geodetic in a different maths library | Reasoned | Not traced to a specific function |
| 7 | Noisy models cannot match native Linux step for step (`std::default_random_engine`) | Reasoned | From the C++ standard and JSBSim's source; no model tested where noise matters |
| 8 | Handle and bulk writes are about 40–50× cheaper than by name | Verified | Test 3 and page timing on the user's iPhone and Mac |
| 9 | `-fwasm-exceptions` gives bit-identical results and is about 2× faster on the iPhone | Verified | Test 2 logs and the user's iPhone runs |
| 10 | `-fwasm-exceptions` costs "nothing measurable" against a build without exceptions | Reasoned | Compared with session 01's package, which used a different JSBSim version and model. Not a like-for-like test. |
| 11 | AB4 body **rates** are within 2–6e-5 deg/s of NASA sims (100 Hz); the default is ~100× outside the spread (10× at 1000 Hz) | Verified (re-checked by Codex against a fresh NASA download) | Test 4. The "inside spread" yardstick was changed to a ratio **after** the first version said "NO". Review: the ratio is a distance, not containment; AB4 rates leave NASA's pointwise envelope at about half the samples (by tiny amounts). Attitude stays 0.01–0.1° off (Euler attitude). |
| 12 | ~~AB4 is safe on the ground at 480/1000 Hz~~ **Wrong** | Verified wrong | f16_test runaway at 120/240 Hz is real (native too), but 737 and AH-1S hard landings run away with AB4 at 480 and 1000 Hz; Euler survives (Codex matrix; re-run by Claude). |
| 13 | AB4 makes gear contact chatter, and it does not go away at 1000 Hz | Verified (native) | Codex: 5 aircraft at rest 60 s never settle with AB4 (c172x 0.008 rad/s at 1000 Hz vs 4e-9 Euler; re-run by Claude). |
| 14 | Chatter is caused by the friction solver assuming an Euler step | Supported | JSBSim source read (verified); the 2010 upstream fix and the fork's independent test agree. Not tested by us. |
| 15 | Chatter size scales with step because the friction limit caps it | Reasoned | Rest amplitudes roughly halve from 480 to 1000 Hz in Codex's matrix, consistent but not tested as a mechanism |
| 16 | AB2 (default for translation) may explain creep at rest | Reasoned | Linearized calculation only |
| 17 | ~~The crash NaN comes from stiff STRUCTURE contact springs~~ | Weakened | Codex: zeroing only STRUCTURE friction before impact keeps the f16 finite at 120/240 Hz, so friction contributes; first invalid operation not located |
| 18 | The 2010 fix existed and was lost in 2011 | Verified | Commits 53709ba8 (2010), e67c5e42 (moved and disabled), 85b3a574 (Euler form re-enabled), 40279c20 (deleted); Codex `source-history.txt` |
| 19 | PteroLabs fork results (implicit midpoint, NASA within 0.0012 deg/s) | Reported by others | One unreviewed author; not run by us |
| 20 | The gap to session 01's 5 µs per step is mainly the autopilot and guidance systems | Reasoned | Not measured (no c172x_noap run with the new build) |
| 21 | The 0.67 ft ECEF X offset on the brick comes from the planet radius in `brick.xml` | Verified | Codex: the offset is already in the initial geometry (20955646.9951 vs NASA 20955646.3253 ft) |
| 22 | Binding: every error becomes a `JSBSimError`; writes and resets behave | **Wrong** | Codex binding probes, re-run by Claude: raw exception from `hasProperty`, silent read-only writes, stale bulk arrays after `reset()`, `NaN` handle → handle 0 |
| 23 | The parity comparator would catch a broken run | **Wrong** | `compare.py` reported zero difference and exit 0 for a one-row NaN log (Codex probe, re-run by Claude) |
| 24 | Buss 2 attitude integrator with AB4/AB2 rates matches NASA attitude to 2e-5–9e-5° at 480 Hz | Verified (Codex, against NASA data); not re-run by Claude | `results/review-codex-02/nasa-integrators.txt` |

## Build

| Item | Value |
|---|---|
| JSBSim | tag **v1.3.3**, commit `66f7fafc07fe13e7ede9db20873030fed2881713` (2026-10-16) |
| Emscripten | **6.0.13** via emsdk. 7.0.0 exists, but it was released 9 days ago and is a major version bump. |
| Patches | **none needed**. v1.3.3 compiles unpatched. `wasm/patches/` is empty; `scripts/build-wasm.sh` applies any `*.patch` placed there. |
| Flags | `-fexceptions` (or `-fwasm-exceptions`) in `CMAKE_C_FLAGS`/`CMAKE_CXX_FLAGS` **before** `add_subdirectory(jsbsim)`, so libJSBSim and expat get it (checked in the generated `flags.make`). `-O3`, single-threaded, `MODULARIZE`, `EXPORT_ES6`, `ALLOW_MEMORY_GROWTH`. |
| Output | `wasm/bin/jsbsim.{mjs,wasm}` (2.15 MB wasm), `wasm/bin/jsbsim-weh.{mjs,wasm}` (1.69 MB), `build-info.json`. Committed. |
| Build version | `fdm-wasm-20261115.1447` (shown at the top of the test page) |
| Toolchain access | emsdk, its Google Storage downloads and github.com all worked in this session. GitHub Actions was not needed. |
| JSBSim data | v1.3.3 `aircraft/`, `engine/`, `systems/`, `scripts/` and `check_cases/NASA_EOM_2015/`, committed in `jsbsim-data/` (5 MB) |

**Binding** (`wasm/bindings.cpp`, about 200 lines, embind). It does not touch physics; it only calls
FGFDMExec's public API.

- Loading and running: `init(root)` (same set-up as the Python package), `loadModel`, `loadScript`, `runIC`,
  `run`, `runSteps(n)`.
- Properties by name: `getProperty` and `setProperty`.
- Cached handles: `handle(name)` once, then `get(h)` and `set(h, v)`.
- Bulk exchange: `bindInputs` and `bindOutputs` once; then each step write the inputs `Float64Array`, call
  `step(n)`, and read the outputs `Float64Array`.
- Error handling: every call catches C++ exceptions and returns a status code. The TypeScript wrapper
  (`src/jsbsim.ts`) throws a `JSBSimError` carrying the C++ message. A load that returns `false` (no exception)
  throws as well, with JSBSim's last console lines as the message.
- Integrators: `setIntegrators({ rateRotational: 5 })` sets the `simulation/integrator/...` properties.

## Test 1: every aircraft loads (`results/02-test1-loadmatrix.txt`)

| | loads | fails |
|---|---|---|
| native jsbsim 1.3.3 | 59 | LM (folder has no `LM.xml`), blank (template, no version) |
| ours, `-fexceptions` | 59 | same two, same messages |
| ours, `-fwasm-exceptions` | 59 | same two |

**PASS.** The package failed 22 of these (c172x, f16, c310, X15, f22, p51d, …). All load now.

## Test 2: same results as native (`results/02-test2-parity.txt`)

Every step was logged in both builds. Differences are ours minus native.

| Script | Agreement | Notes |
|---|---|---|
| c1721 (c172r takeoff, 10 s) | max alpha 9e-6 rad, altitude 7.5e-9 ft, attitude ≤ 3e-10 rad | Same as session 01. Alpha is badly conditioned at standstill. |
| T38 (100 s) | first difference 1 ulp at step 5; ≤ 1.7e-6 relative after lift-off | Same as session 01 |
| f16_test (700 s) | **up to the first ground impact at 127.9 s:** altitude 7.6e-4 ft, attitude ≤ 6e-8 rad, rates ≤ 3e-8 rad/s | After that it diverges (altitude up to 119 ft) |
| c1723 (c172x take-off with autopilot, 200 s) | first 3 s: alpha 3e-6, others ≤ 1e-8 | Grows from t ≈ 3.3 s on the take-off roll. Later max: bank 0.015 rad, altitude 0.24 ft. |

**Why c1723 and f16_test are not at rounding level.** Both runs start about 1 ulp apart: the starting altitude
differs by 7.45e-9 ft, which is 2 ulp of the Earth radius. This comes from the ECEF-to-geodetic conversion in a
different maths library. The scripts then amplify that difference:

- **f16_test** takes off, rolls inverted, and **hits the ground upside down at 128 s and again at 180 s**. Both
  runs end at rest in the same place.
- **c1723**'s ground roll with the wing-leveler autopilot is sensitive from about 3 s.
- **Evidence (called "proof" originally; corrected after review: it shows sensitivity, not the absence of a
  small error in our build):** native JSBSim against itself, with the starting altitude moved by 1e-8 ft,
  diverges the same way.
  - f16_test: altitude 117.7 ft (ours: 119.3 ft), from the same times.
  - c1723: same onset at t ≈ 3.3 s, same growth pattern, about 5× smaller peak.

  A logic difference would show up as a sudden jump, not as a 1-ulp seed that grows.
- `-fwasm-exceptions` and `-fexceptions` give **bit-identical** logs for both scripts.

**Random numbers (a known limit, not a bug).** JSBSim draws sensor noise from `std::default_random_engine` and
`std::normal_distribution`. Both are implementation-defined. Native Linux uses libstdc++ and Emscripten uses
libc++, so a model whose noise really reaches the dynamics cannot match native Linux step for step. In c1723 the
autopilot's noise sensor feeds a 12-bit quantizer whose step (0.0015 rad) is larger than the noise, so removing
the noise changed nothing: the log was bit-identical. If we ever need exact noise across platforms, the fix is a
small patch that uses an explicit engine and distribution.

The heading `psi` is reported in [0, 2π), so 0 and 6.283 are the same heading. The comparison scripts now wrap
angles before taking differences.

## Test 3: outside-force hook (`results/02-test3-extforce.txt`)

c172p plus 1 runtime force, 30 s at 120 Hz, with the same schedule as session 01:

- The external forces and moments JSBSim reports are **bit-identical** to native at every step. Motion agrees
  to ≤ 3.5e-12 relative.
- The force really moves the aircraft: altitude changes by 13 ft and bank by 0.9° compared with magnitude 0.

20 forces, 7 values each written before every step. Node, best of 5 × 6000 steps, µs per step:

| | ours `-fexceptions` | ours `-fwasm-exceptions` | native (Python) |
|---|---|---|---|
| no external forces | 21.6 | 14.2 | 7.3 |
| 20 forces, not updated | 18.6 | 13.5 | 7.4 |
| 20 forces by **name** (140 `setProperty`) | 312 | 151 | 126 (mostly Python overhead) |
| 20 forces by **cached handle** | **26.2** | **19.4** | |
| 20 forces by **bulk array** | **25.7** | **20.3** | |
| the 140 writes alone: name / handle / bulk | 247 / 6.3 / 4.8 | 155 / 3.9 / 2.1 | |

All three methods end in the bit-identical state. With handles or the bulk array, 20 forces add about 5 µs
per step instead of about 250 µs. Session 01's package took 124 µs for the writes by name, at 0.9 µs each.
Ours by name is slower, about 1.8 µs each with `-fexceptions`, because every call passes through a C++ try
block. That does not matter, because the hot path will use handles or bulk.

## Test 4: NASA case 02, tumbling brick (`results/02-test4-nasa.txt`)

This run uses JSBSim v1.3.3's own `check_cases/NASA_EOM_2015` files, **unchanged**: the SLUG mass loads and no
mass fix is needed.

- Ours and native are bit-identical, apart from yaw at 1.1e-13 deg.
- "worst/spread" means: the largest difference from any NASA sim, divided by the largest difference between any
  two NASA sims. A value of 1 or less means we are no farther from any NASA sim than they are from each other.

| | p | q | r | roll | pitch | yaw | altitude |
|---|---|---|---|---|---|---|---|
| default integrator, 100 Hz | 97 | 94 | 103 | 0.99 | 1.08 | 2.29 | 0.78 |
| **AB4, 100 Hz** | **1.00** | **1.00** | **1.00** | **1.00** | **1.01** | **1.01** | **0.78** |
| default, 480 Hz | 20 | 20 | 21 | | | | |
| default, 1000 Hz | 9.8 | 9.6 | 10.3 | | | | |
| AB4, 480 Hz / 1000 Hz | 1.00 | 1.00 | 1.00 | | | | |

- **With AB4, the body rates are within 2–6e-5 deg/s of NASA sims 01, 04 and 05 at 100 Hz.** At 480 and
  1000 Hz they are within 1e-6 deg/s of sims 01 and 04.
- The ratio of 1.00 comes entirely from the farthest sim (06); the spread is set by the distance between sims
  01 and 06.
- **AB4 lands inside NASA's spread** in the sense that matters: it sits on NASA's own solutions. The default
  integrator does not get there even at 1000 Hz.
- ECEF X has a constant 0.67 ft offset from t = 0 in every JSBSim run. Session 01 traced this to the planet
  radius in `brick.xml`. Altitude and longitude agree.

## Test 5: AB4 side effects (`results/02-test5-ab4.txt`)

> **Superseded after review.** The conclusion of this test ("AB4 only together with ≥ 480 Hz") is wrong; see
> "Review outcome". The measurements below are correct for the cases run. "First non-finite" in the sweep means
> "rates passed 1e6 rad/s"; the first actual NaN comes a few steps later.

AB4 (`simulation/integrator/rate/rotational = 5`) against the default (1), in our build, with native checked
too:

- **c1723 (c172x take-off, 120 Hz):** no noticeable change.
  - Lift-off is 0.12 s earlier with AB4.
  - Altitude at 200 s differs by 1 ft, which is the same size as the sensitivity seen in Test 2.
  - Peak body rate is 0.30 rad/s with AB4 against 0.25 rad/s with the default.
- **f16_test (120 Hz): AB4 blows up.** When the jet hits the ground inverted at 127.98 s, the body rates go to
  1e161 and then NaN. Native JSBSim 1.3.3 does exactly the same at the same moment. The default integrator
  survives the impact.
- **Rate sweep:** first non-finite time, peak |p, q, r|, and on-ground jitter:

| | 120 Hz | 240 Hz | 480 Hz | 1000 Hz |
|---|---|---|---|---|
| f16_test crash, default | finite, 19 rad/s | finite | finite | finite |
| f16_test crash, **AB4** | **NaN at 127.98 s** | **NaN at 128.03 s** | finite, 31 rad/s | finite, 15 rad/s |
| f16_runway_test taxi, peak \|pqr\|, default | 0.0076 | 0.0075 | 0.0075 | 0.0075 |
| f16_runway_test taxi, peak \|pqr\|, **AB4** | **0.277** | 0.091 | 0.042 | 0.017 |
| c1723, peak \|pqr\|, default / AB4 | 0.25 / 0.30 | 0.25 / 0.25 | 0.25 / 0.25 | 0.25 / 0.25 |

Reading: AB4 is a multi-step method with a small stability region. Stiff gear contact (and a hard impact above
all) at a large step goes outside it. At 120 Hz on the ground it makes the gear chatter (36× the default's body
rates). At 480 Hz and above, the crash stays finite and the chatter falls to 2–5× the default. **So: AB4 only
together with ≥ 480 Hz.** At 120 Hz the default integrator is the safer choice. The iPhone cost of 480–1000 Hz is
small (session 01: about 5 µs per step).

## Why AB4 misbehaves on the ground: cause, history and options

Added after the tests, following the user's question about JSBSim's known weaknesses on the ground.

### Cause, from JSBSim v1.3.3's source

`FGAccelerations::CalculateFrictionForces` computes wheel friction with Lagrange multipliers (Catto's method). It
picks the force that brings the sliding velocity to zero in exactly one step:

```
vdot += v / dt
wdot += pqr / dt
```

That assumes the next velocity update is an Euler step, `v + dt * vdot`. With AB4, the integrator weights the new
derivative by 55/24 and adds history terms, so the correction overshoots. A linearized check shows how a small
slip evolves from step to step, without the friction limit:

| Integrator | Largest root (growth of a small slip per step) |
|---|---|
| Euler | 0: cancelled in one step |
| AB2 | 1.0: never dies out |
| AB3 | 1.8 |
| AB4 | 2.5 |

- Euler is JSBSim's default for rotation, which hides the problem.
- AB2 is the default for translation. It is only just stable in this sense, which may explain the slow creep at
  rest that JSBSim users report. This is an inference, not tested.
- The friction limit (friction coefficient × normal load) caps the oscillation. Our reading is that this turns it
  into a bounded chatter whose size scales with the step. This matches our f16 taxi peaks of 0.28, 0.09, 0.04 and
  0.017 rad/s at 120, 240, 480 and 1000 Hz, but no source reports it.

### JSBSim history (checked in the upstream repository)

- **2010:** commit `53709ba8` (Bertrand Coconnier): *"Friction forces computation is now taking the integration
  schemes into account for more stable forces while at rest."*
  - It divided the correction by the scheme's leading weight: 24/55 for AB4, 12/23 for AB3, 2/3 for AB2.
  - It also subtracted the history terms.
  - Its comment said Catto's method "only supports Euler integration scheme", and that handling the multistep
    schemes "significantly helps stabilizing the friction forces".
- **2011:** commit `40279c20` (Jon Berndt): *"Removed most external dependencies from ground reactions"* deleted
  this code (`EvaluateRateToResistTo`).
  - The message does not mention it, and nothing in that commit replaces it.
  - v1.3.3 has the Euler-only form.
  - **The problem was solved upstream and then apparently lost in a refactor.**

### Independent confirmation (PteroLabsAI fork of JSBSim, October 2026; one author, unreviewed, not upstream)

- **PR #12** (closed):
  - **Diagnosis:** same as ours. A c172x on its gear at 240 Hz never settles. After 50 s it still turns at 4e-4,
    2e-2 and 3e-2 rad/s with AB2, AB3 and AB4.
  - **Fix:** restoring the 2010 weights; all schemes then settle below 1e-6 rad/s.
- **PR #13** (merged in the fork), which replaced #12:
  - An implicit midpoint integrator, made the default for body rates.
  - It conserves rotational energy and angular momentum for a free body.
  - It keeps NASA's brick within 0.0012 deg/s at 240 Hz; NASA's own spread is 0.004.
  - The authors report the c172x, F450, ah1s and c310 rest and land as they do under Euler.
  - It falls back to Euler if a step diverges.
- We have not tested either change.

### FlightGear and older JSBSim documentation

- Jitter and drift at rest were addressed long ago by:
  - reorganizing the gear code;
  - ramping wind and turbulence in with speed;
  - a steering filter tuned for 120 Hz.
- FlightGear uses the default Euler rotation, so it would not meet this AB4 interaction. We found no FlightGear
  documentation of it.

### Not explained by any source

The NaN on the f16's inverted ground impact at 120 and 240 Hz. The f16 has stiff STRUCTURE contact points on its
wingtips and fin top (spring 10,000 lbs/ft), and AB4 tolerates far less stiffness per step than Euler. The
contact springs may be the cause, possibly together with the friction overshoot. This is not isolated yet.

### Options for phase 2 (to test in this order)

1. **Restore the 2010 integrator-aware friction.** It is a small patch from JSBSim's own history. (Corrected after
   review: it is not a no-op under Euler, because it also covers translation, whose default integrator is AB2.)
2. **Implicit-midpoint body rates** (PteroLabs #13). It is a larger patch, but it addresses NASA accuracy, energy
   and the ground together.
3. **AB4 in the air, Euler while any contact point touches the ground** (the integrator can be switched at run
   time). No patch, but multistep history makes the switch itself a transient.

Each option is to be judged on:

- f16_runway_test chatter and f16_test impact at 120–1000 Hz;
- a c172x resting on its gear for 60 s;
- NASA case 02;
- an energy check (engine off, total energy must not increase).

Sources:

- JSBSim commits 53709ba8 and 40279c20 (github.com/JSBSim-Team/jsbsim).
- github.com/PteroLabsAI/jsbsim pull requests 12 and 13.
- JSBSim Newsletter 2.4 (jsbsim.sourceforge.net/Newsletter_2_4.pdf).
- FlightGear wiki "JSBSim GroundReactions".
- Berndt & De Marco, AIAA 2009-5699.

## Test 6: iPhone page

Page: **https://135crewdog.github.io/FDM/** (deployed from `main` by `.github/workflows/pages.yml`).

- The top line shows `Build fdm-wasm-20261115.1447 · built 2026-11-15T14:47:47Z`. If you see anything else, the
  page is a stale cached copy. Asset URLs carry `?v=<build>`.
- The page auto-runs the default build: `-fexceptions` when these tests were run, `-fwasm-exceptions` since the
  decision below. A second button runs the other build.
- What it shows:
  - Environment details.
  - The full load matrix, with pass or fail and the message for each aircraft.
  - Error handling (malformed XML, text where a number belongs, missing aircraft), then the same instance flying.
  - µs per step for the **unmodified c172x** (reset01, in the air) and **f16** (our airborne init file:
    10,000 ft, 400 kt, engine running) at 1/120, 1/480 and 1/1000 s.
  - c172x with 20 forces: none, by name, by handle and bulk at the same three rates.

Desktop Chromium (headless, this container), µs per step (`results/02-test6-page-chromium-*.txt`):

| | `-fexceptions` | `-fwasm-exceptions` |
|---|---|---|
| load matrix | 59/61, PASS | 59/61, PASS |
| c172x 1/120, 1/480, 1/1000 | 46.8, 30.7, 26.5 | 39.7, 21.2, 16.2 |
| f16 1/120, 1/480, 1/1000 | 34.3, 46.3, 28.7 | 19.4, 18.8, 17.5 |
| 20 forces at 1/1000: none / name / handle / bulk | 24.4 / 241 / 32.5 / 31.0 | 15.4 / 110 / 24.5 / 17.9 |

The end states are identical in both builds and with all force methods.

**Mac, Safari 27.0.1** (macOS, 8 cores, timer 1 ms; pasted by the user 2026-11-15; `-fexceptions` build):

- Load matrix 59/61, PASS, with the same two failures and messages as native.
- Errors: all three are `JSBSimError`s with JSBSim's message, and the same instance flew afterwards.
- End states are identical to desktop Chromium in every timing run.
- Data download 955 ms; module plus files into memory 744 ms (first visit).

| | 1/120 | 1/480 | 1/1000 |
|---|---|---|---|
| c172x, µs/step | 36.7 | 23.3 | 21.7 |
| f16, µs/step | 27.3 | 27.3 | 26.7 |
| 20 forces: none / name / handle / bulk | 32.3 / 318 / 36.7 / 35.3 | 23.3 / 311 / 27.7 / 26.3 | 21.7 / 305 / 26.0 / 25.0 |

**iPhone, Safari 27.2** (iOS UA frozen at 18_7, 393×852 @3x, 4 cores, timer 1 ms; pasted 2026-11-15; `-fexceptions` build):

- Load matrix 59/61, PASS, with the same failures and messages as native.
- Errors: all three are `JSBSimError`s with JSBSim's message, and the same instance flew afterwards.
- End states are identical to the Mac and to desktop Chromium.
- Data 347 ms; module plus files into memory 453 ms.

| | 1/120 | 1/480 | 1/1000 |
|---|---|---|---|
| c172x, µs/step | 26.7 | 17.3 | 16.3 |
| f16, µs/step | 20.0 | 20.3 | 20.3 |
| 20 forces: none / name / handle / bulk | 24.3 / 271 / 30.0 / 28.3 | 18.3 / 264 / 22.7 / 21.7 | 17.3 / 264 / 22.3 / 21.7 |

Reading:

- At 1000 Hz, the unmodified c172x or f16 with 20 forces by handle or bulk needs about 22 ms per simulated
  second, about 2% of one core.
- Handle and bulk add about 4–5 µs per step for 20 forces; by name adds about 245 µs.
- Session 01's c172x_noap took about 5 µs per step on the same phone. That model had no autopilot or guidance
  systems, and the package build had no exception support. Today's c172x is the full model and uses
  `-fexceptions`, which costs about 50% per step in Node. The `-fwasm-exceptions` run on the iPhone will show
  how much of the gap comes from the exception mode.

**iPhone, Safari 27.2, `-fwasm-exceptions` build** (same phone, pasted 2026-11-15):

- Load matrix 59/61, PASS. Errors and recovery are the same as with `-fexceptions`.
- End states are identical to the `-fexceptions` run.
- Loading all 59 aircraft took about 3× less time (c172x 4 ms against 12 ms; f16 4 ms against 11 ms).

| µs per step | 1/120 | 1/480 | 1/1000 |
|---|---|---|---|
| c172x: `-fwasm-exceptions` / `-fexceptions` | **13.0** / 26.7 | **9.0** / 17.3 | **7.7** / 16.3 |
| f16: `-fwasm-exceptions` / `-fexceptions` | **10.7** / 20.0 | **10.3** / 20.3 | **10.7** / 20.3 |
| 20 forces with `-fwasm-exceptions`: none / name / handle / bulk | 11.0 / 70.3 / 15.0 / 13.7 | 9.0 / 68.0 / 12.0 / 11.3 | 8.7 / 65.7 / 11.7 / 11.3 |

**Decision: `-fwasm-exceptions` becomes the default.** It shows a clear gain (about 2×) with no failures, which
was the agreed condition.

- Changed: `createSim()` in Node, and the page now auto-runs `jsbsim-weh`.
- At 1000 Hz, the c172x with 20 strip forces by bulk array needs about 11 ms per simulated second on the iPhone,
  about 1% of one core.
- The rest of the gap to session 01's 5 µs per step is probably the autopilot and guidance systems, which that
  model lacked. This is Reasoned, not measured (ledger #20).
- Requirement: WebAssembly exception handling, which Safari has had since 15.2.

## Not done / limits

- JSBSim's physics was not changed. The binding only calls the public API.
- The random-number difference (Test 2) is documented, not patched.
- Single-step worst-case timing on the iPhone still cannot be measured (1 ms timer). The page times whole
  batches.
- No GitHub Actions build workflow was added, because building here worked. `scripts/build-wasm.sh` rebuilds
  with the pinned versions.
