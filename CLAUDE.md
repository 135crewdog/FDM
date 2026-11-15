# FDM repository: notes for future sessions

Flight dynamics model for a flight-sim game that runs as a PWA on iPhone. The core is **JSBSim v1.3.3 compiled to
WebAssembly by us** (Emscripten 6.0.13). Read in this order:
1. `REPORT-03.md`: defect fixes, the acceptance gates, the floor and candidate 1 against them. **Start here.**
2. `GATES.md`: the gates every integrator candidate must pass, and the rule that they are never changed after a result.
3. `REPORT-02.md` (our build and tests; its "Review outcome" withdraws the AB4 plan) and `REVIEW-codex-02.md`
   (independent review).
4. `REPORT.md` (session 01, the evaluation of the `@0x62/jsbsim-wasm` package, now replaced).

## Chats and prompts (`prompts/README.md`)
The repository is the project's memory; a chat is only where one piece of work happens.
- Every chat is named `FDM <number> <kind>: <topic>`, e.g. `FDM 04 Work: integrator decision`. The number is the
  session number (same as `REPORT-04.md`, `prompts/04-*.md`, `results/04-*`). Kinds: `Work` (Claude Code on the
  repository), `Review` (independent review, Codex), `Plan` (regular Claude chat; cannot see the repository).
- At the start of a session, rename the chat to the name in its prompt (or ask the user to, in the first line).
- Every work session ends by writing the prompt for the next chat, with its chat name at the top and "Name this
  chat ..." as the first instruction, and by adding a row to the table in `prompts/README.md`.
- Next: `prompts/04-integrator-decision.md`.

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
- `tests/gates/run.sh <config>` refuses to run a candidate if the frozen files are uncommitted or changed.
- New candidates go into `tests/gates/configs.json` (not frozen).
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
- **`wasm/bin` contains patch 0001, switched off.** `simulation/integrator/friction-aware`: 0 = JSBSim unchanged
  (default), 1 = integrator-aware friction (candidate 1), 2 = the 2010 code's formula (comparison only).
- **Native answer key:** `pip jsbsim==1.3.3` cannot carry patches. `scripts/build-native.sh` builds the Python module
  from source into `build/native/unpatched` and `build/native/patched`; use `PYTHONPATH=build/native/<set>`. The
  unpatched build is bit-identical to pip on everything compared (REPORT-03, ledger 4).

## Binding API (`src/jsbsim.ts`, browser-safe; Node helpers in `src/wasm.ts`)
```ts
const sim = await createSim();            // Node: loads wasm/bin/jsbsim-weh.mjs (JSBSIM_VARIANT=jsbsim for the other), copies jsbsim-data into MEMFS at /jsbsim
sim.dt = 1 / 480;                         // BEFORE loading (filters cache dt at load); after load it throws (setDtAfterLoad to force)
sim.loadScript("scripts/c1723.xml");      // or sim.loadModel("f16"); sim.loadIC("reset00"); errors throw JSBSimError with JSBSim's message
sim.setIntegrators({ rateRotational: 5 });// unknown ids throw. AB4/AB3 are NOT safe on the ground (REPORT-03); keep default (1) for now
sim.runIC(); sim.run(); sim.runSteps(n);  // run() returns false when a script ends
sim.getProperty(name); sim.setProperty(name, v);   // by name: ~1-2 us per call, fine for setup, not per step
const h = sim.handle(name); sim.get(h); sim.set(h, v);          // cached handle: ~45 ns per write
sim.bindInputs(names); sim.bindOutputs(names);                   // bulk: write sim.inputs (Float64Array),
sim.inputs.set(values); sim.step(1); sim.outputs;                // step(n), read sim.outputs
sim.reset();                              // fresh FGFDMExec, same files; ALL earlier handles become invalid, bulk bindings empty
```
Raw embind class: `wasm/bindings.cpp`. Contract (tested by `tests/binding/regress.ts`, 75 checks, both variants):
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

## What was learned (sessions 01-03)
- Ours vs native `jsbsim==1.3.3`: same 59/61 aircraft load; bit-identical on the NASA brick and external forces;
  rounding-level on c1721/T38. c1723 and f16_test diverge from 1-ulp seeds (start altitude differs by 2 ulp of the
  Earth radius, different libm); native vs native with +1e-8 ft does the same. Compare within tolerances, not bits.
- JSBSim's noise uses `std::default_random_engine`/`std::normal_distribution` (implementation-defined): models with
  active noise cannot match native Linux (libstdc++) step for step.
- psi is reported in [0, 2pi): wrap angles before comparing.
- **Integrator: still undecided (session 04 decides).** Gates and results: `GATES.md`, REPORT-03, `results/03-gates-*.txt`.

  | | G1 Rest | G2 Hard landing | G3 Extreme impacts | G4 NASA | G5 Rigid body | G6 Parity |
  |---|---|---|---|---|---|---|
  | Floor: Euler rates + Buss 2 attitude, no patch | PASS | FAIL | reference | FAIL | FAIL | PASS |
  | Candidate 1 (patch 0001 on) + AB4 + Buss 2 | FAIL (c310 at 120 Hz) | FAIL | worse | PASS | FAIL | PASS |
  | Candidate 1 + AB3 + Buss 2 | PASS | FAIL | worse | PASS | FAIL | PASS |
  | Candidate 1 + AB2 + Buss 2 | PASS | FAIL | worse | FAIL | FAIL | PASS |

  - Keep JSBSim's default body rates (Euler) in anything shipped until a candidate passes.
  - Buss 2 attitude is `simulation/integrator/position/rotational = 7`.
  - Floor: body rates 0.09 deg/s off NASA at 480 Hz (gate 2e-6); it also fails hard landings at 120/240 Hz (ah1s
    also at 480 Hz), and Euler rates gain or lose energy fast when tumbling.
  - Candidate 1 (integrator-aware friction) fixes settling at rest for AB2/AB3/AB4. It does **not** fix hard
    landings or crashes with AB rates.
  - At 1000 Hz, hard landings survive with the floor, AB3 and AB2, not with AB4.
- What the ground problem is made of (REPORT-03 "What we learned"):
  - Friction: `FGAccelerations::CalculateFrictionForces` assumes an Euler step. JSBSim fixed this in 2010 (53709ba8)
    and lost it in 2011 (e67c5e42, 85b3a574, 40279c20). Patch 0001 restores it, adapted: it weights the
    translational and rotational parts of the friction matrix by each scheme's leading weight, and uses the inertial
    derivative. The 2010 formula as written lets a resting aircraft creep (Earth-rotation bias; ledger 16).
  - Gear spring-dampers: the c310 at 120 Hz with AB4 oscillates in pitch even with all friction removed. Reading
    (Reasoned, not tested): the damper is too stiff for AB4's stability limit, about 7x tighter than Euler's.
  - Hard landings are numerically chaotic: native and WebAssembly agree for 3.4 s, then split within 0.15 s. One run
    per case is a coin toss; judge on repeated, perturbed runs.
  - f16 inverted impact: friction on STRUCTURE contacts contributes (Codex ablation). First invalid operation unknown.
  - `gear/wow` counts only BOGEY contacts. The gates read every point: `gear/unit[k]/WOW` and `contact/unit[k]/WOW`.
- G5 with AB4 fails only through JSBSim's multistep start-up (history filled with copies of the first derivative):
  the energy changes in the first 4 steps and is constant afterwards (ledger 17). AB3 also drifts slowly after that.
- **Session 04 plan** (REPORT-03 "What remains"): first add later gates (G5b drift after start-up; G2b/G3b repeated
  perturbed runs; fix the step rates that matter), commit them, then candidate 2 (implicit-midpoint body rates,
  PteroLabsAI/jsbsim PR 13, as patch 0002 with its own switch) and candidate 3 (AB in the air, Euler while any contact
  point touches), then decide, then a second independent review.
- Defects from the review of session 02 are fixed (REPORT-03 step 1). Still open: no memory-leak audit; `setProperty`
  by name creates missing properties.
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
                                      # NATIVE=pip|unpatched|patched picks the answer key; summaries to results/03-*, raw CSVs to out/
scripts/build-native.sh               # native answer keys from source -> build/native/{unpatched,patched}
tests/gates/run.sh floor              # one configuration through all gates (about 2 min) -> results/03-gates-<config>.txt
.venv/bin/python tests/gates/summary.py floor c1-ab4 c1-ab3 c1-ab2   # side-by-side table
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
- `tests/gates/`: the gates (`gates.json`, runners, `evaluate.py`, `run.sh`, `summary.py`), candidate list
  (`configs.json`), diagnostics (`diag/`). `wasm/patches/`: JSBSim patches.
- `tests/review/` and `results/review-codex-02/`: Codex's review tests and results (e.g. `ground_matrix.py`, a native
  stress matrix of 6 aircraft × 5 scenarios × 2 rates × 2 integrators).
- `web/` page source (TypeScript, bundled by esbuild in `scripts/build-site.mjs`); `.github/workflows/pages.yml` deploys
  it from `main` to https://135crewdog.github.io/FDM/.
- `results/03-*` session 03 summaries (`03-gates-*` are the gate reports); `results/02-*` session 02's;
  `results/session01/` session 01's.
- `prompts/`: one prompt per chat, and `README.md` with the chat naming convention and the list of sessions
  (e.g. `04-integrator-decision.md`; `codex-review-02.md`, independent review of session 02). An independent
  review should be repeated after phase 2's integrator decision, before the hybrid wing-strip work builds on it.
