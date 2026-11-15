# FDM repository: notes for future sessions

Flight dynamics model for a flight-sim game that runs as a PWA on iPhone. The core is **JSBSim v1.3.3 compiled to
WebAssembly by us** (Emscripten 6.0.13). Read `REPORT-02.md` first (our build, tests, recommendation; its "Review outcome" section
withdraws the AB4 plan), then `REVIEW-codex-02.md` (independent review), then
`REPORT.md` (session 01, the evaluation of the `@0x62/jsbsim-wasm` package, now replaced).

## Rule: label every finding by strength of evidence
The user cannot check the physics themselves, so every report (REPORT-*.md) labels each finding:
- **Verified**: checked against an answer we did not produce (native JSBSim, NASA data, JSBSim source or
  history, published references, the user's own devices).
- **Supported**: our own test shows it, but there is no outside answer key.
- **Reasoned**: explanation or inference, not tested. Say what test would confirm or refute it.

Keep an "Evidence ledger" table near the top of each report. Rules that go with it:
- Never upgrade a label without new evidence.
- If a pass/fail yardstick or tolerance is changed after seeing results, say so in the ledger.
- When an explanation turns out wrong, say so plainly.
- Name, in each report, which claims an independent reviewer should check first.

## JSBSim data
JSBSim v1.3.3's `aircraft/`, `engine/`, `systems/`, `scripts/` and `check_cases/NASA_EOM_2015/` are committed in
`jsbsim-data/` (private, non-commercial project; the user's decision, 2026-11-15). Refresh with
`scripts/fetch-jsbsim-data.sh <tag>`. Test-generated copies (`aircraft/c172p_ext*`, `scripts/ext_*.xml`) are git-ignored.
NASA check-case reference data is in `reference/nasa-checkcases/`.

## Our build
- `wasm/CMakeLists.txt`: builds libJSBSim (as a subdirectory) plus `wasm/bindings.cpp`. The exception flag is put in
  `CMAKE_C_FLAGS`/`CMAKE_CXX_FLAGS` before `add_subdirectory`, so **all** JSBSim code gets it (JSBSim needs its own
  try/catch to load c172x, f16 and 20 others).
- Two variants: **`jsbsim-weh` (`-fwasm-exceptions`, the default)** and `jsbsim` (`-fexceptions`, kept for comparison).
  Bit-identical results; weh is smaller and about 2x faster on the iPhone (REPORT-02 test 6). Needs WebAssembly
  exception handling in the browser (Safari 15.2+).
- Built files are committed in `wasm/bin/` (`*.mjs`, `*.wasm`, `build-info.json` with the build version shown on the page).
- No JSBSim patches are needed for v1.3.3. Put any future ones in `wasm/patches/*.patch` (applied by the build script).

## Binding API (`src/jsbsim.ts`, browser-safe; Node helpers in `src/wasm.ts`)
```ts
const sim = await createSim();            // Node: loads wasm/bin/jsbsim-weh.mjs (JSBSIM_VARIANT=jsbsim for the other), copies jsbsim-data into MEMFS at /jsbsim
sim.loadScript("scripts/c1723.xml");      // or sim.loadModel("f16"); errors throw JSBSimError with JSBSim's message
sim.setIntegrators({ rateRotational: 5 });// AB4: NOT safe on the ground at any rate tested (REVIEW-codex-02); keep default (1) for now
sim.runIC(); sim.run(); sim.runSteps(n);  // run() returns false when a script ends
sim.getProperty(name); sim.setProperty(name, v);   // by name: ~1-2 us per call, fine for setup, not per step
const h = sim.handle(name); sim.get(h); sim.set(h, v);          // cached handle: ~45 ns per write
sim.bindInputs(names); sim.bindOutputs(names);                   // bulk: write sim.inputs (Float64Array),
sim.inputs.set(values); sim.step(1); sim.outputs;                // step(n), read sim.outputs
sim.reset();                              // fresh FGFDMExec, same files
```
Raw embind class: `wasm/bindings.cpp` (every call catches C++ exceptions and returns a status; no exception
crosses into JavaScript). Shared test helpers used by Node and the page: `src/checks.ts`.

## What was learned (sessions 01-02)
- Ours vs native `jsbsim==1.3.3`: same 59/61 aircraft load; bit-identical on the NASA brick and external forces;
  rounding-level on c1721/T38. c1723 and f16_test diverge from 1-ulp seeds (start altitude differs by 2 ulp of the
  Earth radius, different libm); native vs native with +1e-8 ft does the same. Compare within tolerances, not bits.
- JSBSim's noise uses `std::default_random_engine`/`std::normal_distribution` (implementation-defined): models with
  active noise cannot match native Linux (libstdc++) step for step.
- psi is reported in [0, 2pi): wrap angles before comparing.
- **Integrator: undecided. Keep JSBSim's default (Euler body rates) until a candidate passes gates written down
  before testing** (REPORT-02 "Review outcome"; Codex's "Tests to add").
  - Euler body rates are robust on the ground but ~100x outside NASA's spread on the brick (10x even at 1000 Hz).
  - AB4 (`simulation/integrator/rate/rotational = 5`) has body rates within ~1e-5 deg/s of NASA. But it **fails
    on the ground at every rate tested, including 1000 Hz**:
    - 5 aircraft never settle at rest;
    - 737 and AH-1S hard landings run away;
    - the f16 inverted impact runs away at 120/240 Hz.
    The earlier "fine at 480/1000 Hz" claim was wrong (one crash, one taxi).
  - Buss 2 attitude (`simulation/integrator/position/rotational = 7`) plus AB4/AB2 rates matches NASA attitude to
    about 1e-4 deg (Codex). It does not help the ground.
- Why AB4 chatters on the ground (REPORT-02, "Why AB4 misbehaves on the ground"):
  - `FGAccelerations::CalculateFrictionForces` sizes friction to cancel slip in one **Euler** step (`v/dt`).
    Under AB4 the 55/24 weight makes it overshoot.
  - JSBSim fixed this in 2010 (commit 53709ba8, integrator-aware friction). The 2011 refactor 40279c20 removed it.
  - PteroLabsAI/jsbsim PRs 12-13 (unreviewed fork) re-found it. They chose implicit-midpoint body rates instead.
  - Phase 2 options, in order:
    1. Restore the 2010 friction.
    2. Implicit midpoint.
    3. AB4 in the air, Euler on the ground.
  - The 2011 loss was a sequence: e67c5e42 moved and disabled the code, 85b3a574 re-enabled friction in the
    Euler-only form, and 40279c20 deleted it.
  - Restoring it also changes translation (default AB2), so it is not a no-op under Euler rotation.
  - f16 inverted-impact runaway: friction on the STRUCTURE contacts contributes (Codex ablation). The first
    invalid operation is still unknown.
  - `gear/wow` counts only BOGEY (wheel) contacts. Detect STRUCTURE contact separately.
- **Known defects, to fix before phase 2 builds on them** (REPORT-02 "Review outcome"):
  - Binding:
    - `hasProperty`, `get`, `readOutputs` and `bindList` can throw raw WebAssembly exceptions.
    - `std::string` throws show as "unknown C++ exception".
    - Read-only writes report success.
    - `reset()` keeps stale bulk arrays.
    - NaN or fractional handles become handle 0.
    - Bad integrator IDs and dt=0 are accepted.
  - Harness:
    - `tests/parity/compare.py` ignores NaN and truncates to the shorter log.
    - `scripts/run-tests.sh` tests 2-3 compare the default build with itself since the default changed (set
      `JSBSIM_VARIANT` explicitly).
    - `tests/ab4/rate_sweep.ts` "first non-finite" really means rates > 1e6.
  - Build: `scripts/build-wasm.sh` applies patches only on a fresh clone.
  - Runtime: the 737 needs npm `ws` (missing).
  - Set dt **before** loading a model (FCS filters cache dt at load).
- Native runs write output files into the data root. These are git-ignored now; never commit them.
- Property writes by name are slow (~1.8 us each with -fexceptions); use handles or bulk for per-step traffic.
- `-fexceptions` costs ~50-100% per step vs no exceptions; `-fwasm-exceptions` costs nothing measurable.
- iPhone (Safari 27.2), weh build: unmodified c172x 8-13 us/step, f16 ~10.5 us/step, +20 forces by handle/bulk ~3 us;
  timer resolution 1 ms (time batches only).

## Parked for later: publishing (user's decision, 2026-11-15)
Revisit publishing only once we have a viable FDM that others could use for mobile flight sims. Do not post
anything publicly (issues, pull requests, packages) without the user's explicit go-ahead. Candidates when the
time comes:
- an issue or pull request to 0x62/jsbsim-wasm: build all of JSBSim with exception support, so 22 more aircraft
  load;
- a JSBSim-Team bug report: the integrator-aware friction from 2010 (53709ba8) was lost in 2011, and AB2-AB4 body
  rates never settle at rest. Include Codex's native reproduction, and a tested fix if session 03/04 produces one;
- the FDM itself, with its validation reports.

## How to run
```sh
npm ci
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # native answer key, jsbsim==1.3.3
scripts/run-tests.sh                  # tests 1-5 (session 02 results were produced with -fexceptions; weh is bit-identical) (or e.g. scripts/run-tests.sh 2 4); summaries to results/02-*, raw CSVs to out/
npx tsx tests/smoke.ts                # 2-second sanity check of the build
node scripts/build-site.mjs           # test page into site/ (ignored); serve with: python3 -m http.server -d site
npx tsc                               # typecheck
```
Rebuild the WebAssembly (only when changing the binding, JSBSim version or flags):
```sh
git clone https://github.com/emscripten-core/emsdk.git && emsdk/emsdk install 6.0.13 && emsdk/emsdk activate 6.0.13
source emsdk/emsdk_env.sh
scripts/build-wasm.sh                 # both variants -> wasm/bin/ (JSBSim source cloned into build/, ignored)
```

## Layout
- `wasm/`: CMake build, binding, patches, built files. `scripts/build-wasm.sh`: pinned versions (JSBSim tag, Emscripten).
- `src/jsbsim.ts` wrapper, `src/wasm.ts` Node helpers, `src/checks.ts` shared checks (load matrix, force timing).
- `tests/loadmatrix/` test 1, `tests/parity/` test 2, `tests/extforce/` test 3, `tests/nasa/` test 4, `tests/ab4/` test 5.
- `tests/review/` and `results/review-codex-02/`: Codex's review tests and results (e.g. `ground_matrix.py`, a native
  stress matrix of 6 aircraft × 5 scenarios × 2 rates × 2 integrators).
- `web/` page source (TypeScript, bundled by esbuild in `scripts/build-site.mjs`); `.github/workflows/pages.yml` deploys
  it from `main` to https://135crewdog.github.io/FDM/.
- `results/02-*` session 02 summaries; `results/session01/` session 01's.
- `prompts/`: prompts for other agents (e.g. `codex-review-02.md`, independent review of session 02). An independent
  review should be repeated after phase 2's integrator decision, before the hybrid wing-strip work builds on it.
