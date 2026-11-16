# Independent review of session 05 (prompt for Codex)

**Chat name: `FDM 05 Review: ground model and default integrator`** (naming convention: `prompts/README.md`).

Paste everything below the line into a new Codex task on the repository `135crewdog/FDM` (branch `main`).

---

**Name this chat `FDM 05 Review: ground model and default integrator`.** If you have a tool that renames the
session, use it now. If you do not, make the first line of your first message: "Please rename this chat to: FDM 05
Review: ground model and default integrator".

You are an independent reviewer. Another AI agent (Claude Code) did the work in this repository. The owner is not
a flight-dynamics or simulation expert. They cannot judge the physics themselves and want an outside check before
they build more on it. Your job is to find what is wrong, weak or overstated. Agreeing is not the goal. Treat
every statement in `REPORT-05.md`, `GATES-05.md` and `CLAUDE.md` as a claim to check.

Keep messages to the owner short and plain.

## Background

- The flight dynamics model for a flight-sim game that runs as a web app on iPhone: JSBSim v1.3.3 compiled to
  WebAssembly, plus a small binding (`wasm/bindings.cpp`, `src/jsbsim.ts`).
- You reviewed sessions 03 and 04 and said "not yet" (`REVIEW-codex-04.md`). Session 05 followed your list of
  "What session 05 should do differently".
- Read `CLAUDE.md`, then `REPORT-05.md` (its Evidence ledger, "Earlier explanations that turned out wrong" and
  "What an independent reviewer should check first"), then `GATES-05.md`.
- Raw results: `results/05-*`. Patches: `wasm/patches/` (new: `0003b`, `0004`). Gate code: `tests/gates/`
  (`sim05.py`, `sim05.ts`, `evaluate_05.py`, `run-05.sh`, `run-rates-05.sh`).
- How to build and run: `REPORT-05.md` "How to reproduce". The native answer keys are built by
  `scripts/build-native.sh`; you do not need Emscripten to check most claims.

## What session 05 concluded

- **It changed the wrapper's default** to implicit-midpoint body rates, Buss 2 attitude, the strut limits of patch
  0004, at 1200 Hz (`c2-mid-g`; `FDM_DEFAULT` in `src/jsbsim.ts`).
- Three configuration-and-rate combinations passed every gate on both platforms: `c2-mid-g` at 1200 Hz, and
  `c3-ab4-g` at 960 and at 1000 Hz. The report chose midpoint for its headroom under stiff moments.
- Nothing passes without patch 0004. With it, all 20 crash cases are "contained", though the 737 and ah1s end
  under the ground.
- All five aircraft land in suitable fixtures, the 737 and a rotor-running ah1s included.
- Crash containment was added to the wrapper (a check after every physics step).

## Highest priority: is the default sound?

1. **Were the gates fixed first, and are their limits fair?** `git log` around `888654f` (gates), the commit that
   adds `wasm/patches/0004-strut-limits.patch`, and the results commits. `GATES-05.md` lists what had been seen:
   about 310 fixture trials on JSBSim's default integrators (`results/05-fixture-trials*.jsonl`) and a harness
   check. Several limits were chosen after seeing those defaults. Are any of them shaped to let a candidate
   through? Is anything missing from the list?
2. **The three places where the report argued with the owner's starting positions**:
   - strut travel taken as `2 x weight / spring rate` (JSBSim has no travel data);
   - G7: a margin of 2 over the fastest measured moment (89 per second damping, 9.7 rad/s stiffness;
     `tests/gates/envelope05.py`), and pure dampers judged on stability only, not accuracy. Is the envelope
     computation right? Is a factor 2 enough for the wing-strip work? Does the one-step delay of forces written
     from JavaScript need more than the report says?
   - G8: your synthetic repeated-contact case is **reported, not judged**. `c3-ab4` ends 0.039 rad/s off in it at
     960 Hz. Was it right not to judge it? Do the real-aircraft cases (touch-and-go, skipping on an undulating
     runway with 29 to 82 contact episodes) measure accumulated error fairly, with a reference of Euler at
     9600 Hz?
3. **Patch 0004** (`wasm/patches/0004-strut-limits.patch`): read its header and code against `FGLGear.cpp`.
   - Is "off" really unpatched JSBSim? (`tests/native/verify_key.sh patched unpatched`.)
   - Are the three limits sound (cosine floored at 0.5; a wheel compressed beyond half the CG's height above it
     gives no force and no contact; one strut capped at 5 weights)? Can they act in a legitimate hard landing?
     The report says they never act in G2d (`tests/gates/diag/strut_limits_idle.py`, and identical measurements
     with the patch on and off).
   - **Is "contained" an honest word** for a 737 that ends 4,000 ft under the ground? Should G3d have a height
     condition? Does the wheel that disappears create a new way to gain energy that G3d's 5 runs per case miss?
4. **The fixtures** (`tests/gates/sim05.py`, `gates-05.json`): are these landings a pilot would recognise? Check
   what they really do from the rows, not from the description. In particular:
   - the settling trick: a second `run_ic` every 0.25 s for 4 s. Does JSBSim keep exactly the engine and
     control-system states and reset everything else? Is the state at the release consistent?
   - the trims (`tests/gates/make_fixtures05.py`), made in ground effect;
   - the c172x at its limit sink touches nose wheel first; is that a fair "landing within limits"?
   - the ah1s recipe (built by a helper agent; `tests/gates/explore05/ah1s_landing.py`).
5. **The energy bookkeeping** (`tests/gates/evaluate_05.py`, class `Run`, method `energy`): the frame, the
   centrifugal term, the trapezoidal sums, the helicopter (rotor energy is not in the budget). Can "the ground
   gives no energy" be fooled? Derive the expected closure error for a known case and compare.
6. **The readings at 960 and 1200 Hz** (`tests/gates/run-rates-05.sh`): the frozen gate code run in a shadow copy
   in which only the lists of step rates differ. Is that a fair reading of a frozen gate? Midpoint passes G4 at
   1200 Hz with 1.6e-6 against a limit of 2e-6. Re-run it natively.
7. **The choice between the two candidates** (REPORT-05 "The decision", ledger 17,
   `tests/gates/diag/damping_headroom.py`): is headroom under stiff moments the right reason to prefer midpoint
   at 1200 Hz over `c3-ab4` at 960 Hz, given midpoint's thin NASA margin and 20% more steps? Applied moments stay
   explicit in the midpoint scheme: does the headroom claim hold for stiffness (springs) as well as damping?

## Second priority

8. **Crash containment** (`wasm/bindings.cpp`: `inspect`, `guardStep`; `src/jsbsim.ts`: `setContainment`,
   `halted`; `tests/binding/containment.ts`). The first version measured the ground force without friction and the
   test caught it. Look for the next such defect: is every limit checked on the quantity the game would read? Is
   "the outputs keep the last accepted state" true for every stepping call? Is halting on any thrown step the
   right policy for midpoint's Newton failure?
9. **The default profile** (`FDM_DEFAULT`, `profile` in `src/jsbsim.ts`; `createSim` in `src/wasm.ts` keeps
   JSBSim's defaults for tests). Can a game end up on JSBSim's defaults without noticing (a script with its own
   dt, `simulation/reset`, a re-initialisation inside JSBSim)?
10. **Patch 0003b** and the binding fixes of step 1 (`tests/binding/regress.ts` section 8).
11. **The second crash mechanism** (`tests/gates/diag/structure_friction.py`): does the test support "the
    candidates are not exposed", or only "not in this one trajectory"?
12. **The ledger's labels** in REPORT-05: is anything labelled Verified that is only Supported?
13. Which binary made which result (REPORT-05 "Things a reader should know"): the binding was rebuilt after the
    candidates had run. Is the re-run of the chosen configuration enough?

## What to deliver

Write `REVIEW-codex-05.md` in the repository root: a verdict in the first paragraph (is the new default sound to
build on: yes, yes with conditions, or no), then a table of findings (what you checked, how, what you found, how
sure), then details. Use the labels Verified / Supported / Reasoned. Put your scripts in `tests/review/` (prefix
`review05_`) and your outputs in `results/review-codex-05/`. Do not change gates, patches, aircraft files or
shipped binaries; build experiments in ignored `build/` directories. End with what the next work session should
do differently.
