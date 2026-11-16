# Session 06 (prompt for Claude Code)

**Chat name: `FDM 06 Work: answer the review, first step of wing-strip forces`** (naming convention:
`prompts/README.md`).

Paste everything below the line into a new Claude Code chat on the repository `135crewdog/FDM`.

**Do not start this session before `REVIEW-codex-05.md` is in the repository** (on `main`, or on a branch you name
in the chat). The review's verdict is "no, as shipped"; when this prompt was last edited only its three-sentence
summary was known. This session's first job is to answer the review. The wing-strip work waits for that.

---

**Name this chat `FDM 06 Work: answer the review, first step of wing-strip forces`.** If you have a tool that
renames the session, use it now. If you do not, make the first line of your first message: "Please rename this
chat to: FDM 06 Work: answer the review, first step of wing-strip forces".

Read `CLAUDE.md`, then `REVIEW-codex-05.md` in full, then `REPORT-05.md` and `GATES-05.md`.

Where we are:

- Session 05 made midpoint body rates, Buss 2 attitude, strut limits (patch 0004), 1200 Hz the wrapper's default
  (`c2-mid-g`). It passed every gate. `c3-ab4-g` at 960 and 1000 Hz passed as well.
- **The independent review said "no, as shipped."** Its summary: "NASA passes at 1200 Hz, but scripts and resets
  can silently leave the tested configuration. Output protection has gaps, and damping headroom does not
  establish spring stability." `REPORT-05.md` "Review outcome" answers the summary only; the full review had not
  been read.
- Already checked (`results/05-diag-spring-headroom.txt`): the third point is right. Midpoint treats applied
  moments explicitly and adds energy on lightly damped springs; `c3-ab4` does not when the moment is computed
  inside JSBSim; written from JavaScript both do. Session 05's reason for preferring midpoint covered dampers
  only. **The choice between the two configurations is open again.**
- The default is unchanged in the code and is not cleared to build on.
- The iPhone has timed the default: 10 to 14 microseconds per step, 12 to 16 ms per second of flight
  (`results/05-page-iphone-fwasm-exceptions.txt`).

Keep messages to me short and plain. I am not a flight-dynamics expert. Follow the evidence-label rule and the
gates rule in `CLAUDE.md`, and its lessons (check what a scenario really does; "finite" is not "sane"; old gates
can pass for the wrong reason; a write that is silently ignored; an association is not a cause).

## Working rules

- Commit and push at each checkpoint, to the session branch and to `main` (you have my permission to push to
  `main`).
- If you run low on time or context, stop at a checkpoint, write what is done and what is left in `REPORT-06.md`,
  and push.
- Never change a gate, tolerance or yardstick after seeing a result. New gates get new names and are committed
  before anything is run through them.
- Do not change JSBSim's physics except through a patch file in `wasm/patches/`, with a switch that defaults to
  "unchanged JSBSim" and a proof that "off" is bit-identical. Do not edit an existing patch file.
- Label a finding Verified only when it was checked against an answer we did not produce.

## Step 1: answer the review (checkpoint)

- Read `REVIEW-codex-05.md` in full. For each finding: agree or disagree in writing, reproduce what you can
  (its scripts are in `tests/review/review05_*`), and fix what needs fixing, each fix with a test that fails before
  and passes after. Correct `REPORT-05.md` "Review outcome" where it guessed wrong.
- **The default must not be left silently.** A script with its own time step, `simulation/reset`, a second
  `run_ic`, a re-initialisation inside JSBSim, a property written by a script event: for each, the wrapper either
  keeps the configuration (re-applies it and verifies it) or refuses to step and says why. Decide which, test
  every route the review names and any you find.
- **Close the gaps in the output protection** that the review names. Known before reading it: after a halt,
  `readOutputs()` and `getProperty` read the refused state; the bulk outputs are zeros until first read.
- **A gate for lightly damped springs, before deciding again.** New name (G7b), new file, committed before either
  configuration runs through it; `GATES-05.md` and its files stay as they are. First establish what the game can
  contain: the damping ratios and frequencies of the test aircraft's own modes over their envelope (extend
  `tests/gates/envelope05.py`), and say what margin the wing-strip work needs. Then gate on that, with the moment
  computed inside JSBSim and written from JavaScript, on both platforms. `results/05-diag-spring-headroom.txt`
  has been seen: list it.
- **Decide again between `c2-mid-g` (1200 Hz) and `c3-ab4-g` (960 or 1000 Hz)** with the new gate and the
  review in hand. The rule is unchanged: a configuration is the default only if it passes every gate at its
  rate on both platforms. If the default changes, update `src/jsbsim.ts`, the binding tests, the page and
  `CLAUDE.md`, and say so at the top of the report.
- If the one-step delay of forces written from JavaScript is what limits both configurations (it adds energy to
  springs with either), say so plainly: it then belongs to step 2, not to the choice of integrator.

## Step 2: how wing-strip forces enter JSBSim (checkpoint)

The game will compute aerodynamic forces on strips of the wing in JavaScript and hand them to JSBSim every step.
Before any aerodynamics is written, establish the plumbing and its limits:

- **Where the forces go.** JSBSim's `external_reactions` (forces and moments set by property) through the bulk
  input. Decide: one force per strip at its location, or one summed force and moment at the centre of gravity.
  Measure the cost of each for 20 and 40 strips at 1200 Hz (Node, and the page for the iPhone).
- **The one-step delay.** A value written before step k acts on the state after step k-1, and JSBSim's step k
  first integrates the derivative stored in step k-1 (`REPORT-05.md` ledger 9). Measure what that does to a
  strip-like load with a known answer (start from G7's probes in `tests/gates/sim05.py`). Decide whether the game
  can live with it, must predict one step ahead, or needs a small patch that lets JSBSim re-evaluate external
  forces inside the step. Any patch follows the patch rule.
- **How stiff are strip forces?** For a simple strip model of the c172x wing (lift-curve slope per strip, no
  stall), compute the roll damping and pitch stiffness it produces over the speed range, and compare with the
  aircraft's own table model (`tests/gates/envelope05.py` gives 8 per second roll damping at 160 kt). State the
  largest damping rate the strips can reach, and compare with what the default tolerates when forces arrive from
  outside (600 per second at 1200 Hz, `results/05-diag-damping-headroom.txt`).

## Step 3: a gate for strip forces, before the strip model (checkpoint)

Write and commit, before running the default or `c3-ab4-g` through it:

- a wing made of strips with a lift law simple enough to have a closed-form answer (roll damping of a flat wing:
  the roll rate decays exponentially with a rate you can compute by hand), flown in JSBSim with the strips' forces
  written from JavaScript every step and, for comparison, the same law inside JSBSim;
- limits on stability and on accuracy against the closed form, at the default's step rate, on both platforms;
- the same wing through G2d's landings (the strip forces replace the aircraft's own wing), to see that ground
  contact and strip forces live together.

## Step 4: run it (checkpoint)

- The default and `c3-ab4-g` (960 Hz) through the new gate, both platforms. One table.
- If the default fails and the fallback passes, say so and say what switching would cost. Do not switch without
  an independent review.

## From the user

(Add anything you want stressed.)

## Finish

Write `REPORT-06.md`. Put the Evidence ledger near the top, followed by: your answer to the review; the new gate,
its commit hash and what had been seen before it; the table; what the first real strip model needs next; and
which claims an independent reviewer should check first.

Then:

- Update `CLAUDE.md`.
- Write `prompts/07-<topic>.md` for the next work session, and a review prompt if a default or a patch changed,
  following `prompts/README.md`.
- Add rows to the table in `prompts/README.md`.
- Commit and push.
- End your last message with what you need from me.
