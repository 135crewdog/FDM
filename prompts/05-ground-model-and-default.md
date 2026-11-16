# Claude Code prompt: session 05, fixtures and gates that test what they say, ground safety, two candidates

**Chat name: `FDM 05 Work: ground model and default integrator`** (naming convention: `prompts/README.md`).

Rewritten on 2026-11-16 after the independent review (`REVIEW-codex-04.md`, verdict "not yet").

Before starting (user): use the same cloud environment as sessions 02 to 04 ("FDM build", with network access for
emsdk, GitHub, PyPI and npm). Paste everything below the line into a **new** Claude Code session on
`135crewdog/FDM`.

---

**Name this chat `FDM 05 Work: ground model and default integrator`.** If you have a tool that renames the session,
use it now. If you do not, make the first line of your first message: "Please rename this chat to: FDM 05 Work:
ground model and default integrator".

Read `CLAUDE.md`, then `REPORT-04.md` (its "Review outcome" section first), then `REVIEW-codex-04.md` in full
(especially "What session 05 should do differently"), then `GATES.md`, `GATES-04.md` and `GATES-04b.md`.

Where we are:

- The shipped default is JSBSim's (Euler body rates). Nothing has passed every gate.
- Two candidates remain:
  - **`c3-ab4`**: AB4 body rates in the air, Euler while any contact point touches the ground (patch 0003). Its
    step rate is open. 480 Hz was recommended and withdrawn: AB4 is unstable there under a stiff damping moment,
    and repeated switching accumulates error.
  - **Midpoint at 1200 Hz** (`c2-mid`, patch 0002): meets the NASA limit as frozen, tolerates stiff moments as
    Euler does, has no switch. It throws if Newton's method fails.
- Session 04's landing gates used unsuitable fixtures (every aircraft at 59 kt, engines off). A 737 flown properly
  lands every time.
- The crash blow-ups have at least two mechanisms: JSBSim's wheel geometry (division by a projection that goes to
  zero, no limits), and friction on airframe contacts with AB4.

This session builds fixtures and gates that test what they say, makes the ground safe enough, and runs both
candidates through them. It changes the default only if the rule in step 6 is met. It is a large session:
**stopping at a checkpoint with a clear report is a good outcome.**

Keep messages to me short and plain. I am not a flight-dynamics expert. Follow the evidence-label rule and the gates
rule in `CLAUDE.md`, and its lessons from session 04 (check what a scenario really does; "finite" is not "sane"; a
fixture must fly the aircraft the way it flies; a free-body test says nothing about applied moments; an
association is not a cause).

## Working rules

- Commit and push at each checkpoint below, to the session branch and to `main` (you have my permission to push to
  `main`).
- If you run low on time or context, stop at a checkpoint, write what is done and what is left in `REPORT-05.md`,
  and push.
- Do not change JSBSim's physics except through a patch file in `wasm/patches/`: small, explained in its header,
  switched by a property whose default is "unchanged JSBSim", and proven bit-identical when off.
- Never change a gate, tolerance or yardstick after seeing a result. All existing gate files stay exactly as they
  are. New gates get new names and are committed before any candidate is run through them.
- A fixture has to be tried before it can be trusted. Trying a fixture on JSBSim's defaults in an easy case is
  allowed before the gates are frozen, and every such trial must be listed in the gates document.
- Do not edit an existing patch file, not even its comments, without rebuilding and re-running what depends on it.
- Label a finding Verified only when it was checked against an answer we did not produce. Agreement with our own
  earlier results is Supported.
- Test an explanation by removing the cause, not by counting how often it appears.
- When an earlier explanation turns out wrong, say so plainly.

## Step 1: set up, confirm, close the review's defects (checkpoint)

- Build everything as `REPORT-04.md` "How to reproduce" describes. The build scripts now stop on a compiler error
  (`tests/build/selftest_patches.sh` tests it); confirm that. Run tests 0 to 5 and the patch-off checks.
- Re-run the floor and `c3-ab4` through every existing gate. The reports must match session 04's.
- Fix the binding gaps the review found, each with a regression test that fails before and passes after:
  - a script's own negative or zero time step must be rejected;
  - patch 0003's `contact-active` and `contact-switches` and patch 0002's counters must not be writable from
    outside (or the switch must not depend on a writable property); a negative hold time and an unknown release
    mode must be rejected. If this needs a change to a patch, it becomes a new patch version: rebuild, prove
    "off" is still bit-identical, and say which earlier results it could touch;
  - `setIntegrators` must read its argument once and either apply everything or nothing.

## Step 2: fixtures, then gates, committed before any candidate runs through them (checkpoint)

Write them in new files (for example `tests/gates/gates-05.json`, `GATES-05.md`). Record the commit hash in
`REPORT-05.md` before running any candidate. List honestly what had been seen when they were written, including
every fixture trial and everything in `REVIEW-codex-04.md`.

**Fixtures first.** For each aircraft, an approach that suits it: its own speed, attitude, flaps and gear, engines
or rotor running where it needs them, a simple controller if it needs one. Start from the review's 737 fixture
(`tests/review/review04_powered_landing.py`). Read back the real body-axis velocity, attitude, configuration and
engine state, and the **actual** descent rate at touchdown. Keep the 737 in. Build a rotor-running ah1s approach
if you can; if you cannot, say so and leave it out as "not tested", not as "cannot land".

**Then the gates.** My starting positions; argue with them before freezing, not after:

- **G2d Landing.** Every admitted aircraft, several touchdown descent rates from firm to hard, at each candidate's
  step rates. Judged on physical conditions, each with a limit written down beforehand: stays above the ground;
  stays upright; no wheel beyond its strut travel; ground force within a stated multiple of weight; and an energy
  budget (kinetic plus potential energy, against the work of springs, dampers, friction, engines and
  aerodynamics). "No energy gain" alone is not a valid test.
- **G7 Forced flight.** Stability and accuracy with moments applied, in the air: damping and stiffness moments of
  known strength with a known exact answer, both inside JSBSim and written from JavaScript every step (the way
  the wing-strip forces will arrive, including the one-step delay the review points out). First establish how
  fast the fastest moment in the game can be: compute it for the test aircraft over their flight envelope, and
  state the margin wanted for the wing-strip work. Then gate on that, not on a number picked to suit a candidate.
- **G8 Repeated contact.** Touch-and-go and a wheel skipping along the runway: accumulated error in body rates and
  attitude against a reference run at a much higher step rate. Start from `tests/review/review04_release.py`.
- **G3d Crash containment, case by case.** Replace G3b's pooled count. For each crash case: finite, no runaway, no
  ground force above a stated multiple of weight. A case that newly fails counts, whatever else improves.
- **Step rates, said before running:** `c3-ab4` at 480, 960 and 1000 Hz; midpoint at 960 and 1200 Hz; the floor at
  the same rates as reference. G1, G4, G5b and G6 are run at the new rates with their frozen limits (as new,
  named readings, not as edits). If you think other rates should be judged, say so here.
- G5b excludes the multistep start-up; G8 is where restart errors must show.

## Step 3: ground safety, patch 0004 (checkpoint)

- The wheel geometry in `FGLGear.cpp` needs more than a compression cap (the review showed a cap alone makes it
  worse). Look at the leg projection, the compression and rebound speed, the projected force, the contact
  location, and whether the result converges as the step shrinks. The review's scratch build (2 ft cap, no
  contact when `LGearProj <= 0.1`) is a diagnostic, not a design: choose the limits from the aircraft's own data
  where you can, and explain them in the patch header.
- Its own switch, default off, bit-identical when off.
- Test it as an explanation first: which failures does it remove, which remain, and are the remaining forces
  sane? Then test the second mechanism separately (friction on airframe contacts; the f16 crash with AB4 on
  contact) and say whether `c3-ab4` and midpoint are exposed to it.
- Say whether the game's own aircraft should also carry complete airframe contact points.

## Step 4: both candidates through every gate (checkpoint)

- The floor, `c3-ab4` and `c2-mid`, each with and without patch 0004, at the step rates fixed in step 2, through
  every gate, old and new, native and WebAssembly.
- One table, with the numbers. Report cost per step for each candidate at its rate.

## Step 5: crash containment in the wrapper (checkpoint)

- A check after **every physics step** (not once per drawn frame): non-finite state, runaway rates, below the
  surface, tipped over on the ground, ground force beyond the limit. On a hit: stop before the next step, keep
  the last accepted state for drawing, tell the game why.
- Decide and test what happens when `run` throws (JSBSim error, or midpoint's Newton failure): the step has
  already advanced time and may have changed the attitude, so catching the error is not a rollback.
- Tested with the crash cases of step 2.

## Step 6: decision

- **Change the wrapper's default integrators only if one candidate, at one step rate, passes every gate of step 2
  and G1, G4, G5b and G6 at that rate, on both platforms.** Otherwise leave the default and say what is missing.
- If both pass, recommend one and say what the other would cost or save. If neither passes, say which is closer
  and why.
- If the default changes: update `src/jsbsim.ts`, the binding tests and `CLAUDE.md`; rebuild the test page so that
  it also times the chosen configuration; and give me the exact steps to run it on the iPhone.

## From the user

(Add anything you want stressed. No answer on the NASA limit is needed any more: midpoint at 1200 Hz meets it as
it is.)

## Finish

Write `REPORT-05.md`. Put the Evidence ledger near the top, followed by:

- the new fixtures and gates, their commit hash, and what had been seen before it;
- the table of every candidate against every gate;
- the decision on the default, and what would change it;
- which claims an independent reviewer should check first.

Then:

- Update `CLAUDE.md`.
- Write `prompts/codex-review-05.md` (chat name `FDM 05 Review: <topic>`) if a default was chosen or changed, and
  `prompts/06-<topic>.md` for the next work session, following `prompts/README.md`. If the integrator and ground
  are settled and reviewed, the next topic is the first step of the wing-strip work.
- Add rows to the table in `prompts/README.md`.
- Commit and push.
- End your last message with what you need from me.
