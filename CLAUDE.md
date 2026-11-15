# FDM repository: notes for future sessions

Flight dynamics model for a flight-sim game that runs as a PWA on iPhone. The core is **JSBSim v1.3.3 compiled to
WebAssembly by us** (Emscripten 6.0.13). Read in this order:
1. `REPORT-04.md`: later gates, candidates 2 and 3, the integrator recommendation, and what was found about the
   ground model. **Start here.**
2. `GATES.md`, `GATES-04.md`, `GATES-04b.md`: the gates, and the rule that they are never changed after a result.
3. `REPORT-03.md` (defect fixes, first gates, candidate 1; several of its ground explanations are corrected in
   REPORT-04 "Earlier explanations that turned out wrong").
4. `REPORT-02.md` (our build and tests) and `REVIEW-codex-02.md` (independent review of session 02).
5. `REPORT.md` (session 01, the evaluation of the `@0x62/jsbsim-wasm` package, now replaced).

## Chats and prompts (`prompts/README.md`)
The repository is the project's memory; a chat is only where one piece of work happens.
- Every chat is named `FDM <number> <kind>: <topic>`, e.g. `FDM 04 Work: integrator decision`. The number is the
  session number (same as `REPORT-04.md`, `prompts/04-*.md`, `results/04-*`). Kinds: `Work` (Claude Code on the
  repository), `Review` (independent review, Codex), `Plan` (regular Claude chat; cannot see the repository).
- At the start of a session, rename the chat to the name in its prompt (or ask the user to, in the first line).
- Every work session ends by writing the prompt for the next chat, with its chat name at the top and "Name this
  chat ..." as the first instruction, and by adding a row to the table in `prompts/README.md`.
- Next: `prompts/codex-review-04.md` (independent review of sessions 03 and 04), then
  `prompts/05-ground-model-and-default.md`.

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

## Rule: gates before candidates (`GATES.md`)
- The gate files are frozen: `tests/gates/gates.json`, `run_native.py`, `run_wasm.ts`, `evaluate.py`,
  `fixtures/brick_poi.xml`, `tests/parity/compare.py`, `GATES.md`. Committed as `164c1d0` before anything was run.
- Never edit a gate, tolerance or yardstick after seeing a result. If a gate is wrong: say so, keep the result, add a
  new gate with a new name (G5b, G7, ...) and commit it before the next candidate runs.
- Also frozen (session 04): `tests/gates/gates-04.json`, `run_native_04.py`, `run_wasm_04.ts`, `evaluate_04.py`,
  `GATES-04.md` (commit `e5bcd1d`: G5b, G2b, G3b, judged at 480 and 1000 Hz) and `gates-04b.json`,
  `run_native_04b.py`, `run_wasm_04b.ts`, `evaluate_04b.py`, `GATES-04b.md` (commit `9fb7f63`: G2c).
- `tests/gates/run.sh`, `run-later.sh` and `run-forward.sh` refuse to run if the frozen files are uncommitted or
  changed.
- New candidates go into `tests/gates/configs.json` (not frozen).
- **Check what a scenario really does before trusting its name.** G2's "hard landing, 100 ft/s forward" was flown
  backward by four of five aircraft for two sessions (the scenario set the velocity north; the start files face
  south). Read the body-axis velocity, the attitude and the height from the simulation, not from the description.
- **"Finite" is not "sane".** A run can stay finite while the aircraft is 150 ft under the ground or thrown to
  1,000 ft. Gates on the ground need conditions on height, attitude and energy.
- Do not change JSBSim's physics except through `wasm/patches/*.patch`: small, explained in its header, switched by a
  property that defaults to "unchanged JSBSim", and proven bit-identical when off (`tests/native/verify_key.sh
  patched unpatched`, `tests/native/verify_wasm_patch_off.sh`).

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
- Built files are committed in `wasm/bin/` (`*.mjs`, `*.wasm`, `build-info.json` with the build version, patch hashes
  and binary hashes). Two builds of the same source differ in a few hundred bytes (JSBSim embeds the build time).
- **Patches** live in `wasm/patches/*.patch`. `scripts/lib-jsbsim-src.sh` resets the pinned source and re-applies them on
  every build, the same way for WebAssembly (`scripts/build-wasm.sh`) and for the native answer key
  (`scripts/build-native.sh`). `PATCHSET=unpatched scripts/build-wasm.sh` builds without them into
  `build/wasm-bin-unpatched/`. A wrong Emscripten version stops the build.
- **`wasm/bin` contains patches 0001, 0002 and 0003, all switched off** (bit-identical to unpatched JSBSim when
  off: REPORT-04 ledger 2).
  - 0001 `simulation/integrator/friction-aware`: 0 = JSBSim unchanged (default), 1 = integrator-aware friction
    (candidate 1), 2 = the 2010 code's formula (comparison only).
  - 0002 `simulation/integrator/rate/rotational` = 10: implicit-midpoint body rates (candidate 2; PteroLabsAI/jsbsim
    PR 13, commit 33384d9, unchanged plus counters under `simulation/integrator/midpoint/`).
  - 0003 `simulation/integrator/rate/rotational-on-contact`: -1 = no switching (default); an integrator id (1 =
    Euler) = that scheme integrates the body rates while any contact point (BOGEY or STRUCTURE) touches
    (candidate 3). Also `.../contact-hold-sec` (default 0), `.../contact-release-mode` (1 = restart the multistep
    history on release, default), and read-only `.../contact-active`, `.../contact-switches`.
  - A patch's header text is part of its hash, and the hashes are in every result file: do not edit a patch
    (even its comments) without rebuilding and re-running what depends on it.
- **Native answer key:** `pip jsbsim==1.3.3` cannot carry patches. `scripts/build-native.sh` builds the Python module
  from source into `build/native/unpatched` and `build/native/patched`; use `PYTHONPATH=build/native/<set>`. The
  unpatched build is bit-identical to pip on everything compared (REPORT-03, ledger 4).

## Binding API (`src/jsbsim.ts`, browser-safe; Node helpers in `src/wasm.ts`)
```ts
const sim = await createSim();            // Node: loads wasm/bin/jsbsim-weh.mjs (JSBSIM_VARIANT=jsbsim for the other), copies jsbsim-data into MEMFS at /jsbsim
sim.dt = 1 / 480;                         // BEFORE loading (filters cache dt at load); after load it throws (setDtAfterLoad to force)
sim.loadScript("scripts/c1723.xml");      // or sim.loadModel("f16"); sim.loadIC("reset00"); errors throw JSBSimError with JSBSim's message
sim.setIntegrators({ rateRotational: 5, positionRotational: 7, rateRotationalOnContact: 1 });  // the configuration recommended in
                                          // REPORT-04 (not the default yet). Unknown ids throw. AB4 alone is fragile on the ground.
sim.runIC(); sim.run(); sim.runSteps(n);  // run() returns false when a script ends
sim.getProperty(name); sim.setProperty(name, v);   // by name: ~1-2 us per call, fine for setup, not per step
const h = sim.handle(name); sim.get(h); sim.set(h, v);          // cached handle: ~45 ns per write
sim.bindInputs(names); sim.bindOutputs(names);                   // bulk: write sim.inputs (Float64Array),
sim.inputs.set(values); sim.step(1); sim.outputs;                // step(n), read sim.outputs
sim.reset();                              // fresh FGFDMExec, same files; ALL earlier handles become invalid, bulk bindings empty
```
Raw embind class: `wasm/bindings.cpp`. Contract (tested by `tests/binding/regress.ts`, 80 checks, both variants):
- Every public call catches every C++ exception (`std::string` and `const char*` too) and returns a status; the
  wrapper throws `JSBSimError` with JSBSim's message. Nothing else is ever thrown.
- Nothing fails silently: read-only writes, invalid handles (NaN, fractions, out of range, from before `reset()`),
  bad dt, unknown integrator ids and bad step counts all throw.
- Handles are numbers (generation x 2^20 + index). Re-read `sim.inputs`/`sim.outputs` after `reset()`, binding, or
  anything that can allocate.
- Socket input (`<input port=...>` in aircraft files) is disabled in our runtime, so no npm `ws` is needed.
- `setProperty` still creates a missing property (as JSBSim does); `handle()` and bulk binding do not.

Shared test helpers used by Node and the page: `src/checks.ts`. Node helpers: `src/wasm.ts` (`JSBSIM_VARIANT`,
`JSBSIM_BIN` to use another build directory, `describeBuild()` for the hash line).

## What was learned (sessions 01-04)
- Ours vs native `jsbsim==1.3.3`: same 59/61 aircraft load; bit-identical on the NASA brick and external forces;
  rounding-level on c1721/T38. c1723 and f16_test diverge from 1-ulp seeds (start altitude differs by 2 ulp of the
  Earth radius, different libm); native vs native with +1e-8 ft does the same. Compare within tolerances, not bits.
- JSBSim's noise uses `std::default_random_engine`/`std::normal_distribution` (implementation-defined): models with
  active noise cannot match native Linux (libstdc++) step for step.
- psi is reported in [0, 2pi): wrap angles before comparing.
- **Integrator (session 04): recommended, not yet the default.** Gates and results: `GATES*.md`, REPORT-04,
  `results/04-gates-summary.txt`.
  - **Recommended to carry forward: `c3-ab4` at 480 Hz** = AB4 body rates in the air, Euler while any contact point
    touches (patch 0003), Buss 2 attitude (`position/rotational` = 7), friction as in JSBSim. It needs patch 0003 only.
  - **The shipped default is still JSBSim's** (Euler body rates). By the rule nothing passes every gate: every
    configuration fails the hard-landing gate, through the 737 and ah1s only. Do not change the default until a
    landing gate that tests landings exists and `c3-ab4` passes it (session 05).
  - At 480 and 1000 Hz (judged rates; 120 and 240 Hz are reported only):

    | | G1 Rest | Landings: c172x, f16, c310 | Landings: 737, ah1s | Crash cases against the floor | G4 NASA | G5b Energy | G6 Parity |
    |---|---|---|---|---|---|---|---|
    | Floor (Euler + Buss 2) | pass | all runs | fail | reference | fail (0.09, 0.04 deg/s) | fail | pass |
    | Candidate 1 (patch 0001 + AB4) | pass | all runs | fail | worse | pass | pass | pass |
    | Candidate 2 (midpoint, patch 0002) | pass | all runs | fail | same at 480, worse at 1000 | fail (1.0e-5, 2.3e-6; gate 2e-6) | pass (1e-14) | pass |
    | Candidate 3 (`c3-ab4`, patch 0003) | pass | all runs | fail | same at 480, worse at 1000 | pass (1.4e-6, 3.2e-7) | pass | pass |

  - AB3 in the air fails G5b (a real, slow drift); AB2 fails G4. Candidate 3 with patch 0001 added is no better.
  - Candidate 3 is exactly "the floor while touching, AB4 while flying" (bit-identical on both sides, REPORT-04
    ledger 16). Its switch adds no kick and does not flap in real landings.
  - Candidate 2 never took a failure path in 3.7 million steps; if Newton ever failed it would throw. It would
    become the simplest choice if G4's limit were relaxed (the user's decision, REPORT-04 "What would change it").
  - No configuration costs measurably more per step.
- **What the ground problem really is** (REPORT-04; this replaces REPORT-03's reading):
  - **Unlimited wheel compression.** `FGLGear.cpp` computes a BOGEY's strut compression as
    `height * normalZ / LGearProj` and divides the force by `LGearProj` again; nothing limits either. With the
    aircraft tipped over, inverted or under the surface, a wheel reports tens to millions of feet and pushes with
    millions of pounds for one step. 60 of 60 failed runs checked start this way. No integrator survives that.
    Fix candidates for session 05: a patch that limits it, complete airframe (STRUCTURE) contact points on the
    aircraft, crash detection in the wrapper.
  - **Test aircraft matter.** The 737 has three wheels and no airframe contact points: it tips onto its tail and
    sinks through the ground. The ah1s with its rotor stopped tumbles before it touches. Neither can test a
    landing. The c172x, f16 and c310 land and stay upright in every run, at every rate, with every configuration
    (13,104 runs).
  - **Gear dampers and stability at rest.** A stiff damper needs a small enough step: the c310 at 120 Hz tolerates
    0.71 (AB4), 1.20 (AB3), 1.81 (AB2), 2.58 (Euler) times its own damping; the limit doubles with the step rate.
    This explains session 03's one G1 failure. It does **not** explain the landing failures (softer dampers make
    them worse). `tests/gates/diag/gear_damper.py`.
  - Friction: `FGAccelerations::CalculateFrictionForces` assumes an Euler step. JSBSim fixed this in 2010 (53709ba8)
    and lost it in 2011. Patch 0001 restores it, adapted. Not needed with Euler on contact.
  - `gear/wow` counts only BOGEY contacts. Read every point: `gear/unit[k]/WOW` and `contact/unit[k]/WOW`.
  - G5 with AB4 fails only through JSBSim's multistep start-up (first 4 steps); G5b (from 1 s) passes.
- Defects from the review of session 02 are fixed (REPORT-03 step 1). Still open: no memory-leak audit; `setProperty`
  by name creates missing properties; patch 0001's mathematics is unreviewed.
- `.gitignore` used to ignore every directory named `build`, so `tests/build/selftest_patches.sh` was never
  committed in session 03. It now ignores only `/build/`. After adding a file, check `git status` shows it.
- Set dt **before** loading a model (FCS filters cache dt at load). The binding now enforces it.
- Native JSBSim writes output files into its data root unless told otherwise. Every native runner must go through
  `tests/pylib/native.py` (`new_fdm()` sets a scratch output path); `scripts/run-tests.sh` fails if anything appears
  in `jsbsim-data/`.
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
scripts/run-tests.sh                  # tests 0-5 (0 = binding, comparator and build self-tests); or e.g. scripts/run-tests.sh 0 2
                                      # NATIVE=pip|unpatched|patched picks the answer key; SESSION=04 writes results/04-*
                                      # (the default prefix is still 03); raw CSVs go to out/
scripts/build-native.sh               # native answer keys from source -> build/native/{unpatched,patched}
tests/gates/run.sh floor              # G1-G6 (about 2 min) -> results/04-gates-<config>.txt   (the floor first)
tests/gates/run-later.sh floor        # G5b, G2b, G3b (about 3 min) -> results/04-later-<config>.txt
tests/gates/run-forward.sh floor      # G2c and the verdict per step rate, both ways -> results/04-forward-<config>.txt
.venv/bin/python tests/gates/summary_04.py floor c1-ab4 c2-mid c3-ab4   # one table (summary.py: session 03's table)
npx tsx tests/smoke.ts                # 2-second sanity check of the build
node scripts/build-site.mjs           # test page into site/ (ignored); serve with: python3 -m http.server -d site
npx tsc                               # typecheck
```
Rebuild the WebAssembly (only when changing the binding, JSBSim version or flags):
```sh
git clone https://github.com/emscripten-core/emsdk.git && emsdk/emsdk install 6.0.13 && emsdk/emsdk activate 6.0.13
source emsdk/emsdk_env.sh
scripts/build-wasm.sh                 # both variants, with wasm/patches -> wasm/bin/ (JSBSim source cloned into build/, ignored)
PATCHSET=unpatched scripts/build-wasm.sh   # without patches -> build/wasm-bin-unpatched/ (needed to run the floor)
```

## Layout
- `wasm/`: CMake build, binding, patches, built files. `scripts/build-wasm.sh`: pinned versions (JSBSim tag, Emscripten).
- `src/jsbsim.ts` wrapper, `src/wasm.ts` Node helpers, `src/checks.ts` shared checks (load matrix, force timing).
- `tests/loadmatrix/` test 1, `tests/parity/` test 2 (and the strict comparator `compare.py`), `tests/extforce/`
  test 3, `tests/nasa/` test 4, `tests/ab4/` test 5.
- `tests/binding/` binding regression tests; `tests/build/` patch and build self-test; `tests/pylib/native.py` shared
  set-up for native runs; `tests/native/` answer-key checks.
- `tests/gates/`: the gates (`gates.json`, `gates-04.json`, `gates-04b.json`, runners, evaluators, `run.sh`,
  `run-later.sh`, `run-forward.sh`, `summary.py`, `summary_04.py`), candidate list (`configs.json`), diagnostics
  (`diag/`: `gear_damper.py`, `landing_anatomy.py`, `blowup_cause.py`, `midpoint_counters.py`, `contact_switch.py`,
  `confirm_rate.py`). `wasm/patches/`: JSBSim patches.
- `tests/review/` and `results/review-codex-02/`: Codex's review tests and results (e.g. `ground_matrix.py`, a native
  stress matrix of 6 aircraft × 5 scenarios × 2 rates × 2 integrators).
- `web/` page source (TypeScript, bundled by esbuild in `scripts/build-site.mjs`); `.github/workflows/pages.yml` deploys
  it from `main` to https://135crewdog.github.io/FDM/.
- `results/04-*` session 04 (`04-gates-*`, `04-later-*`, `04-forward-*` are the gate reports, `04-diag-*` the
  diagnostics); `results/03-*` session 03; `results/02-*` session 02; `results/session01/` session 01.
- `prompts/`: one prompt per chat, and `README.md` with the chat naming convention and the list of sessions
  (e.g. `05-ground-model-and-default.md`; `codex-review-04.md`, independent review of sessions 03 and 04). The
  review should be done before session 05, and before the hybrid wing-strip work builds on the integrator choice.
