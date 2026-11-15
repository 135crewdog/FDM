# Session 02: our own WebAssembly build of JSBSim v1.3.3

Date: 2026-11-15. Raw outputs: `results/02-*.txt`. How to rebuild and rerun: `CLAUDE.md`.

## Summary

**Recommendation: yes, our build is ready to be the FDM core,** with two settings decided by the tests below:
run AB4 only at 480 Hz or faster, and use cached handles or the bulk array for the wing-strip forces.

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
    is moved by 1e-8 ft, so the cause is the scripts' sensitivity, not our build.
- **Fast property access works.** Writing 140 values (20 forces × 7) per step costs:

  | Method | Cost per step |
  |---|---|
  | by name | 247 µs |
  | cached handle | 6.3 µs |
  | one bulk array | 4.8 µs |

  End states are identical with all three methods.
- **AB4 lands on NASA's spread** (ratio 1.00–1.01 at 100 Hz). It is within 1e-6 deg/s of two NASA sims at
  480–1000 Hz. The default integrator is about 100× outside the spread at 100 Hz, and still 10× outside at 1000 Hz.
- **AB4 has a side effect at low rates.** At 120 and 240 Hz it blows up to NaN when the f16 hits the ground
  inverted. At 120 Hz it makes the f16's body rates jitter 36× more while taxiing. At 480 and 1000 Hz both
  problems go away. Native JSBSim does exactly the same, so this is JSBSim's AB4, not our build.
- **`-fwasm-exceptions` is faster.** Results are bit-identical to `-fexceptions`, and the file is smaller
  (1.69 MB against 2.15 MB). It runs 1.2–1.8× faster in Node and in desktop Chromium. `-fexceptions` costs
  about 50% per step compared with a build without exceptions; `-fwasm-exceptions` costs nothing measurable.
  The iPhone decides the default (Test 6).

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
- **Proof:** native JSBSim against itself, with the starting altitude moved by 1e-8 ft, diverges the same way.
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

## Test 6: iPhone page

Page: **https://135crewdog.github.io/FDM/** (deployed from `main` by `.github/workflows/pages.yml`).

- The top line shows `Build fdm-wasm-20261115.1447 · built 2026-11-15T14:47:47Z`. If you see anything else, the
  page is a stale cached copy. Asset URLs carry `?v=<build>`.
- The page auto-runs the default `-fexceptions` build. A second button runs the `-fwasm-exceptions` build.
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

**iPhone results: pending.** The `-fwasm-exceptions` run on Safari is also pending.

## Not done / limits

- JSBSim's physics was not changed. The binding only calls the public API.
- The random-number difference (Test 2) is documented, not patched.
- Single-step worst-case timing on the iPhone still cannot be measured (1 ms timer). The page times whole
  batches.
- No GitHub Actions build workflow was added, because building here worked. `scripts/build-wasm.sh` rebuilds
  with the pinned versions.
