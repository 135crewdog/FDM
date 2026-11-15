# Independent review of sessions 03 and 04 (prompt for Codex)

**Chat name: `FDM 04 Review: integrator decision`** (naming convention: `prompts/README.md`).

Paste everything below the line into a new Codex task on the repository `135crewdog/FDM` (branch `main`).

---

**Name this chat `FDM 04 Review: integrator decision`.** If you have a tool that renames the session, use it now. If
you do not, make the first line of your first message: "Please rename this chat to: FDM 04 Review: integrator
decision".

You are an independent reviewer. Another AI agent (Claude Code) did the work in this repository. The owner is not
a flight-dynamics or simulation expert. They cannot judge the physics themselves and want an outside check before
they build more on it. Your job is to find what is wrong, weak or overstated. Agreeing is not the goal. Treat
every statement in `REPORT-03.md`, `REPORT-04.md` and `CLAUDE.md` as a claim to check.

Keep messages to the owner short and plain.

## Background

- The flight dynamics model for a flight-sim game that runs as a web app on iPhone: JSBSim v1.3.3 compiled to
  WebAssembly, plus a small binding (`wasm/bindings.cpp`, `src/jsbsim.ts`).
- You reviewed session 02 (`REVIEW-codex-02.md`). Sessions 03 and 04 answered that review: defects fixed,
  acceptance gates written before candidates were run, and four integrator configurations tested.
- Read `CLAUDE.md`, then `REPORT-04.md` (start with its Evidence ledger and "Earlier explanations that turned out
  wrong"), then `GATES.md`, `GATES-04.md`, `GATES-04b.md`, then `REPORT-03.md`.
- Raw results: `results/04-*.txt` and `results/03-*.txt`. Patches: `wasm/patches/`. Gate code: `tests/gates/`.
- How to build and run: `CLAUDE.md` "How to run" and `REPORT-04.md` "How to reproduce". The native answer keys
  are built by `scripts/build-native.sh`; you do not need Emscripten to check most claims.

## What session 04 concluded

- By its own rule nothing passes every gate, so the shipped default is unchanged.
- It recommends carrying forward `c3-ab4` at 480 Hz: AB4 body rates in the air, Euler while any contact point
  touches the ground (patch 0003), Buss 2 attitude, friction as in JSBSim.
- It says the hard-landing gate fails for every configuration only through two aircraft (737, ah1s) that never
  land in any configuration, and that every crash blow-up starts with JSBSim's wheel code reporting an impossible
  strut compression.

## Highest priority: is the recommendation sound?

1. **The reading of the landing gate (REPORT-04 ledger 5 to 7 and 19).** The report recommends on the three
   aircraft that land (c172x, f16, c310) and sets the 737 and ah1s aside. That reading was made after seeing the
   results. Is it fair? Check `results/04-diag-landing-anatomy-*.txt` and `tests/gates/diag/landing_anatomy.py`.
   Would a properly built hard landing of the 737 or ah1s (engines or rotor running, sensible attitude and
   speed) change the picture? Try one.
2. **The cause of the blow-ups (ledger 8, 9).** Read `FGLGear.cpp` in JSBSim v1.3.3 (the lines that compute
   `compressLength` and divide by `LGearProj`). Is "unlimited wheel compression" really what starts every
   failure, or only something that accompanies it? `tests/gates/diag/blowup_cause.py` shows 60 of 60. Test the
   claim directly if you can: limit the compression in a scratch build and rerun the failing cases. Is there a
   second mechanism the report missed (friction on STRUCTURE contacts, which your first review pointed at)?
3. **Patch 0003** (`wasm/patches/0003-body-rate-scheme-on-contact.patch`).
   - Does the contact flag belong to the same instant as the derivative that the step integrates? (It is read in
     `FGFDMExec::LoadInputs` for `ePropagate`.)
   - Is restarting the multistep history on release sound? Is there a case where it loses accuracy that matters
     (touch-and-go, a wheel skipping along the runway)?
   - It changes the accessor that patch 0001 uses to learn the body-rate scheme. Is that right?
   - Is "off" really unpatched JSBSim? (`tests/native/verify_key.sh patched unpatched`.)
   - The report says candidate 3 is bit-identical to the floor on the ground and to AB4 in the air (ledger 16).
     Check it.
4. **Were the gates really fixed first?** `git log` around `e5bcd1d` (later gates), `9fb7f63` (G2c), `18016cb`
   (patches 0002 and 0003), `45a0c73` (results). `GATES-04.md` and `GATES-04b.md` say what had been seen at each
   point. Is anything missing from those lists? Was replacing G2b by G2c legitimate, and is printing the verdict
   both ways enough?
5. **480 Hz.** The NASA gate passes at 480 Hz with a thin margin (1.4e-6 against 2e-6 deg/s). Is 480 Hz a sound
   recommendation, or should it be 960 or 1000 Hz? Is there anything in flight (stiff aerodynamic moments at high
   speed, the planned wing-strip forces set from JavaScript every step) that AB4 at 480 Hz would not tolerate?
   AB4's stability limit is about 7 times tighter than Euler's on the real axis.

## Second priority

6. **Candidate 2** (`wasm/patches/0002-implicit-midpoint-body-rates.patch`): is it the code of PteroLabsAI/jsbsim
   pull request 13 (commit `33384d9`) unchanged apart from the counters? It fails the NASA gate by 15% at 1000 Hz.
   Is G4's limit (2e-6 deg/s after 30 s) the right yardstick for a game, or is the report right to leave that to
   the owner? Is the scheme's failure path (it throws) acceptable?
7. **The later gates themselves** (`GATES-04.md`): G5b from 1.0 s; 21 runs with perturbations of 1e-6; a pass mark
   of every run; the G3b allowance of 5%. Are they fair? The report says the G3b rule turned out not to be useful
   (ledger 19). Do you agree?
8. **The gear-damper test** (ledger 10, 11; `tests/gates/diag/gear_damper.py`): the linear model predicts the c310
   within 6 to 26% and is far too cautious for the other aircraft. Is the conclusion (right for the c310 at rest,
   wrong for the landings) supported?
9. **Patch 0001's mathematics** (`wasm/patches/0001-integrator-aware-friction.patch`, mode 1): still unreviewed
   from session 03. It is not needed by the recommendation but it is in the build.
10. **Binding** (`wasm/bindings.cpp`, `src/jsbsim.ts`): integrator id 10 and the on-contact setting are now
    validated. Is any path unguarded? Does `setIntegrators` leave a half-applied state on an error?
11. **Evidence labels.** For each row of REPORT-04's ledger: is the label (Verified, Supported, Reasoned) earned?
    Name any that should be lower.

## What to deliver

Write `REVIEW-codex-04.md` in the repository root, and put any test code you write in `tests/review/` and its
output in `results/review-codex-04/`. In the review:

- Start with a short verdict in plain words: is `c3-ab4` at 480 Hz a sound choice, yes, no, or not yet, and why.
- Then a table of findings: what you checked, how, what you found, how sure you are.
- Then what session 05 should do differently from `prompts/05-ground-model-and-default.md`.
- Say what you could not check.

Do not change the gate files, the patches or the binaries. Do not post anything publicly (issues, pull requests).
Commit and push your review to `main`.
