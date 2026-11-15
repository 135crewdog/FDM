# Acceptance gates for the body-rate integrator

Written in session 03, **before** any candidate was run. The numbers are in `tests/gates/gates.json`; this file
explains them. The code that measures and judges is in `tests/gates/`.

## The rule

- The gate files are frozen once committed: `tests/gates/gates.json`, `run_native.py`, `run_wasm.ts`,
  `evaluate.py`, `fixtures/brick_poi.xml`, `tests/parity/compare.py` and this file.
- `tests/gates/run.sh` refuses to run a candidate (the floor included) unless those files are committed and
  unchanged. Every result file names the commit.
- **Changing a gate:** never edit a number after seeing a result. If a gate turns out to be wrong, say so in the
  report, keep the original result, and add a new gate with a new name (G1b, G7, ...) and the date.
- New candidates are added to `tests/gates/configs.json`. That file is not frozen.

## What a candidate is

A candidate is a set of JSBSim properties (which integrators, and any switch a patch adds) plus the source it runs
on: JSBSim v1.3.3 as released ("unpatched"), or with the patches in `wasm/patches/` ("patched").

Every gate is measured twice: in **native JSBSim built from that source** (the answer key) and in **our WebAssembly
build of the same source** (`jsbsim-weh`, the one that ships). A gate passes only if it passes on both.

Set-up used by every ground test (G1 to G3), the same on both platforms:

1. Set dt (before loading anything).
2. Load the aircraft, then its initial-conditions file: `reset_at_rest` for c172x, `reset00` for f16, c310, ah1s
   and 737.
3. Set the scenario's initial conditions, then the candidate's properties, then run the initial conditions.
4. Step, and after every step read 31 quantities (rates, velocities, attitude, position, accelerations, total
   forces and moments) and every contact point.

Engines are not started. Contact means any contact point touching, wheels (BOGEY) or airframe (STRUCTURE), read
from each point's own flag. `gear/wow` is not used, because it ignores the airframe points.

## The gates

### G1 Rest

c172x, f16, c310, ah1s and 737 standing on their gear for 60 s, at 120, 240, 480 and 1000 Hz (20 runs per
platform). Pass, for every run:

- every quantity finite at every step;
- in the last 10 s, every body-rate component below **1e-6 rad/s** in magnitude;
- in the last 10 s, the aircraft never moves more than **0.01 ft** horizontally from where it was at 50 s (the
  largest distance at any step, not just the end);
- in the last 10 s, some contact point touches the ground at every step (it really is standing on the ground).

### G2 Hard landing

The review's "hard" scenario: 40 ft above the ground, level, 100 ft/s forward, 30 ft/s down. Same five aircraft
and four rates, 15 s. Pass, for every run:

- every quantity finite at every step;
- no body rate above 1e6 rad/s (a "runaway": such a run is lost even while the numbers are still finite);
- the aircraft touched the ground (otherwise the run is invalid and counts as a failure).

The second and third conditions are additions to "every state finite". They can only make the gate stricter.

### G3 Extreme impacts (compared with the floor, not pass/fail on its own)

The review's inverted, banked and nose-first impacts, same five aircraft and four rates, 15 s (60 runs per
platform). A run is a **runaway** if any body rate exceeds 1e6 rad/s, any quantity is NaN or infinite, or JSBSim
throws.

A candidate is "no worse than the floor" if its **number** of runaways is no higher than the floor's, on each
platform. Runaways that the floor does not have are listed. Crash handling belongs to the phase 2 wrapper, so
this gate only guards against a candidate making things worse.

### G4 NASA check case 02 (tumbling brick)

JSBSim's own check-case files, unchanged, at 480 and 1000 Hz, 30 s, sampled every 0.1 s. Compared with NASA sims
01 and 04. Pass:

- all 301 samples present, finite, and matched in the NASA file;
- largest body-rate error below **2e-6 deg/s**;
- largest attitude error (roll, pitch, yaw; angles wrapped) below **1e-3 deg**.

Position differences are reported with their cause, not gated. The known one: `brick.xml` sets the planet's
radius so that the run starts 0.67 ft further from the Earth's centre than NASA's sims.

### G5 Torque-free rigid body

A body with no forces but gravity and no moments at all, tumbling for 60 s (dropped from 100,000 ft so it does
not reach the ground). Two bodies: NASA's brick, and `brick_poi`, the same brick with its inertia tensor rotated so
that it has products of inertia. Eight starting spins, in deg/s about the body axes:

| name | spin | size | gated |
|---|---|---|---|
| A | 10, 20, 30 (NASA's) | 37 | yes |
| B, C, D | 60 about x, y, z alone | 60 | yes |
| E | 2, 120, 2 (close to the unstable middle axis) | 120 | yes |
| F | 200, 100, -50 | 229 | yes |
| G | 300, -150, 120 | 356 | yes |
| H | 600, -300, 240 | 712 | no, reported only |

Pass, at **480 and 1000 Hz**, for both bodies and spins A to G:

- rotational kinetic energy changes by less than **1e-6** of its starting value at every step;
- the magnitude of the angular momentum changes by less than **1e-6** of its starting value at every step.

120 and 240 Hz and spin H are run and reported, not gated.

Choices made here, stated so that a reviewer can disagree:

- "Angular momentum drift" is gated on its **magnitude**. Energy and that magnitude are the two quantities the
  body-rate integrator alone should conserve. The **direction** of the angular momentum in space also depends on
  the attitude integrator; it is measured (native only) and reported, and the attitude integrator is gated by G4.
- The gate applies at 480 and 1000 Hz, like G4. The lower rates are reported.
- The inertia matrix is read back from JSBSim, and the native runner checks it against JSBSim's own matrix.

### G6 Parity: WebAssembly against native of the same source

The review's four controlled flights, with the candidate's properties: c172x and f16, 480 Hz, 10 s, open-loop
control inputs, 30 quantities logged at every step (4801 rows). Both WebAssembly variants (`jsbsim-weh` and
`jsbsim`) are compared with native by `tests/parity/compare.py --gate`, which refuses logs with NaN, missing rows
or shifted times. Tolerances (the review's):

| quantity | tolerance |
|---|---|
| positions | 1e-4 ft |
| velocities | 1e-5 ft/s |
| forces, moments, thrust | 1e-5 + 1e-7 x the largest native value |
| rates, attitudes, control surfaces | 1e-7 |

This gate covers flight only. On the ground the two platforms are tied together by G1 and G2 being judged on both.

### Cost (no gate)

Microseconds per step in Node for each candidate: c172x and f16 in flight and standing on the ground, at 120 and
1000 Hz, median of 7 identical repetitions. The iPhone runs the same WebAssembly, so the ratio between candidates
carries over; the absolute numbers do not.

## What is known about the gates before any candidate ran

The measuring code was checked on two **reference** configurations whose answers were already known from the
independent review (`REVIEW-codex-02.md`), not on any candidate: JSBSim's defaults (`ref-default`) and unpatched
AB4 body rates (`ref-ab4`). Results: `results/03-gates-ref-default.txt`, `results/03-gates-ref-ab4.txt`.

- The harness reproduces the review's numbers. Examples, AB4 at rest, largest body rate in the last 10 s at 480
  and 1000 Hz: c172x 0.0170 and 0.0080 rad/s (review: 0.01697, 0.008005); 737 hard landing NaN at 7.192 s and
  5.416 s (review: 7.194, 5.417); NASA rate error 1.39e-6 and 3.21e-7 deg/s (review: 1.393e-6, 3.207e-7).
- **G2 is partly a matter of luck at low rates.** With JSBSim's defaults, the 737 hard landing at 120 Hz stays
  finite in native JSBSim and goes to NaN in WebAssembly. The two runs agree to 7 digits for 3.4 s, then split
  apart within 0.15 s: the bouncing itself is numerically unstable there, so a rounding-level difference decides
  the outcome. The gate is kept as written (both platforms must pass); read a single G2 failure at 120 or 240 Hz
  with this in mind.
- JSBSim's defaults already fail G2 at 120 and 240 Hz (ah1s on both platforms). The review only ran 480 and
  1000 Hz.
- The spin list of G5 was written before anything was run. During the harness check, the reference results for
  G5 were seen (for example: unpatched AB4 passes spins A to E and fails F and G). The list was not changed
  afterwards.

## How to run

```sh
scripts/build-native.sh                       # native answer keys: build/native/unpatched and build/native/patched
scripts/build-wasm.sh                         # WebAssembly with the patches -> wasm/bin/
PATCHSET=unpatched scripts/build-wasm.sh      # WebAssembly without patches -> build/wasm-bin-unpatched/
tests/gates/run.sh floor                      # about 2 minutes; report in results/03-gates-floor.txt
tests/gates/run.sh <candidate>                # needs the floor's measurements for G3
```
