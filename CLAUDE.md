# FDM repository: notes for future sessions

Flight dynamics model for a flight-sim game that runs as a PWA on iPhone. The core is **JSBSim v1.3.3 compiled to
WebAssembly by us** (Emscripten 6.0.13). Read in this order:
1. `REPORT-05.md`: the new landing, repeated-contact, crash and forced-flight gates, patch 0004 (strut limits),
   crash containment, and **the decision: the wrapper's default is now midpoint body rates, Buss 2, strut limits,
   1200 Hz**. Not yet independently reviewed (`prompts/codex-review-05.md`).
2. `GATES-05.md` (this session's gates and what had been seen before them), then `GATES.md`, `GATES-04.md`,
   `GATES-04b.md`: the rule that gates are never changed after a result.
3. `REPORT-04.md` with its "Review outcome", and `REVIEW-codex-04.md` (the review that said "not yet").
4. `REPORT-03.md` (defect fixes, first gates, candidate 1; several ground explanations are corrected later).
5. `REPORT-02.md` (our build and tests) and `REVIEW-codex-02.md` (independent review of session 02).
6. `REPORT.md` (session 01, the evaluation of the `@0x62/jsbsim-wasm` package, now replaced).

## Chats and prompts (`prompts/README.md`)
The repository is the project's memory; a chat is only where one piece of work happens.
- Every chat is named `FDM <number> <kind>: <topic>`, e.g. `FDM 04 Work: integrator decision`. The number is the
  session number (same as `REPORT-04.md`, `prompts/04-*.md`, `results/04-*`). Kinds: `Work` (Claude Code on the
  repository), `Review` (independent review, Codex), `Plan` (regular Claude chat; cannot see the repository).
- At the start of a session, rename the chat to the name in its prompt (or ask the user to, in the first line).
- Every work session ends by writing the prompt for the next chat, with its chat name at the top and "Name this
  chat ..." as the first instruction, and by adding a row to the table in `prompts/README.md`.
- Next: `prompts/codex-review-05.md` (the independent review of session 05; the default changed, so it comes
  first), then `prompts/06-wing-strip-forces.md`.

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
- Also frozen (session 05, commit `888654f`): `tests/gates/gates-05.json`, `sim05.py`, `sim05.ts`,
  `run_native_05.py`, `run_wasm_05.ts`, `evaluate_05.py`, `GATES-05.md` (G2d Landing, G8 Repeated contact, G3d
  Crash containment, G7 Forced flight).
- `tests/gates/run.sh`, `run-later.sh`, `run-forward.sh`, `run-05.sh` and `run-rates-05.sh` refuse to run if the
  frozen files are uncommitted or changed.
- **Reading a frozen gate at a step rate it does not list:** never edit it. `tests/gates/run-rates-05.sh <config>
  <hz>` runs the frozen code in a shadow copy in which only the lists of step rates differ.
- New candidates go into `tests/gates/configs.json` (not frozen).
- **Check what a scenario really does before trusting its name.** G2's "hard landing, 100 ft/s forward" was flown
  backward by four of five aircraft for two sessions (the scenario set the velocity north; the start files face
  south). Read the body-axis velocity, the attitude and the height from the simulation, not from the description.
- **"Finite" is not "sane".** A run can stay finite while the aircraft is 150 ft under the ground or thrown to
  1,000 ft. Gates on the ground need conditions on height, attitude and energy.
- **A fixture must fly the aircraft the way it flies.** G2c fixed the direction but still flew a 737 at 59 kt with
  engines off; it tipped over, and session 04 wrongly concluded the 737 cannot test a landing. With 140 kt, flaps
  and running engines it lands every time (REVIEW-codex-04). Do not drop an aircraft because a bad fixture fails.
- **A free-body test says nothing about stability under applied moments.** AB4 passes NASA's tumbling brick at
  480 Hz and blows up at 480 Hz under a stable damping moment with a 5 ms time constant (AB4 needs about
  `|lambda| * dt < 0.3`; Euler 2). Test integrators with forces applied, not only without.
- **An association is not a cause.** "60 of 60 failures were preceded by X" did not show that X starts the
  failure (176 finite runs had X too). Test an explanation by removing the cause, as the review did.
- **Old gates can pass for the wrong reason.** With the strut limits on, G2c and G3b pass for the 737 and ah1s
  while the aircraft falls through the ground: they only see "finite". Read the height and the energy (G3d does).
- **Native JSBSim ignores a write to a read-only property without a word** (`f[p] = v`). A fixture's crosswind was
  never set that way; only the WebAssembly wrapper noticed. Use `sim05.set_props` (it checks) for anything a
  fixture depends on, and read back what a fixture really does.
- **A limit must be checked on the quantity that is reported.** The first crash-containment check used
  `FGGroundReactions::GetForces()` (no friction) while the gates and the property `forces/fb*-gear-lbs` include
  friction (`FGAccelerations::GetGroundForces()`).
- **Fixture facts about JSBSim** (session 05): a kinematic component (flaps, gear) reads its state back from its
  output property, so preset that property or it starts at zero and travels; a second `run_ic` resets position,
  velocity, attitude and rates and KEEPS engine, rotor and control-system states (used to settle engines);
  `forces/hold-down` zeroes the velocity (useless for a moving aircraft); the aircraft models have ground effect,
  so trim at the height you start from; JSBSim's trim fails for the c310; `ic/vw-north-fps` and `-east-fps` are
  read-only (set wind with `ic/vw-mag-fps` and `ic/vw-dir-deg`).
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
- Both build scripts stop when the compiler fails (they did not until 2026-11-16: `... | grep ... || true` hid the
  failure and a stale binary was recorded as built; `tests/build/selftest_patches.sh` now tests this). Never put
  `|| true` after a pipeline whose first command matters.
- **Patches** live in `wasm/patches/*.patch`. `scripts/lib-jsbsim-src.sh` resets the pinned source and re-applies them on
  every build, the same way for WebAssembly (`scripts/build-wasm.sh`) and for the native answer key
  (`scripts/build-native.sh`). `PATCHSET=unpatched scripts/build-wasm.sh` builds without them into
  `build/wasm-bin-unpatched/`. A wrong Emscripten version stops the build.
- **`wasm/bin` contains patches 0001, 0002, 0003, 0003b and 0004, all switched off inside JSBSim** (bit-identical
  to unpatched JSBSim when off: REPORT-05 ledger 2). The wrapper's default profile switches on 0002's scheme and
  0004 (see "Binding API").
  - 0001 `simulation/integrator/friction-aware`: 0 = JSBSim unchanged (default), 1 = integrator-aware friction
    (candidate 1), 2 = the 2010 code's formula (comparison only). Not used by the default; mathematics unreviewed.
  - 0002 `simulation/integrator/rate/rotational` = 10: implicit-midpoint body rates (PteroLabsAI/jsbsim PR 13,
    commit 33384d9, unchanged plus counters under `simulation/integrator/midpoint/`). **The default's scheme.**
    It throws if Newton's method fails (never seen with an aircraft; the wrapper then halts the simulation).
  - 0003 `simulation/integrator/rate/rotational-on-contact`: -1 = no switching (default); an integrator id (1 =
    Euler) = that scheme integrates the body rates while any contact point (BOGEY or STRUCTURE) touches
    (candidate 3). Also `.../contact-hold-sec`, `.../contact-release-mode`, and `.../contact-active`,
    `.../contact-switches`.
  - 0003b (session 05; property access only, no switch): `contact-active`, `contact-switches` and the midpoint
    counters are read-only; `rotational-on-contact`, `contact-hold-sec` and `contact-release-mode` refuse bad
    values (they throw).
  - 0004 `gear/strut-limits/enabled`: 0 = JSBSim unchanged (default inside JSBSim), 1 = limits on the wheel
    (BOGEY) strut model: `min-projection` 0.5 (the leg's cosine is not allowed below it), `max-travel-leg-fraction`
    0.5 (a wheel that would be compressed beyond that share of the CG's height above it is gone: no force, no
    contact), `max-force-weights` 5 (cap of one strut). Read-only counters `projection-floored`, `force-capped`,
    `travel-exceeded`. Airframe (STRUCTURE) points are unchanged. **On in the default.** It never acts in a
    landing within the aircraft's limits (REPORT-05 ledger 14).
  - A patch's header text is part of its hash, and the hashes are in every result file: do not edit a patch
    (even its comments) without rebuilding and re-running what depends on it. Add a new patch file instead (as
    0003b did).
- **Native answer key:** `pip jsbsim==1.3.3` cannot carry patches. `scripts/build-native.sh` builds the Python module
  from source into `build/native/unpatched` and `build/native/patched`; use `PYTHONPATH=build/native/<set>`. The
  unpatched build is bit-identical to pip on everything compared (REPORT-03, ledger 4).

## Binding API (`src/jsbsim.ts`, browser-safe; Node helpers in `src/wasm.ts`)
**Defaults (session 05).** `JSBSim.create({factory})` (what the game uses) runs the configuration that passed every
gate, `FDM_DEFAULT`: 1200 Hz (set at create and reset), implicit-midpoint body rates + Buss 2 attitude + strut
limits (set after every `loadModel` / `loadScript`). `profile: "jsbsim"` gives JSBSim's own defaults (120 Hz, Euler,
no limits). **The Node helper `createSim()` defaults to `"jsbsim"`** (override: `profile: "fdm"` or `FDM_PROFILE=fdm`):
every test and frozen gate runner compares with native JSBSim and sets its own integrators. A script loaded
without an explicit dt keeps its own dt (the default is qualified at 1200 Hz only).
```ts
const sim = await createSim();            // Node: loads wasm/bin/jsbsim-weh.mjs (JSBSIM_VARIANT=jsbsim for the other), copies jsbsim-data into MEMFS at /jsbsim
sim.dt = 1 / 480;                         // BEFORE loading (filters cache dt at load); after load it throws (setDtAfterLoad to force)
sim.loadScript("scripts/c1723.xml");      // or sim.loadModel("f16"); sim.loadIC("reset00"); errors throw JSBSimError with JSBSim's message
sim.setIntegrators({ rateRotational: 5, positionRotational: 7, rateRotationalOnContact: 1 });  // e.g. c3-ab4; reads each setting
                                          // once, applies all or nothing. Unknown ids throw.
sim.runIC(); sim.run(); sim.runSteps(n);  // run() returns false when a script ends or the step halted the simulation
sim.getProperty(name); sim.setProperty(name, v);   // by name: ~1-2 us per call, fine for setup, not per step
const h = sim.handle(name); sim.get(h); sim.set(h, v);          // cached handle: ~45 ns per write
sim.bindInputs(names); sim.bindOutputs(names);                   // bulk: write sim.inputs (Float64Array),
sim.inputs.set(values); sim.step(1); sim.outputs;                // step(n), read sim.outputs
sim.setContainment({});                   // crash containment, off until called: checked after EVERY physics step
if (sim.halted) { sim.halted.reason; }    // "below-surface" | "tipped-over" | "ground-force" | "runaway-rate" | "non-finite" | "exception"
sim.reset();                              // fresh FGFDMExec, same files; ALL earlier handles become invalid, bulk bindings empty; clears a halt
```
Raw embind class: `wasm/bindings.cpp`. Contract (tested by `tests/binding/regress.ts`, 136 checks, both variants,
and `tests/binding/containment.ts`):
- Every public call catches every C++ exception (`std::string` and `const char*` too) and returns a status; the
  wrapper throws `JSBSimError` with JSBSim's message. Nothing else is ever thrown.
- Nothing fails silently: read-only writes, invalid handles (NaN, fractions, out of range, from before `reset()`),
  bad dt (also a script's own), unknown integrator ids and bad step counts all throw.
- **Crash containment** (`setContainment`, limits: 30 rad/s, CG under the surface, 75 deg tilt on the ground, 50
  weights of ground force; each can be changed or set to null): on a hit the step is not published (`outputs` keep
  the last accepted state), no further step runs (`run`/`runSteps`/`step` throw until `reset()`), `halted` says why.
- **A step that throws halts the simulation too** (reason `exception`), with containment on or off: JSBSim has
  already advanced its clock when it throws, so the state is not a rollback.
- Handles are numbers (generation x 2^20 + index). Re-read `sim.inputs`/`sim.outputs` after `reset()`, binding, or
  anything that can allocate.
- Socket input (`<input port=...>` in aircraft files) is disabled in our runtime, so no npm `ws` is needed.
- `setProperty` still creates a missing property (as JSBSim does); `handle()` and bulk binding do not.
- A value written through the bulk inputs or a property before `step` acts **one step late**: JSBSim's step first
  integrates the derivative it stored in the step before. Stable up to about `rate x step < 1`; costs accuracy
  (REPORT-05 ledger 9). The wing-strip work must be validated with this in mind.

Shared test helpers used by Node and the page: `src/checks.ts`. Node helpers: `src/wasm.ts` (`JSBSIM_VARIANT`,
`JSBSIM_BIN` to use another build directory, `describeBuild()` for the hash line).

## What was learned (sessions 01-05)
- Ours vs native `jsbsim==1.3.3`: same 59/61 aircraft load; bit-identical on the NASA brick and external forces;
  rounding-level on c1721/T38. c1723 and f16_test diverge from 1-ulp seeds (start altitude differs by 2 ulp of the
  Earth radius, different libm); native vs native with +1e-8 ft does the same. Compare within tolerances, not bits.
- JSBSim's noise uses `std::default_random_engine`/`std::normal_distribution` (implementation-defined): models with
  active noise cannot match native Linux (libstdc++) step for step.
- psi is reported in [0, 2pi): wrap angles before comparing.
- **Integrator: decided in session 05, not yet independently reviewed** (REPORT-05 "The decision").
  - **The default is `c2-mid-g` at 1200 Hz**: implicit-midpoint body rates (patch 0002), Buss 2 attitude, strut
    limits (patch 0004). It passed every gate, old and new, on both platforms.
  - **`c3-ab4-g`** (AB4 in the air, Euler on contact, Buss 2, strut limits) **also passes, at 960 and at 1000 Hz**,
    and fails at 480 Hz (AB4 is unstable under a 180 per second damper there). It is 4 times closer to NASA and
    needs 20% fewer steps, but tolerates about 7 times less stiff moments (damper limit 250 per second against
    1,800 inside JSBSim; 300 against 600 when written from JavaScript). One `setIntegrators` call selects it.
  - **Nothing passes without patch 0004**: every configuration fails crash containment (G3d) with JSBSim's wheel
    code as it is.
  - Midpoint fails the NASA limit at 960 Hz (2.5e-6 against 2e-6) and passes at 1200 Hz with a thin margin
    (1.6e-6). Do not run the default below 1200 Hz without revisiting that.
  - The table (`results/05-gates-summary.txt`; `-g` = strut limits on; new-gate cells are cases good on both
    platforms):

    | | G1 Rest | G4 NASA | G5b Energy | G6 Parity | G2d Landing | G8 Repeated contact | G3d Crash containment | G7 Forced flight | passes |
    |---|---|---|---|---|---|---|---|---|---|
    | Floor, 480 to 1200 Hz | pass | fail | fail | pass | 23/23 | 8/8 | fail (14 to 16 of 20) | 12/12 | no |
    | Floor with strut limits | pass | fail | fail | pass | 23/23 | 8/8 | 20/20 | 12/12 | no |
    | `c3-ab4-g` 480 Hz | pass | pass | pass | pass | 23/23 | 8/8 | 20/20 | fail (10/12) | no |
    | `c3-ab4-g` 960, 1000 Hz | pass | pass | pass | pass | 23/23 | 8/8 | 20/20 | 12/12 | **yes** |
    | `c2-mid-g` 960 Hz | pass | fail | pass | pass | 23/23 | 8/8 | 20/20 | 12/12 | no |
    | `c2-mid-g` 1200 Hz | pass | pass | pass | pass | 23/23 | 8/8 | 20/20 | 12/12 | **yes** |

  - The fastest aerodynamic moments of the test aircraft: damping 89 per second (f16, 800 kt), stiffness 9.7 rad/s
    (`results/05-envelope.txt`). G7 gates at twice that. The wing-strip forces must be measured against this.
  - AB3 in the air fails G5b (a real, slow drift); AB2 fails G4. Candidate 1 (patch 0001 + AB4 everywhere) is
    worse than the floor in crashes. Neither was taken further.
  - In the review's synthetic repeated-contact case (reported, not judged) `c3-ab4` ends 0.039 rad/s off at 960 Hz;
    midpoint and Euler end at zero. In real touch-and-go and skipping all configurations are within 0.1 deg.
- **All five test aircraft land when flown properly** (G2d: c172x 55 kt flaps 30; c310 75 kt flaps 25; 737 130 kt
  full flaps; f16 150 kt; ah1s rotor-running vertical; sink 2 ft/s to the aircraft's limit, 8 to 10 ft/s). The
  landings are deterministic (1.5% between 480 and 9600 Hz), the ground never gives net energy, and no
  configuration differs from another in them. Session 04's "737 and ah1s cannot land" was a fixture error.
- **What the ground problem is** (REPORT-05 ledger 12 to 15):
  - **Wheel geometry** (`FGLGear.cpp`): compression, its speed and the force are each divided by the cosine of the
    leg's tilt, with no limit. Patch 0004 floors the cosine, removes a wheel that is buried beyond its travel, and
    caps one strut's force. With it all 20 crash cases are contained (forces at most 171 weights, from the
    airframe points' own dampers; no energy from the ground). Without it forces reach 1e10 weights.
  - **An aircraft needs complete airframe (STRUCTURE) contact points.** With the limits on, a wheel that is gone
    stops pushing. The 737 model has no airframe points and then falls through the ground (4,000 ft in 15 s); the
    c172x has only wing tips and a tail skid. Every game aircraft needs points on nose, belly, tail, wing tips
    and nacelles, and the game must switch crash containment on.
  - **Friction on airframe contacts with AB4 on the ground** (`scripts/f16_test.xml` at 120 and 240 Hz): real, not
    cured by the strut limits. The floor's integrators, `c3-ab4` and midpoint are not exposed in that test.
  - **Gear dampers and stability at rest.** A stiff damper needs a small enough step: the c310 at 120 Hz tolerates
    0.71 (AB4), 1.20 (AB3), 1.81 (AB2), 2.58 (Euler) times its own damping; the limit doubles with the step rate.
    `tests/gates/diag/gear_damper.py`.
  - Friction: `FGAccelerations::CalculateFrictionForces` assumes an Euler step. JSBSim fixed this in 2010 (53709ba8)
    and lost it in 2011. Patch 0001 restores it, adapted. Not needed by the default.
  - `gear/wow` counts only BOGEY contacts. Read every point: `gear/unit[k]/WOW` and `contact/unit[k]/WOW`.
  - G5 with AB4 fails only through JSBSim's multistep start-up (first 4 steps); G5b (from 1 s) passes.
- Defects from the review of session 02 are fixed (REPORT-03 step 1). Still open: no memory-leak audit; `setProperty`
  by name creates missing properties. Patch 0001's algebra was checked by the reviewer for frozen geometry.
- The binding gaps found by REVIEW-codex-04 are fixed (REPORT-05 ledger 3): a script's own dt is validated before
  loading; status properties are read-only and the switch's settings validated (patch 0003b); `setIntegrators` is
  all-or-nothing.
- `build/wasm-bin-unpatched` (the floor's comparison build, not shipped) still carries session 04's binding.
- `.gitignore` used to ignore every directory named `build`, so `tests/build/selftest_patches.sh` was never
  committed in session 03. It now ignores only `/build/`. After adding a file, check `git status` shows it.
- Set dt **before** loading a model (FCS filters cache dt at load). The binding now enforces it.
- Native JSBSim writes output files into its data root unless told otherwise. Every native runner must go through
  `tests/pylib/native.py` (`new_fdm()` sets a scratch output path); `scripts/run-tests.sh` fails if anything appears
  in `jsbsim-data/`.
- Property writes by name are slow (~1.8 us each with -fexceptions); use handles or bulk for per-step traffic.
- `-fexceptions` costs ~50-100% per step vs no exceptions; `-fwasm-exceptions` costs nothing measurable.
- iPhone (Safari 27.2), weh build, JSBSim's defaults: c172x 8-13 us/step, f16 ~10 us/step, +20 forces by
  handle/bulk ~3 us; timer resolution 1 ms (time batches only) (`results/04-page-iphone-fwasm-exceptions.txt`).
  **The default (midpoint, Buss 2, strut limits, 1200 Hz) on the same iPhone: 10-14 us/step, f16 11.3, with 20
  forces in bulk 13.0, so 12 to 16 ms of computing per second of flight** (about 1.5% of one core); crash
  containment costs nothing measurable (`results/05-page-iphone-fwasm-exceptions.txt`, the page's section 5).
  The first timed run on a freshly created module is slower (13.7 against 10.0 for the same flight); read that as
  warm-up, not as the scheme's cost (not tested).

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
tests/gates/run.sh floor              # G1-G6 (about 2 min) -> results/<SESSION>-gates-<config>.txt   (the floor first; SESSION=05)
tests/gates/run-later.sh floor        # G5b, G2b, G3b (about 3 min) -> results/<SESSION>-later-<config>.txt
tests/gates/run-forward.sh floor      # G2c and the verdict per step rate, both ways -> results/<SESSION>-forward-<config>.txt
tests/gates/run-05.sh c2-mid-g        # G2d, G8, G3d, G7 at the configuration's rates (configs.json, rates_05) -> results/05-new-<config>.txt
tests/gates/run-rates-05.sh c2-mid-g 1200   # the frozen G1-G6 and G5b read at 960 or 1200 Hz -> results/05-rates-<hz>-*.txt (the floor first)
.venv/bin/python tests/gates/summary_05.py floor floor-g c3-ab4 c3-ab4-g c2-mid c2-mid-g   # one table (summary_04.py, summary.py: earlier sessions)
JSBSIM_VARIANT=jsbsim-weh npx tsx tests/binding/containment.ts    # crash containment: unit tests and the 20 crash cases
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
- `tests/build/` patch and build self-test; `tests/pylib/native.py` shared
  set-up for native runs; `tests/native/` answer-key checks.
- `tests/gates/`: the gates (`gates.json`, `gates-04.json`, `gates-04b.json`, `gates-05.json`, runners, evaluators,
  `run.sh`, `run-later.sh`, `run-forward.sh`, `run-05.sh`, `run-rates-05.sh`, `summary.py`, `summary_04.py`,
  `summary_05.py`), candidate list (`configs.json`: `-g` = strut limits on; `rates_05`; `ref05-*` = 9600 Hz
  references), diagnostics (`diag/`: `gear_damper.py`, `landing_anatomy.py`, `blowup_cause.py`,
  `midpoint_counters.py`, `contact_switch.py`, `confirm_rate.py`, and session 05's `structure_friction.py`,
  `strut_limits_idle.py`, `damping_headroom.py`). Session 05: `sim05.py` / `sim05.ts` (the fixtures and
  procedures, one per platform), `evaluate_05.py` (the one judge; energy bookkeeping), `make_fixtures05.py` (trims),
  `envelope05.py` (fastest moments), `cost05.ts`, `explore05/` (every fixture trial script; the trials are logged in
  `results/05-fixture-trials*.jsonl`). `wasm/patches/`: JSBSim patches.
- `tests/binding/`: `regress.ts` (binding contract) and `containment.ts` (crash containment).
- `tests/review/` and `results/review-codex-02/`, `results/review-codex-04/`: Codex's review tests and results
  (e.g. `ground_matrix.py`; `review04_powered_landing.py`, a proper 737 approach; `review04_airborne.ts`, forced
  damping; `review04_release.py`, repeated switching; `review04_build_scratch.py`, scratch builds with a
  compression cap and projection guard).
- `web/` page source (TypeScript, bundled by esbuild in `scripts/build-site.mjs`); `.github/workflows/pages.yml` deploys
  it from `main` to https://135crewdog.github.io/FDM/.
- `results/05-*` session 05: `05-new-*` (G2d, G8, G3d, G7 per configuration), `05-gates-*`, `05-later-*`,
  `05-forward-*` (the older gates), `05-rates-<hz>-*` (older gates read at 960 and 1200 Hz), `05-gates-summary.txt`,
  `05-diag-*`, `05-containment-*`, `05-cost.txt`, `05-repro-*` (session 04 reproduced on the build as it was),
  `05b-*` (after patch 0003b), `05-fixture-trials*.jsonl`. `results/04-*` session 04; `results/03-*` session 03;
  `results/02-*` session 02; `results/session01/` session 01.
- `prompts/`: one prompt per chat, and `README.md` with the chat naming convention and the list of sessions
  (e.g. `06-wing-strip-forces.md`; `codex-review-05.md`, the prompt of the review of session 05, which chose
  the default integrator and must be reviewed before more is built on it).
