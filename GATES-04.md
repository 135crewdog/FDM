# Later gates (session 04)

Written on 2026-11-15, in session 04, **before candidate 2 or candidate 3 was run or even written**. The numbers are
in `tests/gates/gates-04.json`; this file explains them. `GATES.md` and the gates G1 to G6 are unchanged and are
still measured and reported exactly as before.

## What was already known when these gates were written

These gates are **not** blind in the way G1 to G6 were. When they were written, the following had been seen:

- every result of the floor and of candidate 1 (AB4, AB3, AB2) on G1 to G6 (`REPORT-03.md`, `results/03-gates-*`);
- that AB4's G5 failures come from the first 4 steps and AB3 also drifts slowly afterwards (REPORT-03 ledger 17);
- that hard landings are chaotic, and which single runs had failed (REPORT-03 ledger 12 and 14);
- session 04's re-run of the floor and of `c1-ab3` on G1 to G6 (step 1 of session 04).

Not seen when the numbers in `gates-04.json` were chosen: any repeated or perturbed hard-landing run, any drift
measured after start-up as a gate, and any result of candidate 2 (implicit midpoint) or candidate 3 (switching on
contact). Neither candidate's patch existed.

Seen after the numbers were chosen and before this commit (the numbers were not changed afterwards): a check of
the new measuring code on session 03's two **reference** configurations, whose single-run answers were known.

- `ref-ab4` (unpatched AB4) through G5b: the drift from the start equals session 03's G5 numbers (1.3e-5 and
  3.6e-5 at 480 Hz for spins F and G); measured from 1 s it is below 1e-8. This is REPORT-03 ledger 17 again.
- `ref-default` (JSBSim's defaults), 737 only, through the repeated runs: run 0 reproduces the frozen runner's
  single runs exactly (WebAssembly non-finite at 7.650 s at 120 Hz and 7.138 s at 240 Hz, native finite). Over
  the 21 runs the 737's hard landing fails 15 to 19 times at 120 Hz, 17 to 19 at 240 Hz, 11 to 13 at 480 Hz and
  0 (native) or 1 (WebAssembly) at 1000 Hz.
- `ref-ab4` in full (all five aircraft), to test the evaluator: unpatched AB4 survives the hard landing in 0 of
  21 runs with the ah1s at every step rate, in 2 to 10 of 21 with the 737, and in 21 of 21 with the c172x, f16
  and c310. Unpatched AB4 is not a candidate.
- So before this commit I already knew that a configuration with JSBSim's default body rates will probably fail
  G2b at 480 Hz, and may fail it at 1000 Hz by a single run. The pass fraction of 1.0 was written before that was
  seen, and stays.

## The rule

- Frozen once committed: `tests/gates/gates-04.json`, `run_native_04.py`, `run_wasm_04.ts`, `evaluate_04.py` and this
  file. `tests/gates/run-later.sh` refuses to run unless these and session 03's frozen files are committed and
  unchanged.
- Never edit a number after seeing a result. A wrong gate is kept, said to be wrong, and replaced by a new gate
  with a new name.
- As before, every gate is measured in native JSBSim and in our WebAssembly build of the same source, and must
  hold on both.

## Which step rates count

**The decision is judged at 480 Hz and 1000 Hz. 120 Hz and 240 Hz are measured and reported, not judged.**

Reasons, all from evidence that existed before these gates were written:

- The iPhone measurements of session 02 (8 to 13 microseconds per step for the c172x) make 1000 Hz cost about 1%
  of one processor core. Step rate is not what limits the game.
- At 120 and 240 Hz nothing we have passes hard landings, not even JSBSim's defaults (REPORT-03 ledger 8), and
  the Euler body rates are 4 to 8 times less accurate than at 1000 Hz. There is no reason to ship those rates.
- I did not find evidence for judging at any other rate. One caveat, said now and not after the results: a game
  that draws at 60 or 120 frames per second will want a step rate that is a multiple of it (480 or 960 Hz), not
  1000 Hz. All earlier data is at 1000 Hz, so 1000 Hz stays the judged rate here. If the recommendation lands on
  1000 Hz, the recommended configuration must be re-checked at 960 Hz before it ships (a confirmation run, not a
  new gate).

For the decision, a configuration **passes at a step rate R** (480 or 1000 Hz) if all of these hold:

| | gate | read how |
|---|---|---|
| G1 at R | Rest | the frozen G1, its own limits, on the runs at R only |
| G2b at R | Hard landing, repeated | new, below |
| G3b at R | Extreme impacts, repeated | new, below; compared with the floor |
| G4 at R | NASA case 02 | the frozen G4 at R |
| G5b at R | Rigid body after start-up | new, below |
| G6 | Parity | the frozen G6 (measured at 480 Hz; applies to the configuration) |

The original verdicts of G2, G3 and G5 (all four rates, single runs, start-up included) are still printed in every
report. They do not enter the decision: G2b, G3b and G5b measure the same things in a way that single runs and the
start-up steps cannot distort. The original G1 verdict (all four rates) is also still printed.

## The later gates

### G5b Rigid body after start-up

G5's bodies (brick, brick_poi), G5's eight spins and G5's set-up, 60 s. The only difference: the drift of the
rotational kinetic energy and of the magnitude of the angular momentum is measured against their values **at
1.0 s**, over every step from 1 s to 60 s. So JSBSim's multistep start-up (the first few steps, where the history
of past derivatives is filled with copies of the first one) is not counted.

Pass, at a step rate, for both bodies and spins A to G: both drifts below **1e-6** at every step after 1 s. Spin H
is reported, as in G5. The drift from the start (G5's own number) is recorded next to it.

What G5b does not excuse: whatever the start-up did to the state stays in the state. G5 still shows it.

### G2b Hard landing, repeated

G2's hard landing (40 ft up, level, 100 ft/s forward, 30 ft/s down; 5 aircraft; 4 step rates; 15 s), **21 runs
per case**: run 0 is G2's own start, and runs 1 to 20 move the start by a tiny, fixed amount:

- altitude by up to 1e-6 ft (0.3 micrometres),
- vertical speed by up to 1e-6 ft/s,
- pitch angle by up to 1e-6 deg.

The 20 triples were drawn once (uniform, fixed seed) and are written out in `gates-04.json`, so native and
WebAssembly start from exactly the same numbers. Nobody could fly to this precision; the perturbations only
sample the chaos.

A run is good by G2's own conditions: every quantity finite at every step, no body rate above 1e6 rad/s, and the
aircraft touched the ground.

**Pass at a step rate: every run of every aircraft is good, on both platforms (pass fraction 1.0, 210 runs).**
The fractions are reported for every rate.

Why 1.0 and not, say, 0.95: a non-finite state is a crash of the simulation, not of the aircraft, and dropping an
aircraft onto its gear at 30 ft/s is something players will do all the time. A configuration that fails one
landing in twenty would fail in front of every player. The repetition is there so that a pass cannot be luck.

### G3b Extreme impacts, repeated (compared with the floor)

G3's inverted, banked and nose-first impacts, with the same 21 runs per case (15 cases per step rate, 315 runs per
rate and platform). A run is a runaway by G3's definition (a body rate above 1e6 rad/s, a non-finite value, or an
exception).

**"No worse than the floor" at a step rate: on each platform, the configuration's number of runaway runs is at most
the floor's number plus 15** (5% of the 315 runs, rounded down).

Why an allowance: single chaotic cases scatter by a few runs between configurations that are equally good. One
impact that the floor always survives and a candidate never does adds 21 runaway runs, more than the allowance,
so a systematic new failure is still caught. Cases that differ from the floor by more than 5 runs are listed.

As with G3, this is not pass/fail on its own: crash handling belongs to the game's wrapper. The floor is the
reference.

### Not added

- A ground energy-balance gate (the review's "Tests to add") was optional and is not written. It stays open.
- No new G1, G4 or G6: they are read per step rate with their frozen limits.

## How to run

```sh
tests/gates/run.sh <config>          # G1-G6 as before -> results/04-gates-<config>.txt
tests/gates/run-later.sh <config>    # G5b, G2b, G3b and the verdict per step rate -> results/04-later-<config>.txt
.venv/bin/python tests/gates/summary_04.py floor c1-ab3 ...   # one table
```

The floor must be measured first (G3 and G3b compare with it).
