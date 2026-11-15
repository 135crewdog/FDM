# Claude Code prompt: session 04, later gates, candidates 2 and 3, integrator decision

**Chat name: `FDM 04 Work: integrator decision`** (naming convention: `prompts/README.md`).

Before starting (user): use the same cloud environment as sessions 02 and 03 ("FDM build", with network access
for emsdk, GitHub, PyPI and npm). Paste everything below the line into a **new** Claude Code session on
`135crewdog/FDM`.

---

**Name this chat `FDM 04 Work: integrator decision`.** If you have a tool that renames the session, use it now.
If you do not, make the first line of your first message: "Please rename this chat to: FDM 04 Work: integrator
decision".

Read `CLAUDE.md`, then `REPORT-03.md` (especially the Evidence ledger and "What remains for session 04"), then
`GATES.md`.

Where we are:

- Our WebAssembly build of JSBSim v1.3.3 is validated, and the defects found by the independent review are fixed.
- Acceptance gates G1 to G6 exist and are frozen (commit `164c1d0`). Nothing passes all of them yet:
  - The floor (JSBSim's default Euler body rates plus Buss 2 attitude) is inaccurate in the air and fails hard
    landings at low step rates.
  - Candidate 1 (integrator-aware friction, patch 0001) makes aircraft settle at rest with AB2, AB3 and AB4, and
    keeps AB3/AB4's accuracy in the air. It does not fix hard landings or crashes.
- Hard-landing and crash results are numerically chaotic: one run per case is partly luck.

This session adds the later gates, tests candidates 2 and 3, and ends with a recommendation on the integrator.

Keep messages to me short and plain. I am not a flight-dynamics expert. Follow the evidence-label rule and the
gates rule in `CLAUDE.md`.

## Working rules

- Commit and push at each checkpoint below, to the session branch **and to `main`** (you have my permission to
  push to `main`).
- If you run low on time or context, stop at a checkpoint, write what is done and what is left in
  `REPORT-04.md`, and push.
- Do not change JSBSim's physics except through a patch file in `wasm/patches/`. Each patch must be small,
  explained in its header, switched by a property whose default is "unchanged JSBSim", and proven bit-identical
  when off (`tests/native/verify_key.sh patched unpatched`, `tests/native/verify_wasm_patch_off.sh`).
- Never change a gate, tolerance or yardstick after seeing a candidate's results. The existing gate files stay
  exactly as they are. New gates get new names and are committed before any new candidate runs.
- When an earlier explanation turns out wrong, say so plainly.

## Step 1: set up and confirm session 03 (checkpoint)

- Build everything as `REPORT-03.md` "How to reproduce" describes: both native answer keys, the patched and the
  unpatched WebAssembly.
- Run tests 0 to 5 and the two "patch off is bit-identical" checks.
- Re-run the floor and `c1-ab3` through the existing gates. The verdicts must match session 03's. Hard-landing
  and crash cells may differ by luck; say which did.

## Step 2: later gates, committed before any new candidate runs (checkpoint)

Add these as new gates in a new file (for example `tests/gates/gates-04.json` plus a section "Later gates" in a
new `GATES-04.md`). Do not edit the frozen files. Record the commit hash in `REPORT-04.md` before running
candidate 2 or 3.

- **G5b Rigid body after start-up:** the same bodies, spins and rates as G5, but drift measured from 1 s to 60 s,
  so that JSBSim's multistep start-up is not counted. Same 1e-6 limit.
- **G2b Hard landing, repeated:** each G2 case run many times (at least 20) with tiny perturbations of the
  starting state. Report the fraction that stays finite. Choose and write down the perturbation size and the
  pass fraction before running.
- **G3b Extreme impacts, repeated:** the same idea for G3, compared with the floor's fractions.
- **Which step rates count.** My starting position: the game can afford 480 to 1000 Hz (session 02 iPhone
  timings), so the decision is judged at 480 and 1000 Hz, and 120 and 240 Hz are reported. If the evidence argues
  for something else, say so before running candidates, not after.
- Optional, if time allows: a ground energy balance gate (the review's "Tests to add").

Be honest in the report that these gates were written after the floor's and candidate 1's results on G1 to G6
had been seen. Then run the floor and candidate 1 (AB4, AB3, AB2) through the new gates.

Also test the one explanation session 03 left untested (REPORT-03 ledger 15): that the gear's spring-damper is
too stiff for the AB schemes' stability limit. A sweep of the gear damping coefficient, or the eigenvalues of
the linearised gear modes times dt, would confirm or refute it.

## Step 3: candidate 2, implicit-midpoint body rates (checkpoint)

- Source: PteroLabsAI/jsbsim pull request 13 (unreviewed fork; see REPORT-02). Fetch it with git. If it cannot be
  reached, say so and implement from the description.
- Bring it in as patch 0002 with its own switch, default off, bit-identical when off.
- Count how often its fallback and failure paths are taken (Newton non-convergence, singular Jacobian, Euler
  fallback), and report its cost per step.
- Run it through every gate, old and new, with and without patch 0001, with Buss 2 attitude.

## Step 4: candidate 3, switching integrators on contact (checkpoint)

- AB3 or AB4 body rates in the air, Euler while any contact point touches the ground. Detect every contact point
  (BOGEY and STRUCTURE), not `gear/wow`.
- Implement it so that native JSBSim and the WebAssembly build run the same logic (a patch is the natural
  place).
- Test variants: AB3 and AB4; with and without patch 0001; and how the switch behaves on touch, release and
  bouncing (no extra impulse, no rapid flapping).
- Run each through every gate, old and new.

## Step 5: recommendation

- One table: floor, candidate 1, candidate 2, candidate 3 against every gate, with the numbers.
- Recommend one configuration and one step rate, or say plainly that nothing is good enough and what is missing.
- Change the shipped default only if the recommended configuration passes every gate at the judged rates.
  Otherwise leave the default as it is.

## Finish

Write `REPORT-04.md`. Put the Evidence ledger near the top, followed by:

- the later gates and their commit hash;
- the table of every candidate against every gate;
- the recommendation, and what would change it;
- which claims an independent reviewer should check first.

Then:

- Update `CLAUDE.md`.
- Write `prompts/codex-review-04.md`, a prompt for an independent review of sessions 03 and 04. Its chat name is
  `FDM 04 Review: integrator decision`. Put the "name this chat" line at the top, as in this prompt.
- Write `prompts/05-<topic>.md` for the next session, with its chat name, following `prompts/README.md`.
- Commit and push.
- End your last message with what you need from me (for example: open the test page on the iPhone and paste the
  results).
