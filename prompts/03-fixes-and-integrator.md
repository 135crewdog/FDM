# Claude Code prompt: session 03, fixes, acceptance gates and first integrator candidate

Before starting (user): use the same cloud environment as session 02 ("FDM build", with network access for
emsdk, GitHub, PyPI and npm). Paste everything below the line into a new Claude Code session on `135crewdog/FDM`.

---

Read `CLAUDE.md`, then `REPORT-02.md` (especially "Review outcome" and the Evidence ledger), then
`REVIEW-codex-02.md`.

Where we are:

- Our WebAssembly build of JSBSim v1.3.3 is validated. It loads the same aircraft as native JSBSim, matches native
  in controlled flight, and runs fast on my iPhone.
- What is open:
  - defects in our binding and test harness, found by an independent review;
  - which body-rate integrator to use. AB4 is accurate in the air but fails on the ground at every rate tested,
    including 1000 Hz. JSBSim's default (Euler) is robust on the ground but less accurate in the air.

This session fixes the defects, writes down the pass/fail gates, and tests the safe fallback and the first
candidate. It does **not** make the final integrator decision; that comes in session 04, after two more
candidates.

Keep messages to me short and plain. I am not a flight-dynamics expert. Follow the evidence-label rule in
CLAUDE.md.

## Working rules

- Commit and push to `main` at each checkpoint below.
- If you run low on time or context, stop at a checkpoint, write what is done and what is left in
  `REPORT-03.md`, and push.
- Do not change JSBSim's physics except through a patch file in `wasm/patches/`. Each patch must be small,
  explained in its header, and applied in the same way to the WebAssembly build and to the native answer key.
- Never change a gate, tolerance or yardstick after seeing a candidate's results. If a gate turns out to be
  wrong, say so in the report, keep the original result, and add the new gate as a separate, later gate.

## Step 1: fix the defects (checkpoint after each group)

Every defect listed under "Known defects" in CLAUDE.md and "Review outcome" in REPORT-02.md. For each one:
turn Codex's probe (`tests/review/*`) or a new test into a permanent regression test, show that it fails before
the fix and passes after, and only then fix it.

1. **Binding** (`wasm/bindings.cpp`, `src/jsbsim.ts`):
   - Every public call catches every C++ exception, including `std::string` throws, and reports JSBSim's message
     as a `JSBSimError`.
   - Writes to read-only properties fail.
   - `reset()` clears bulk bindings and invalidates old handles under a documented lifetime rule.
   - Handles must be integers in range; `NaN`, fractions and wrapped values are rejected.
   - Unknown integrator IDs and non-positive or non-finite dt are rejected.
   - After fixing, rebuild both variants with `scripts/build-wasm.sh`.
2. **Harness:**
   - `tests/parity/compare.py` rejects NaN/Inf, mismatched lengths, times or headers, and exits non-zero on any
     of them. Add self-tests with synthetic bad logs.
   - `scripts/run-tests.sh` names the build variant explicitly everywhere and records each binary's hash in
     the results.
   - `tests/ab4/rate_sweep.ts` reports "rates > 1e6" and "first NaN" separately.
   - Benchmarks compare the same workload.
3. **Build and runtime:**
   - `scripts/build-wasm.sh` re-applies patches when they change (re-clone or reset the source), records patch
     hashes in `build-info.json`, and fails on a different Emscripten version.
   - Fix the 737's missing `ws` dependency, either by declaring it or by disabling socket I/O in our runtime.
     State which you chose.
   - Make native runs write their output files outside `jsbsim-data/`.
   - Set dt before loading a model everywhere it matters.
4. Re-run tests 1–5 with both variants named explicitly, and confirm the session 02 results still hold.

## Step 2: native answer key for patched JSBSim (checkpoint)

Once we patch JSBSim, `pip install jsbsim==1.3.3` is no longer the answer key.

- Build native JSBSim v1.3.3 from source in this container. The Python module is preferred, so the existing
  native harness works.
- First prove the unpatched native build is a valid answer key: it must agree with `pip jsbsim==1.3.3` on
  tests 1–4 and on Codex's controlled-flight probes (`tests/review/parity_probe.*`). Use Codex's tolerances:
  positions ≤ 1e-4 ft, velocities ≤ 1e-5 ft/s, rates and attitudes ≤ 1e-7.
- Then the same build plus any patch becomes the answer key for the patched WebAssembly build.

## Step 3: write the gates, then commit them before any candidate runs (checkpoint)

Write `tests/gates/` and `GATES.md`. Record the commit hash of the gates in `REPORT-03.md` before running any
candidate. Start from Codex's "Tests to add" with these numbers:

- **G1 Rest:** c172x, f16, c310, ah1s and 737 on their gear for 60 s, at 120, 240, 480 and 1000 Hz.
  - In the last 10 s, every body-rate component < 1e-6 rad/s.
  - Horizontal displacement < 0.01 ft over the last 10 s.
  - Every state finite.
- **G2 Hard landing:** Codex's "hard" scenario (40 ft AGL, 100 ft/s forward, 30 ft/s down, level) on the same
  five aircraft. Every state finite for 15 s at each rate.
- **G3 Extreme impacts:** Codex's inverted, banked and nose scenarios. These are not pass/fail yet, because
  crash handling belongs to the phase 2 wrapper. A candidate must be no worse than the floor: count runaways
  (rates > 1e6 or NaN) and list them.
- **G4 NASA case 02** at 480 and 1000 Hz, against NASA sims 01 and 04, all 301 samples present:
  - body-rate error < 2e-6 deg/s;
  - attitude error < 1e-3 deg;
  - report position offsets with their cause.
- **G5 Torque-free rigid body:** rotational kinetic energy and angular momentum drift < 1e-6 relative over 60 s,
  for the brick and one body with products of inertia, at several spin axes and rates.
- **G6 Parity:** each candidate's WebAssembly build against the native build of the same source, within the
  Step 2 tolerances, on Codex's controlled flights.
- Also record, without a gate: iPhone-relevant cost (µs per step in Node) for each candidate.

Use Codex's `tests/review/ground_matrix.py` scenarios. Set dt before loading the model. Detect contact with
every contact point (BOGEY and STRUCTURE), not `gear/wow`.

## Step 4: run the floor and candidate 1 (checkpoint after each)

- **Floor:** JSBSim's default body rates (Euler, `rate/rotational = 1`) plus Buss 2 attitude
  (`position/rotational = 7`). No patch.
  - It is expected to fail G4's body-rate gate. Report by how much.
  - It is the fallback if nothing else passes.
- **Candidate 1:** restore JSBSim's 2010 integrator-aware friction as a patch.
  - History: upstream commits `53709ba8`, `e67c5e42`, `85b3a574`, `40279c20`; see REPORT-02 and
    `results/review-codex-02/source-history.txt`.
  - Adapt it to v1.3.3's `FGAccelerations::CalculateFrictionForces`. It must cover both translation and
    rotation, and account for their different integrators.
  - Test it with AB4 body rates plus Buss 2 attitude, and also with AB2 and AB3 body rates.
- For each: run G1–G6, show a pass/fail table, and compare against the floor.

## Finish

Write `REPORT-03.md`. Put the Evidence ledger near the top, followed by:

- the defects fixed;
- the gates and their commit hash;
- a table of floor and candidate 1 against every gate, with the numbers;
- what remains for session 04 (candidates 2 and 3: implicit-midpoint body rates from PteroLabsAI/jsbsim PR 13,
  and switching integrators on contact);
- which claims an independent reviewer should check first.

Update CLAUDE.md. Commit and push to `main`.
