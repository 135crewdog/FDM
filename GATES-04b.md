# Correction to the later gates: G2c, the forward hard landing

Written on 2026-11-15, in session 04, after `GATES-04.md` was committed (`e5bcd1d`) and **before candidate 2 or 3 was
written or run**. The numbers are in `tests/gates/gates-04b.json`. Nothing in `GATES.md`, `GATES-04.md` or their
files is changed; G2 and G2b are still measured and reported as defined.

## What is wrong with G2 and G2b

G2 (and so G2b) is described as "40 ft above the ground, level, **100 ft/s forward**, 30 ft/s down". The scenario
sets the velocity as "100 ft/s **north**". Each aircraft's own start file decides which way it faces:

| aircraft | heading in its start file | how it actually touches down in G2 and G2b (body axes, ft/s) |
|---|---|---|
| c172x | 0 deg (north) | 100 forward |
| f16 | 180 deg | 100 **backward** |
| ah1s | 180 deg | 100 **backward** |
| c310 | 200 deg | 94 **backward**, 34 sideways |
| 737 | 225 deg | 71 **backward**, 71 sideways |

So G2 and G2b are a forward hard landing for the c172x only. For the other four they are a touchdown at 60 knots
moving backward or sideways, which is a crash, not a landing. The scenario came from the independent review's
`tests/review/ground_matrix.py`; session 03 copied it into the gates without checking the headings, and I repeated
the wrong description in `GATES-04.md`. This is an error in the gate, found by tracing a failing 737 run.

What the trace showed (JSBSim's defaults, 737, 480 Hz, run 1 of G2b): the aircraft touches down sliding backward
and sideways, tips over within 4 s, and its fuselage sinks through the ground (the 737 model has three wheels and
**no airframe contact points**). At 6.0 s it is 54 ft below the surface; then a wheel comes back into contact, tens
of feet "deep", and the spring throws the aircraft to 880 ft. Whether such a run ends finite or not is not a
statement about landings.

## How this was found, and what had been seen

- Seen before this correction was written: the reference-configuration checks listed in `GATES-04.md`, and the
  trace above. All of them are JSBSim's defaults or unpatched AB4; none is the floor or a candidate.
- **Not looked at:** any result of the floor or of candidate 1 on G2b, G3b or G5b. Those runs were in progress
  while this was written; their reports had not been opened. No forward hard landing had been run with anything,
  except the c172x check below.
- Check of the new runner (reference configuration `ref-default`, c172x only): for the c172x G2c is the same
  scenario as G2b, and all 84 records agree on both platforms (same peak rate, contact steps and first contact).
  The start velocity is (100, 0, 30) ft/s in body axes for all five aircraft.

## G2c Hard landing, forward, repeated

Exactly G2b, with one addition: **the heading is set to north (`ic/psi-true-deg` = 0) before the velocity**, so
"100 ft/s north" is forward for every aircraft. Same height (40 ft), level attitude, 30 ft/s down, same five
aircraft, four step rates, 15 s, the same 21 runs with the same perturbations.

The runners check the start: the body-axis velocity must be (100, 0, 30) ft/s within 1e-3, or every run of that
case is recorded as an error and fails.

**Pass at a step rate: every run of every aircraft is good, on both platforms** (G2b's own rule: finite, no
runaway, touched the ground; pass fraction 1.0).

## What happens to G2b

G2b's results stand and are printed. Because its scenario is a crash for four aircraft, it is also **read as a
crash case, like G3b**: at a step rate, on each platform, a configuration's number of bad runs may be at most the
floor's number plus 5 (5% of the 105 runs, rounded down).

## The decision, both ways

Every report prints two verdicts per judged step rate:

- **as first committed** (`GATES-04.md`): G1, **G2b with every run good**, G3b, G4, G5b, G6;
- **corrected**: G1, **G2c with every run good**, **G2b as a crash case**, G3b, G4, G5b, G6.

I recommend reading the corrected one, because G2b does not test what it says. This changes a yardstick after
`GATES-04.md` was committed, so both are shown and the reader can disagree. It was changed for a reason that
anyone can check in the aircraft's start files, before any result of the floor or of a candidate on it was seen.

G3 and G3b have the same heading effect (their "100 ft/s" is north as well). They are deliberately extreme
impacts that are only compared with the floor, so they are left as they are.

## How to run

```sh
tests/gates/run-forward.sh <config>     # after run.sh and run-later.sh -> results/04-forward-<config>.txt
```
