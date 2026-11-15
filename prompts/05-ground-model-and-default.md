# Claude Code prompt: session 05, landing gates that test landings, wheel-compression limit, default integrator

**Chat name: `FDM 05 Work: ground model and default integrator`** (naming convention: `prompts/README.md`).

Before starting (user):

- Run the independent review first (`prompts/codex-review-04.md`). This session reads its result.
- Use the same cloud environment as sessions 02 to 04 ("FDM build", with network access for emsdk, GitHub, PyPI
  and npm). Paste everything below the line into a new Claude Code session on `135crewdog/FDM`.

---

**Name this chat `FDM 05 Work: ground model and default integrator`.** If you have a tool that renames the session, use
it now. If you do not, make the first line of your first message: "Please rename this chat to: FDM 05 Work: ground
model and default integrator".

Read `CLAUDE.md`, then `REPORT-04.md` (especially the Evidence ledger, "Recommendation" and "What remains for
session 05"), then `REVIEW-codex-04.md` if it exists, then `GATES.md`, `GATES-04.md` and `GATES-04b.md`.

Where we are:

- Session 04 recommended an integrator but did not make it the default: `c3-ab4` at 480 Hz (AB4 body rates in the
  air, Euler while any contact point touches the ground, Buss 2 attitude; patch 0003).
- It passes rest, NASA accuracy, energy conservation and parity. Every configuration, JSBSim's defaults included,
  fails the hard-landing gate, and only through two test aircraft (737, ah1s) that never land.
- Every crash blow-up that was checked starts with JSBSim's wheel code reporting an impossible strut compression
  (`FGLGear.cpp`, BOGEY contacts: no limit, and a division by a projection that goes to zero).
- Two lessons from session 04, both in `CLAUDE.md`: check what a scenario really does before trusting its name,
  and "finite" is not "sane".

This session makes the ground trustworthy enough to switch the default, or says plainly why not.

Keep messages to me short and plain. I am not a flight-dynamics expert. Follow the evidence-label rule and the gates
rule in `CLAUDE.md`.

## Working rules

- Commit and push at each checkpoint below, to the session branch and to `main` (you have my permission to push to
  `main`).
- If you run low on time or context, stop at a checkpoint, write what is done and what is left in `REPORT-05.md`,
  and push.
- Do not change JSBSim's physics except through a patch file in `wasm/patches/`: small, explained in its header,
  switched by a property whose default is "unchanged JSBSim", and proven bit-identical when off.
- Never change a gate, tolerance or yardstick after seeing a result. All existing gate files stay exactly as they
  are. New gates get new names and are committed before anything is run through them.
- Do not edit an existing patch file, not even its comments, without rebuilding and re-running what depends on it
  (its hash is in the result files).
- When an earlier explanation turns out wrong, say so plainly.

## Step 1: set up, confirm session 04, answer the review (checkpoint)

- Build everything as `REPORT-04.md` "How to reproduce" describes. Run tests 0 to 5 and the patch-off checks.
- Re-run the floor and `c3-ab4` through every gate. The reports must match session 04's.
- If `REVIEW-codex-04.md` exists: list its findings, and for each say "agree and will fix", "agree, no action
  needed" or "disagree, because". Fix what is wrong before going on. If the review says `c3-ab4` is not sound,
  stop after this step and report.

## Step 2: gates that test landings, committed before anything runs through them (checkpoint)

Write them in new files (for example `tests/gates/gates-05.json` and `GATES-05.md`). Record the commit hash in
`REPORT-05.md` before running anything through them. Say honestly what had been seen when they were written.

- **G2d Landing.** Only aircraft that can land in these tests. Check that each one really lands with JSBSim's
  defaults in an easy case before it is admitted, and say which were left out and why. Flown forward (check the
  body-axis velocity), at each aircraft's own sensible touchdown speed and attitude, at several descent rates
  from firm to hard (my starting position: 5, 10, 15 and 30 ft/s). Repeated with tiny perturbations, as G2b.
- **Judged on more than "finite".** For every run: the aircraft stays above the ground, stays upright, does not
  gain mechanical energy from the ground beyond a stated tolerance, and no wheel reports a compression beyond its
  strut's travel (choose and write down the limits before running).
- **G3d Crash cases** for the wheel-compression limit: the impacts where a wheel currently reports an impossible
  compression. Judged on: finite, no runaway, and no ground force above a stated multiple of the aircraft's
  weight.
- Keep judging at 480 and 1000 Hz unless the review argues otherwise. If 960 Hz is to replace 1000 Hz, say so
  here, before running.
- The ground energy balance is the review's "Tests to add" from session 02; this is where it gets written.

## Step 3: patch 0004, a limit on wheel compression (checkpoint)

- `FGLGear.cpp`, BOGEY contacts: `compressLength = height * normalZ / LGearProj`, and the strut force is divided
  by the same projection again. Decide what the right limit is (for example: no contact when the leg is close to
  parallel to the ground; compression capped at a strut travel) and explain the choice in the patch header.
- Its own switch, default off, bit-identical when off.
- First test REPORT-04 ledger 9 as a claim: with the limit on, do the blow-ups of `blowup_cause.py` disappear?
- Consider whether the game's own aircraft should simply have complete airframe (STRUCTURE) contact points, and
  whether that alone is enough. Say which of the two (patch, or contact points) you recommend, or both.

## Step 4: candidates through the new gates (checkpoint)

- The floor, `c3-ab4` and `c2-mid`, each with and without patch 0004, through every gate, old and new.
- One table, with the numbers.

## Step 5: the default, and crash detection

- **Change the wrapper's default integrators to the recommended configuration only if it passes every gate of
  step 2 and G1, G4, G5b and G6 at the judged rates.** Otherwise leave the default and say what is missing.
- If the default changes: update `src/jsbsim.ts`, the binding tests and `CLAUDE.md`; rebuild the test page; and
  give me the exact steps to re-run the timing on the iPhone.
- Add crash detection to the wrapper (not to JSBSim): a call that tells the game the aircraft is tipped over on
  the ground, below the surface, or non-finite, so the game can stop the simulation. Tested with the crash cases.
- About candidate 2: REPORT-04 says it would be the simplest choice if G4's limit (2e-6 deg/s) were looser. If I
  have answered that question in this prompt's "From the user" section below, follow the answer. If not, leave G4
  as it is and say again what the choice costs.

## From the user

(Add here: your answer on G4's limit, the review's main points if you want to stress any, and anything else.)

## Finish

Write `REPORT-05.md`. Put the Evidence ledger near the top, followed by:

- the new gates and their commit hash;
- the table of every candidate against every gate;
- the decision on the default, and what would change it;
- which claims an independent reviewer should check first.

Then:

- Update `CLAUDE.md`.
- Write `prompts/06-<topic>.md` for the next session, with its chat name, following `prompts/README.md`. If the
  integrator and ground are settled, the next topic is the first step of the wing-strip work (external forces set
  from JavaScript every step).
- Add rows to the table in `prompts/README.md`.
- Commit and push.
- End your last message with what you need from me (for example: open the test page on the iPhone and paste the
  results).
