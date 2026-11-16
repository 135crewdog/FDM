# Session 06 (prompt for Claude Code)

**Chat name: `FDM 06 Work: answer the review, first step of wing-strip forces`** (naming convention:
`prompts/README.md`).

Paste everything below the line into a new Claude Code chat on the repository `135crewdog/FDM`.

**Do not start this session before `REVIEW-codex-05.md` exists** (run `prompts/codex-review-05.md` first). If the
review says the default is not sound, this session's first job is to answer it, and the wing-strip work waits.

---

**Name this chat `FDM 06 Work: answer the review, first step of wing-strip forces`.** If you have a tool that
renames the session, use it now. If you do not, make the first line of your first message: "Please rename this
chat to: FDM 06 Work: answer the review, first step of wing-strip forces".

Read `CLAUDE.md`, then `REVIEW-codex-05.md` in full, then `REPORT-05.md` and `GATES-05.md`.

Where we are:

- The wrapper's default is implicit-midpoint body rates, Buss 2 attitude, strut limits (patch 0004), 1200 Hz
  (`c2-mid-g`). It passed every gate in session 05. `c3-ab4-g` at 960 or 1000 Hz passed as well and is the
  fallback.
- Crash containment exists in the wrapper (off until switched on).
- The iPhone has not timed the new default unless `results/` holds a file `06-page-iphone-*.txt` or the owner
  pastes the page's output at the start of this chat.

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

- For each finding of `REVIEW-codex-05.md`: agree or disagree in writing, reproduce what you can, and fix what
  needs fixing, each fix with a test that fails before and passes after.
- If the review rejects the default or a gate: do what it asks first. A gate that was wrong is kept, said to be
  wrong, and replaced by a new gate with a new name, committed before anything is re-run.
- If the owner pasted the iPhone results: save them as `results/06-page-iphone-fwasm-exceptions.txt` and report
  the cost of the default (section 5 of the page) in milliseconds per second of flight.

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
