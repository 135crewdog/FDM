# Independent review of session 02 (prompt for Codex)

Paste everything below the line into a new Codex task on the repository `135crewdog/FDM` (branch `main`).

---

You are an independent reviewer. Another AI agent (Claude Code) built and tested this repository. The owner is not
a flight-dynamics or simulation expert. They cannot judge the physics themselves and want an outside check before
they build more on it. Your job is to find what is wrong, weak or overstated. Agreeing is not the goal. Do not
take the other agent's conclusions as given: treat every statement in `REPORT-02.md` and `CLAUDE.md` as a claim to
check.

## Background (what the project is)

- The flight dynamics model (FDM) for a flight-sim game that runs as a web app on iPhone.
- The core is JSBSim v1.3.3, an open-source C++ flight dynamics library, compiled to WebAssembly with Emscripten.
- Our additions:
  - a small C++ binding, `wasm/bindings.cpp`;
  - a TypeScript wrapper, `src/jsbsim.ts`;
  - tests that compare our build against native JSBSim (`pip install jsbsim==1.3.3`) and against NASA's published
    6-DOF check case 02 (data in `reference/nasa-checkcases/`).
- Read `REPORT-02.md` (results and an "Evidence ledger" labelling each finding Verified, Supported or Reasoned)
  and `CLAUDE.md` (how to run).
- Raw summaries are in `results/02-*.txt`. Test code is in `tests/`.

## Highest-priority question: the integrator decision

The plan is to run JSBSim at 480–1000 Hz with the Adams-Bashforth 4 integrator for body rates
(`simulation/integrator/rate/rotational = 5`).

The report claims:
- AB4 matches NASA's tumbling-brick case, while JSBSim's default (Euler) does not.
- AB4 blows up to NaN on a hard inverted ground impact at 120/240 Hz but not at 480/1000 Hz.
- AB4 makes gear contact chatter because JSBSim's friction solver (`FGAccelerations::CalculateFrictionForces`)
  assumes an Euler step.
- An integrator-aware fix existed upstream in 2010 (commit `53709ba8`) and was removed in 2011 (commit `40279c20`).

Check, as independently as you can:

1. **Friction cause.** Is the friction-solver explanation correct? Read the JSBSim v1.3.3 source (`git clone
   --branch v1.3.3 https://github.com/JSBSim-Team/jsbsim`) and the two commits. Was the 2010 code really removed,
   or moved or replaced? Is there anything else in the ground model that interacts with the integrator?
2. **"480 Hz is enough."** This rests on one crash scenario (f16_test) and one taxi (f16_runway_test), plus a
   c172x take-off. Is that enough evidence? Run other aircraft or scenarios to try to break it: hard landings,
   ground impacts at other attitudes, other aircraft with STRUCTURE contact points, resting on the gear for 60 s.
3. **Crash NaN.** What actually causes the NaN on f16_test's inverted impact? The report only guesses (stiff
   contact springs). Isolate it if you can.
4. **NASA yardstick.** The "inside NASA's spread" yardstick was changed to a ratio after the first version said
   "NO" on borderline cases. Is the new yardstick fair? Do the raw distances in `results/02-test4-nasa.txt`
   support the claim that "AB4 sits on NASA's solutions"?
5. **Missing alternatives.** Are better options missing from the report's phase 2 list (restore the 2010
   friction; implicit midpoint body rates as in the PteroLabsAI/jsbsim fork PRs 12–13; switch integrators on the
   ground)? Are there risks in each that the report does not mention?

## Second priority: other claims to check

6. **Parity explanation.** c1723 and f16_test differ from native far beyond rounding. The report blames the
   scripts' sensitivity, because native JSBSim against itself with the start altitude raised by 1e-8 ft diverges
   similarly. Is that argument sound, or could a real difference in our build hide behind it? Propose and run a
   stronger test if you can.
7. **Binding correctness.** Review `wasm/bindings.cpp`, `src/jsbsim.ts` and `wasm/CMakeLists.txt`:
   - exception handling: is every path caught, and are there leaks;
   - handle bounds;
   - the bulk `Float64Array` views after WebAssembly memory growth;
   - whether exception flags really reach all JSBSim code;
   - anything that could silently give wrong numbers.
8. **Benchmarks and the build choice.** Are the timing methods sound, and is choosing `-fwasm-exceptions` as
   the default well supported?
9. **Anything else** you think is wrong, unsupported or missing.

## How to run (Node 22, Python 3.11+)

```sh
npm ci
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
npx tsx tests/smoke.ts
scripts/run-tests.sh          # tests 1-5, several minutes; or a subset, e.g. scripts/run-tests.sh 4 5
```

- The WebAssembly build is committed in `wasm/bin/`; you do not need Emscripten to run the tests.
- `tests/ab4/rate_sweep.ts <script>` runs the integrator and rate sweep for any JSBSim script in
  `jsbsim-data/scripts/`.
- You may write new scripts or initial-condition files for extra scenarios.
- If network access blocks `npm ci`, `pip`, or cloning JSBSim, say exactly what was blocked. Review what you can
  from the files and mark those findings as not run.

## Rules

- Do not change JSBSim's physics or the existing tests to make results look better.
- Do not push to `main`. Put any new test code on a branch named `review/codex-02`.
- Label every finding with one of:
  - **Verified**: checked against something the other agent did not produce, such as native JSBSim, NASA data,
    JSBSim source or history, or a published reference.
  - **Supported**: your own test shows it, without an outside answer key.
  - **Reasoned**: logic only, not tested.
- Give the file, command or result behind each finding. Do not soften findings.

## Deliverable

Write `REVIEW-codex-02.md` on the `review/codex-02` branch, in plain language for a non-expert owner:

1. **Verdict.** One paragraph: can the owner build phase 2 on this work as it stands, and is the integrator
   plan (AB4 at 480–1000 Hz) sound?
2. **Findings.** A table ordered by severity. Columns: claim checked, your verdict (holds / weakened / wrong /
   could not check), label, evidence.
3. **Missed issues.** Problems the original report does not mention.
4. **Tests to add.** Specific tests to add before phase 2, with a pass/fail condition for each.
5. **What you could not check, and why.**
