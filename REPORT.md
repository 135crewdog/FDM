# Evaluation: `@0x62/jsbsim-wasm` as the base for the iPhone flight-sim FDM

Date: 2026-11-15. Raw outputs: `results/`. How to rerun: `CLAUDE.md`.

## Summary

**Recommendation: compile JSBSim to WebAssembly ourselves. Do not build on `@0x62/jsbsim-wasm` as published.**

- The physics itself runs correctly in WebAssembly. Where a model loads, results match native JSBSim to rounding
  level. Runtime external forces work exactly as they do natively. The NASA tumbling-brick case matches native
  JSBSim to about 1e-13.
- But the package's build turns off C++ exception catching inside the JSBSim library. JSBSim uses
  try/catch in normal operation (for example, to decide whether `<default value="...">` holds a number or a
  property name). As a result **c172x, f16 and 20 other of the 60 bundled aircraft fail to load** in the package.
  All 22 load in native JSBSim. Error reports reach JavaScript only as a bare number with no message.
- On an iPhone (Safari 27.2), JSBSim takes **about 5 µs per step** for a c172x-based model, and about 60 µs with
  20 runtime forces set by name. That is well within budget even at 1000 Hz. Errors are caught, and the page keeps
  working after them.
- The package's label is also misleading. It says "1.2.4", but it is built from a JSBSim master commit
  (`1a2e114`, 15 Feb 2026, 27 commits before v1.3.0) and reports `1.2.5.dev1`. It is a beta from a single
  maintainer.
- The fix looks small: build `libJSBSim` with `-fexceptions` too, not only the binding file. That is a build-flag
  change, which is why compiling it ourselves is the better path. We can reuse the package's approach
  (Emscripten + embind, and a 99-line compatibility patch), pin a real JSBSim release tag, and add faster property
  access for the wing-strip forces. **Not verified here:** installing the Emscripten toolchain was blocked in this
  session, so the claim that a rebuild fixes loading is reasoned from the build files and the failure pattern, not
  tested.

## Setup

| Item | Value |
|---|---|
| WASM package | `@0x62/jsbsim-wasm` **1.2.4-beta.4** (exact pin; the only line published, all betas) |
| JSBSim inside it | commit `1a2e114d79af2430db02a4f7a4a85328cdc5d403` (master, 2026-02-15), per the package's `release/publish-metadata.json`; binary banner `v1.2.5.dev1 Feb 22 2026`. The `v1.2.4` tag (`e07a7d8`) is on a different branch and is **not** what was built. |
| Data files | Fetched by `scripts/fetch-jsbsim-data.sh` at that same commit `1a2e114` (matches the code better than the v1.2.4 tag). NASA brick files are fetched from tag `v1.3.2`, the first release that has them. All are git-ignored. |
| Answer key | `pip install jsbsim==1.3.0`, the nearest PyPI release (27 commits after `1a2e114`; the source differences are mostly logging and trim). |
| Node / Python | Node 22.23, Python 3.13 (Linux x86-64) |

## Finding 0: many aircraft do not load (blocks tests 1 and 4 as specified)

`cmake/CMakeLists.txt` in the package source puts `-fexceptions` only on the `jsbsim_wasm` target (the generated
binding file). `libJSBSim` is compiled without it. Emscripten's default then drops catch blocks, so any exception
that JSBSim throws and expects to catch itself escapes to JavaScript instead.

Example: `FGParameterValue` and `FGSwitch` first try to parse a value as a number. On `InvalidNumber` they treat it
as a property name. In the package, `<default value="guidance/wp-heading-rad"/>` aborts the load.

Load results for every folder in `aircraft/` (`loadModel`):

- **Fail in WASM, load natively (22):** c172x, f16, c310, X15, f22, p51d, ah1s, Concorde, F4N, f104,
  fokker100, dr1, global5000, Boeing314, Camel, F450, J246, Pterosaur, Short_S23, Submarine_Scout, ZLT-NT,
  weather-balloon. Typical error: `Expecting a numeric attribute value, but got: guidance/wp-heading-rad`.
- **Load (36):** c172p, c172r, c182, 737, 787-8, A320, B747, T37, T38, f15, J3Cub, pa28, ball, mk82 and others.
- `LM` and `blank` fail in both builds (loadModel returns false), so they are not counted.

Error handling in general:

- A load failure reaches JavaScript as `throw 602600`: a raw pointer, no `Error` object and no message.
  The test harness and the page decode the message by reading the C++ exception object out of WASM memory.
  That is a hack, not something to ship.
- On the positive side, the instance survives. After a failed load, the same instance loaded and flew another
  model (checked in Node and in desktop Chromium).

## Test 1: same results as native JSBSim

`c1723` (c172x) and `f16_test` (f16) **cannot run in the package** (Finding 0). As the closest stand-ins I used
`c1721.xml` (c172r takeoff) and `T38.xml` (jet runway/takeoff). Every step was logged in both builds.
Differences below are WASM minus native.

| Quantity | c1721 max abs diff | T38 max abs diff |
|---|---|---|
| altitude (ft) | 7.5e-9 | 7.5e-9 |
| true airspeed (kt) | 1.2e-8 | 1.1e-9 |
| alpha (rad) | 9.1e-6 | 1.5e-10 |
| beta (rad) | 4.8e-8 | 3.0e-12 |
| roll phi (rad) | 2.7e-10 | 2.8e-10 |
| pitch theta (rad) | 2.4e-10 | 1.1e-10 |
| heading psi (rad) | 1.3e-12 | 4.7e-12 |
| p (rad/s) | 2.1e-9 | 5.9e-9 |
| q (rad/s) | 1.0e-9 | 9.1e-10 |
| r (rad/s) | 9.4e-12 | 8.6e-12 |

Relative to each column's largest value, most columns are below 1e-6. A few exceed it:

- c1721: alpha 6e-6, airspeed 8e-6, beta 2e-6, p 2e-6.
- T38: p 6e-6.

**Why the results are not bit-identical:**

1. The differences start at rounding level. In T38, the first difference is 1 ulp in beta at step 5. It grows
   smoothly (1e-13 by 8 s, 2e-11 by 42 s) and jumps to about 1e-6 around lift-off (about 50 s), where ground
   contact amplifies small differences. A logic difference would appear as a sudden jump, not a 1-ulp seed.
2. In c1721, the initial altitude on the runway differs by 7.45e-9 ft, which is 2 ulps of the Earth radius
   (about 2.09e7 ft). This comes from the ECEF-to-geodetic conversion. The run starts at rest, where
   alpha = atan2(w, u) with u ≈ 0 is badly conditioned. That explains alpha's 9e-6 rad.
3. Likely causes: different math libraries (Emscripten's musl libm against glibc for sin, cos, atan2 and pow;
   these can differ in the last bit), different compilers and optimisation choices, and the 27-commit source gap
   between `1a2e114` and 1.3.0.

I could not separate these causes without a native build of `1a2e114`. Test 2 (no ground contact) shows the
in-flight level is about 1e-13 relative over 30 s.

**Speed (Node, including logging):** WASM is 2–3× slower than native (c1721: 35 µs vs 10 µs per step;
T38: 25 µs vs 12 µs).

## Test 2: external forces driven from JavaScript

The setup is a copy of **c172p** (c172x does not load), generated by `tests/extforce/make_aircraft.py`, with one
`<force frame="BODY">` in `<external_reactions>`. Before every step, JavaScript sets the force's
`location-x/y-in`, `location-z-in`, `x/y/z` and `magnitude` properties from a deterministic schedule. The schedule
uses only + − × ÷, so the inputs are bit-identical in JavaScript and Python. The run is 30 s at 120 Hz in the air.

- **Matches native:** the force and moment JSBSim reports (`forces/fb{x,y,z}-external-lbs`,
  `moments/{l,m,n}-external-lbsft`) are **bit-identical** at every step. The motion matches to ≤ 3.5e-12 relative
  (altitude 7.5e-9 ft, angles ≤ 7e-14 rad).
- **The force really changes the motion:** compared with the same run at magnitude 0, altitude differs by 13 ft,
  bank by 0.9°, and body rates by up to 0.017 rad/s.
- **Cost of 20 forces** (c172p + 20 forces, 6000 steps, best of 5):

| | WASM (Node) | native (Python) |
|---|---|---|
| no external forces | 14.1 µs/step | 7.8 µs/step |
| 20 forces defined, not updated | 13.9 µs/step | 8.2 µs/step |
| 20 forces, 7 properties each set every step | **139.8 µs/step** | 162 µs/step* |
| the 140 `setPropertyValue` calls alone | 123.6 µs/step | |

\* Most of the native figure is Python call overhead.

The physics of 20 forces costs nothing measurable. The roughly 125 µs comes almost entirely from 140 property
writes by name, about 0.9 µs each (a JavaScript-to-C++ string conversion plus a property-tree lookup on every call).
At 120 Hz that is about 1.5% of a core; at 1000 Hz it is about 13%. A self-built binding should give the wing-strip
model cached property handles or a single array write per step. The package's unreleased `main` branch has started
on "batched property access".

## Test 3: NASA check case 02 (tumbling brick, no damping)

NASA's data downloaded fine and is saved under `reference/nasa-checkcases/`. JSBSim's case files
(`check_cases/NASA_EOM_2015`) are newer than the package (v1.3.2). One change was needed: the brick's mass is
given in SLUG, and the SLUG→LBS conversion only arrived in v1.3.2. `tests/nasa/make_brick.py` rewrites it as
4.99999909 LBS, using v1.3.2's own conversion factor.

Maximum difference over 30 s against NASA's 5 solutions (NASA's spread = largest difference between any two NASA sims):

| Variable | NASA spread | WASM, JSBSim default | WASM, rate integrator = AB4 |
|---|---|---|---|
| p (deg/s) | 0.0030 | 0.29 | 0.00002–0.003 |
| q (deg/s) | 0.0047 | 0.44 | 0.00003–0.005 |
| r (deg/s) | 0.0012 | 0.12 | 0.00001–0.001 |
| roll (deg) | 3.7† | 1.8 | 0.10 (3.7 vs sim_02) |
| pitch (deg) | 3.4† | 1.2 | 0.05 |
| yaw (deg) | 1.3† | 2.5 | 0.025 |
| altitude (ft) | 0.0021 | 0.0012 | 0.0012 |
| ECEF X (ft) | 0.0015 | 0.67‡ | 0.67‡ |

† The Euler-angle spread comes from NASA's sim_02, which is an outlier. The others agree to about 0.01°.
‡ The X offset is constant from t = 0. JSBSim's `brick.xml` uses an equatorial radius 0.67 ft larger than NASA's.
Altitude and latitude/longitude agree.

- **WASM vs native JSBSim on this case:** identical, apart from yaw at 1.1e-13 deg.
- **WASM vs NASA:** with JSBSim's default rotational-rate integrator (1 = rectangular Euler, first order), body
  rates drift 0.1–0.45 deg/s over 30 s. The error is ten times smaller at dt = 0.001. Setting the property
  `simulation/integrator/rate/rotational = 5` (Adams-Bashforth 4) brings JSBSim inside NASA's spread. This is a
  JSBSim setting, not a WebAssembly issue. **We should set it in our models.**

## Test 4: iPhone page

The page is deployed by `.github/workflows/pages.yml` and built by `scripts/build-site.mjs`.
It shows the user agent and timer resolution, then:

1. tries the unmodified c172x and shows the caught error;
2. loads deliberately broken aircraft files (malformed XML, text where a number belongs, a missing aircraft)
   and checks that the same instance still works afterwards;
3. times 3000 steps after a 300-step warm-up at 1/120, 1/480 and 1/1000 s, with and without 20 forces updated
   every step.

Because c172x does not load, the timing uses **`c172x_noap`**: c172x with its GNCUtilities and Autopilot systems
and c172ap autopilot removed, and the three `ap/*` outputs the flight controls read held at 0. Aerodynamics, engine,
propeller and gear are untouched. The modification is stated in the file, as the GPL requires.

Desktop Chromium (headless, this container) for reference:

| Case | dt | avg µs/step | worst 25-step block µs/step |
|---|---|---|---|
| c172x_noap | 1/120 | 16.7 | 44 |
| c172x_noap | 1/480 | 13.0 | 28 |
| c172x_noap | 1/1000 | 11.7 | 20 |
| + 20 forces updated | 1/120 | 124 | 240 |
| + 20 forces updated | 1/480 | 135 | 188 |
| + 20 forces updated | 1/1000 | 126 | 212 |

**iPhone results** (Safari tab, not the home-screen PWA; pasted from the device on 2026-11-15):

- User agent: `Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/27.2 Mobile/15E148 Safari/604.1`.
  That is Safari 27.2. Newer iOS versions freeze the OS number in the user agent at 18_7.
- Screen 393×852 @3x; 4 cores reported; timer resolution 1 ms.
- The package loaded in 25 ms when cached and 623 ms on a cold load.
- A second run 20 minutes later gave the same results: averages within 0.5 µs/step (6.0/5.3/5.3 and 57.3/62.0/61.0 µs) and identical final states.

| Case | dt | avg µs/step | 3000 steps took |
|---|---|---|---|
| c172x_noap | 1/120 | **5.7** | 17 ms (25 s of flight) |
| c172x_noap | 1/480 | **5.0** | 15 ms |
| c172x_noap | 1/1000 | **5.0** | 15 ms |
| + 20 forces updated every step | 1/120 | **58.3** | 175 ms |
| + 20 forces updated every step | 1/480 | **62.0** | 186 ms |
| + 20 forces updated every step | 1/1000 | **59.7** | 179 ms |

- **Errors:** every load error was caught on the iPhone too (as a bare number; the page decoded the text). The same
  instance kept working after each failure, and the page stayed responsive.
- **Same results as desktop:** final altitude and airspeed in every timing run were identical to the desktop
  Chromium run, to the printed precision.
- **Speed:** the iPhone was about 2.5× faster than this container's Chromium, and faster than native JSBSim on
  this container's CPU. At 1000 Hz, JSBSim alone needs about 5 ms per simulated second (0.5% of a core). With 20
  forces set by name it needs about 60 ms per second (6%). At 120 Hz both are negligible.
- **Worst-case single steps** could not be measured: Safari's 1 ms timer resolution is coarser than a step.
  'Worst 1000 µs' and 'worst-25-block 40/80 µs' are just one timer tick landing inside a step or block. The only
  reliable bound is the averages. Measuring frame spikes properly would need many steps per timed batch, or a run
  inside a real frame loop.
- The 20-force cost is still about 90% property writes by name. Reducing this is a reason for our own binding,
  but even as it is, the cost is affordable.

## What it would take to build our own

- Emscripten build of a pinned JSBSim release tag, with `-fexceptions` (or `-fwasm-exceptions`) on **all** JSBSim
  code, and exceptions converted to JavaScript `Error`s carrying the message.
- An embind surface limited to what the game needs: load from an in-memory filesystem, run, get/set property, a
  cached property handle API or a bulk `Float64Array` exchange for the wing-strip forces, and integrator settings.
- Rerun tests 1–3 from this repository against it. The harness is independent of the package apart from
  `src/wasm.ts`.

## Not done / limits

- I did not verify that rebuilding with `-fexceptions` fixes loading, because the Emscripten toolchain download
  was blocked in this session.
- The answer key is JSBSim 1.3.0, not the exact `1a2e114` commit; there is no PyPI build of that commit.
- Test 1 used c1721 (c172r) and T38 instead of c1723 (c172x) and f16_test, which fail in the package.
