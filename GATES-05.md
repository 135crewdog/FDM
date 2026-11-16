# Gates of session 05: landing, repeated contact, crash containment, forced flight

Written on 2026-11-16, in session 05, **before the floor or any candidate was run through them**. The numbers are
in `tests/gates/gates-05.json`; this file explains them. Every earlier gate file is unchanged and is still
measured and reported as before.

## The rule

- Frozen once committed: `tests/gates/gates-05.json`, `sim05.py`, `sim05.ts`, `run_native_05.py`, `run_wasm_05.ts`,
  `evaluate_05.py` and this file. `tests/gates/run-05.sh` refuses to run anything but a reference configuration
  unless these, and every earlier frozen file, are committed and unchanged.
- Never edit a number after seeing a result. A wrong gate is kept, said to be wrong, and replaced by a new gate
  with a new name.
- Every gate is measured in native JSBSim and in our WebAssembly build of the same source, and must hold on both.
- One judge for both platforms: the runners only write one row of numbers per physics step; `evaluate_05.py`
  reads the rows of both and applies the limits.

## What had been seen when these gates were written

These gates are not blind. When the numbers were chosen I had read or seen:

- Everything in `REPORT-04.md`, `REVIEW-codex-04.md` and `results/review-codex-04/`. In particular:
  - the floor, `c3-ab4` and `c2-mid` on every existing gate (G1 to G6, G5b, G2b, G3b, G2c);
  - the review's 737 landings: all 24 land with the floor, `c3-ab4` and midpoint;
  - the review's forced damping: AB4 blows up at 480 Hz with a damping rate of 200 per second, and at 960 and
    1000 Hz with 400 per second; Euler and midpoint decay;
  - the review's repeated-contact case: `c3-ab4` ends 0.087 rad/s off at 480 Hz (0.039 at 960 Hz), worse than
    Euler alone;
  - the review's scratch builds: a compression cap alone makes the crash cases worse; with a projection guard
    the floor's failures go, and forces still reach 5,700 times the weight.
- AB4's stability limit under damping (about `rate x step < 0.3`; Euler's is 2). This is textbook knowledge and it
  cannot be un-known: with G7's damping rate of 180 per second it says beforehand that AB4 at 480 Hz will fail
  the in-core damping case. The rate was not chosen for that; it is twice the fastest moment measured (see G7).
- **Fixture trials, all with JSBSim's default integrators** (no property under `simulation/integrator/` set),
  native only unless said otherwise. Every trial is logged: `results/05-fixture-trials.jsonl` (my trials, about 230) and
  `results/05-fixture-trials-ah1s.jsonl` (82 trials of a helper agent that built the ah1s landing, re-run by me
  through the gate runner). By kind:
  - trims: JSBSim's own trim (9; it fails for the c310), my Newton solver on fresh and on settled states (58);
  - control signs of the four fixed-wing aircraft (4);
  - landings of the draft fixtures, at 480 to 9600 Hz (65 fixed-wing, 6 ah1s through the gate runner);
  - touch-and-go and skipping against the same run at 9600 Hz (48);
  - the forced-flight probes at 480 and 960 Hz (16) and the fast-flight fixture against its reference (20);
  - rest on the gear (4), for the standing height of each aircraft.
- What those trials showed, and so what I knew when choosing limits (all JSBSim defaults):
  - landings: every fixed-wing case lands, upright, with no airframe contact, at every rate tried; peak ground
    force and compression at 480 Hz are within 1.5% of the 9600 Hz run; ground force up to 6.7 times the weight
    (f16 at its limit sink; its dampers are stiff); largest compression 0.69 ft; energy closure at most 0.07 ft
    at 480 Hz and falling in proportion to the step; the ground never gave net energy (0.0000 ft);
  - the ah1s lands upright at 2 to 15 ft/s; its hover attitude and peak force depend on the step rate itself
    (2.0 times the weight at 480 Hz, 2.7 at 9600 Hz for the same 6 ft/s touchdown), whatever the integrator;
  - touch-and-go and skipping: attitude within 0.09 deg and end rates within 0.002 rad/s of the 9600 Hz run;
  - probes: Euler's error is 3.8% (in-core) and 17% (external, one step late) for the 90 per second damper at
    480 Hz, 8% and 31% for the 180 per second one; springs 1.4% to 5.5%;
  - fast flight: JSBSim's defaults are within 0.24 deg and 0.015 rad/s of the reference.
- **A harness check of the complete pipeline** (both platforms) on JSBSim's defaults at 1000 Hz
  (`ref-default-05`), with its reference runs at 9600 Hz, run twice. Report: `results/05-new-ref-default-05.txt`.
  - The first run exposed a fixture bug: the crosswind of `hard_drift` was written to a read-only property.
    Native JSBSim ignored the write silently, the WebAssembly wrapper refused it. Fixed (the wind is now set
    through the two writable properties, and the native runner refuses a write that does not take), and the
    case re-flown: it now touches down drifting sideways at 8.5 to 9.5 ft/s.
  - The second run: G2d 23 of 23 good, G8 8 of 8, G7 12 of 12, on both platforms, with numbers that agree
    between the platforms to the digits printed. G3d: 14 (native) and 15 (WebAssembly) of 20 cases contained;
    the others are the ah1s and 737 blow-ups known from session 04. The largest ground force among the
    contained cases is 269 times the weight (c172x, nose first). G3d's limits (500 weights, 10 ft) were written
    before this run and were not changed after it.
  - The reference for ground cases uses the floor's integrators (Euler rates, Buss 2) at 9600 Hz. I looked at
    it only as a reference.

Not seen: any run of the floor, `c3-ab4` or `c2-mid` through any fixture or gate of this file. Patch 0004 did not
exist.

Limits chosen after seeing the default-integrator trials (said here, as the rule asks): the energy limits
(0.25 ft and 0.05 ft), the convergence limit (10%), the ground-force limit for landings (10 weights), G8's limits
and G7's flight limits. Each is a round number at least 1.4 times, and mostly 3 or more times, what JSBSim's
defaults showed, and far below what a real failure looks like. They are not blind and a reviewer should weigh
them.

## Fixtures: an approach that suits each aircraft

**Fixed-wing (c172x, c310, 737, f16).** A steady descent at the case's sink rate, at the aircraft's approach
speed, in landing configuration, engines running, flown by three simple proportional controllers (pitch, roll,
yaw), the same for every configuration and platform.

| | c172x | c310 | 737 | f16 |
|---|---|---|---|---|
| Approach speed | 55 kt | 75 kt | 130 kt | 150 kt |
| Configuration | flaps 30 | flaps 25, gear down | flaps full, gear down | gear down |
| Angle of attack (trimmed) | 4.3 to 4.6 deg | 5.1 to 5.7 deg | 4.7 to 5.4 deg | 10.9 to 11.9 deg |
| Limit sink rate (ft/s) | 8.5 | 9.8 | 10 | 10 |

- **The limit sink rate comes from the aircraft's own weight and wing area**: the certification rule for light
  aircraft, 4.4 x (wing loading)^0.25 ft/s, capped at 10 ft/s, which is also the transport and fighter value.
- **Trim**: angle of attack, elevator and throttle for each sink rate are in `gates-05.json`. They were found
  natively by `tests/gates/make_fixtures05.py` (Newton's method on the forces left over, at the height of the
  release so that the model's own ground effect is included). JSBSim's trim routine is not used.
- **Settling**: after the engines are set running they need up to 4 s to reach the state of the flight
  condition, and control actuators start at zero. So the fixture flies 4 s with fixed controls, putting the
  aircraft back on its initial conditions every 0.25 s (a second `run_ic`: JSBSim resets position, velocity,
  attitude and rates and keeps engine and control-system states). Flaps and gear are preset through the output
  property of their actuators, or they would start retracted and travel.
- **Release**: the start height puts the lowest wheel on the ground 1 s after the release. Rows are recorded from
  the release.
- **After the first wheel contact**: idle, the nose lowered at 1.5 deg/s, wings level, brakes 0.2 after 3 s. The
  run ends 15 s after the touchdown.
- **What really happens is read back, not assumed**: every report prints the actual sink rate, pitch, bank and
  speed at the last step in the air, and a run whose sink is outside 50% to 130% of the nominal value, or that
  moves backward, fails as "not the landing described". On JSBSim's defaults the touchdowns were at 1.5 to 1.9
  (nominal 2), 4.7 to 5.9 (nominal 6) and 8.2 to 9.3 ft/s (limit), main wheels first except the c172x at its
  limit sink (nose wheel first: an unflared arrival at 55 kt is nose-low).

Cases: `firm` (2 ft/s), `hard` (6 ft/s), `limit` (the aircraft's limit sink), `hard_bank3` (6 ft/s with 3 deg of
bank, one wheel first), `hard_drift` (6 ft/s in a 5 kt crosswind without de-crabbing, so the aircraft touches
down drifting sideways).

**Helicopter (ah1s).** A rotor-running vertical landing. The rotor is spooled up on the skids by the model's own
governor; a second `run_ic` puts the helicopter into a hover (rotor and control states are kept); the model's
own attitude-hold channels, a vertical-speed loop on the collective and a slow position hold fly the hover and
then a descent at the case's sink rate; after the first contact the collective is lowered. Cases: `firm` (2),
`hard` (6), `limit` (8 ft/s: the usual military limit for helicopter gear; my choice, the model gives none). No
banked, drifting, touch-and-go or skipping case was built for it.

**Not built:** a run-on landing of the ah1s, an autorotation, any landing with a failed engine, cross-wind
landings with de-crab, wet or sloped runways. They are "not tested", not "passed".

## Step rates

Said before anything was run:

| configuration | judged step rates |
|---|---|
| floor (reference for the candidates) | 480, 960, 1000, 1200 Hz |
| `c3-ab4` | 480, 960, 1000 Hz |
| `c2-mid` | 960, 1200 Hz |

Each also runs with the ground-safety patch (0004) switched on, as a separate configuration with its own
reference runs. References run at 9600 Hz. I see no reason to judge other rates; 120 and 240 Hz stay out, as
decided in `GATES-04.md`.

## G2d Landing

Every aircraft, every case (23 landings), at each judged rate. A landing is **good** if all of these hold:

| condition | limit | why this number |
|---|---|---|
| completes | no exception, every value finite, wheels touch within 10 s of the release | |
| is the landing described | touchdown sink within 50% to 130% of nominal, moving forward | a fixture that does something else must not pass or fail on its name |
| stays above the ground | the centre of gravity never below 75% of the height at which the aircraft stands | lower means the airframe is in the ground |
| stays upright | bank at most 10 deg; pitch between -5 deg and the approach pitch + 5 deg; heading within 15 deg | wing-tip strike and tail strike territory starts about there |
| no airframe contact | no STRUCTURE point touches, ever | a landing within limits does not scrape |
| no wheel beyond its strut travel | compression at most `2 x weight / spring rate` of that wheel | JSBSim's files give no travel. This is where the wheel's spring alone pushes with twice the aircraft's weight, more than any gear is built for. 0.9 ft (c172x mains) to 1.8 ft (737 mains) |
| ground force | at most 10 times the weight | the models' own dampers ask for up to 7 (f16, c310) at their limit sink; real gear is built for 2 to 6 |
| energy accounted for | closure at most 0.25 ft | see below |
| the ground gives no energy | ground work never above +0.05 ft | see below |
| converged (fixed-wing only) | peak ground force and largest compression within 10% of the reference run at 9600 Hz | a spike that is not in the converged answer is numerical |
| settled | all wheels on the ground at the end, and not airborne in the last 5 s | |

**G2d passes at a step rate if every landing is good on both platforms.**

**The energy budget.** In the Earth-fixed frame, for every step: kinetic energy of the aircraft (translation and
rotation), and the power of every force and moment JSBSim reports: ground contact, aerodynamics, propulsion,
external, weight, plus the centrifugal term of the rotating Earth. Two conditions:

- **Closure**: kinetic energy now, minus kinetic energy at the release, minus the summed work of all forces,
  must stay near zero. If the state gains energy that no force supplied, the integration invented it.
- **The ground gives nothing**: the ground's summed work on the aircraft may go as negative as it likes
  (springs store, dampers and friction dissipate) and may come back up as springs return what they stored, but
  never above zero. This is the test that catches an aircraft being thrown.

Energies are divided by the weight, so they read in feet: 0.25 ft is "enough to lift the aircraft 3 inches". The
vertical energy of a 10 ft/s touchdown is 1.55 ft; the 737 thrown to 1,300 ft in session 04 would read 1,300.

Not applied to the ah1s: the convergence condition. Its rotor and control model depend on the step rate
themselves (seen on JSBSim's defaults: 35% between 480 and 9600 Hz), which says nothing about a body-rate
integrator.

## G8 Repeated contact

The four fixed-wing aircraft, two cases, at each judged rate:

- `touch_and_go`: the `hard` approach; at the touchdown full power, the approach attitude plus 2 deg; 6 s more.
- `skip`: a 2 ft/s approach onto an **undulating runway** (0.2 ft high, 25 ft long waves; the runner sets the
  terrain height from the distance run, before every step, as a game's terrain would), approach power and
  attitude held for 8 s. On JSBSim's defaults the wheels leave and meet the ground 29 (c172x) to 82 (f16)
  times.

Judged against the **reference**: the same run at 9600 Hz with JSBSim's Euler body rates and Buss 2 attitude, on
the same source and with the same ground-safety setting, compared 40 times a second from the release.

| condition | limit |
|---|---|
| attitude at the end | within 0.2 deg |
| body rates at the end | within 0.005 rad/s |
| attitude at any time | within 0.5 deg |
| is the case described | at least 1 contact episode (touch-and-go), at least 10 (skip), in the run and in the reference |

**G8 passes at a step rate if all eight runs are good on both platforms.**

- The largest body-rate difference at any time is reported, not judged: during an impact the rates change by
  0.1 rad/s in a few milliseconds, so a touchdown one step earlier or later shows as a large difference that is
  not an accumulated error.
- **The review's synthetic case is run and reported, not judged** (`tests/review/review04_release.py`: unit
  inertia, a roll moment of 10 rad/s^2 at 5 Hz, a force-free wheel made to touch for 1/60 s every 0.2 s, so the
  contact pattern is locked to the moment). I know from the review that `c3-ab4` does badly on it. I do not judge
  it because its moment is not derived from any aircraft and its contact pattern is the worst case by
  construction; the judged cases are real aircraft with up to 82 contact episodes. This is a choice a reviewer
  may reject: the number is in every report so that it can be judged later without re-running anything.

## G3d Crash containment, case by case

Twenty cases: the five aircraft of the earlier gates (c172x, f16, c310, ah1s, 737), each in four scenarios, with
the set-up of the frozen ground tests (start file, engines and rotor stopped): `drop` (G2c's: 59 kt forward,
30 ft/s down, from 40 ft), `inverted`, `banked`, `nose` (G3's, headings as they are). Each case is run 5 times
(the unperturbed start and the first four perturbations of `gates-04.json`). A run is **contained** if:

| condition | limit | why |
|---|---|---|
| completes | no exception, every value finite | |
| no runaway | no body rate above 1e6 rad/s | the earlier gates' definition |
| ground force | at most 500 times the weight | the models' own airframe points ask for up to about 100 to 200 at these impact speeds (c172x wing tip: 2,000 lb per ft/s of damping x 100 ft/s = 81 weights per point). Blow-ups are thousands to millions |
| the ground gives no energy | ground work never above +10 ft | a crash may bounce; it must not be thrown |

**A case is contained if all 5 runs are. G3d passes at a step rate if every one of the 20 cases is contained on
both platforms.** Nothing is pooled and nothing is compared with the floor: a case that fails counts, whatever
else improves. The height range of every case is reported (an aircraft that ends below the ground is a matter
for the wrapper's crash check, step 5, not for this gate).

G3b stays as it is and is still reported.

## G7 Forced flight

**How fast is the fastest moment?** `tests/gates/envelope05.py` computes, for the four fixed-wing aircraft from
their approach speed to their fastest speed at sea level, the damping (change of angular acceleration per unit
of body rate) and stiffness (per unit of angle of attack or sideslip) of the aerodynamic moments
(`results/05-envelope.txt`, JSBSim's defaults). Fastest found: **damping 89 per second** (f16 yaw at 800 kt;
c310 pitch 41 per second at 220 kt), **stiffness 9.7 rad/s** (f16 pitch at 800 kt).

**Margin wanted for the wing-strip work: a factor 2** (the usual 6 dB gain margin of control engineering). It has
to cover: aircraft other than these four, lighter loading (inertia down, so rates up), speeds beyond the
envelope, and strip forces that are stronger than a table model's. So the gate is: **damping 180 per second,
stiffness 20 rad/s**. More margin can be bought later with a higher step rate; it is not assumed here.

**(a) Probes with an exact answer.** A body of unit inertia, no contact points, and a roll moment
`-c x rate - k x angle`. Four cases: a pure damper at 90 and at 180 per second, and a spring at 10 and at 20
rad/s with a damping ratio of 0.3 (a typical short-period value). Each is run twice: with the moment computed
**inside JSBSim** (as its aerodynamics are), and with the moment **written from outside before every step**
(WebAssembly: through the bulk input, exactly as the game's wing-strip forces will arrive; native: a property
write at the same point). The outside path is one step late by construction: the moment written before step k
comes from the state after step k-1, and JSBSim's step k first integrates the derivative it stored in step k-1.

| condition | limit | applies to |
|---|---|---|
| stable | finite, and never above 1.05 times its starting size | all 8 runs |
| dies away | below 1% of its start from 10 time constants on | all 8 runs |
| accurate | within 10% of its starting size of the exact answer, at every step | the four spring runs |

Why the dampers are not judged on accuracy: a 180 per second damper is over in 30 ms, and a result that is one
step late differs from the exact curve by 31% of the start for a few milliseconds (Euler at 480 Hz). Nobody can
see that; what must not happen is growth or ringing. The damper errors are printed in every report. The springs
are the modes a pilot feels (short period, Dutch roll), so they are judged: 10% is about what handling-quality
standards treat as the same aircraft.

**(b) The real aircraft at their fastest.** c172x at 160 kt, c310 at 220 kt, 737 at 340 kt, f16 at 800 kt, at
1,000 ft: level, clean, full throttle, trimmed, held by the same three controllers, with small doublets
(0.02 of full travel) on elevator, aileron and rudder for 5 s. Compared 40 times a second with the reference
(AB4 body rates, Buss 2, 9600 Hz, same source).

| condition | limit |
|---|---|
| completes | no exception, finite |
| attitude | within 0.5 deg of the reference at every sample |
| body rates | within 0.02 rad/s of the reference at every sample |

**G7 passes at a step rate if all 8 probe runs and all 4 aircraft are good on both platforms.**

## G1, G4, G5b and G6 at the new step rates

The frozen files list 480 and 1000 Hz (G4, G5b) and four rates (G1); G6 is measured at 480 Hz. For 960 and
1200 Hz, `tests/gates/run-rates-05.sh <config> <hz>` copies the frozen measuring and judging code into a shadow
tree, replaces **only the lists of step rates** in a copy of `gates.json` and `gates-04.json` by that one rate,
checks that every other frozen file is byte-identical, and runs the frozen code there. Every limit is the frozen
one. The reports are named `results/05-rates-<hz>-*.txt` and say at the top what differs. G6 at a new rate
means: the same flights, flown and compared at that rate.

## The decision rule (from the session's prompt)

A configuration **passes at a step rate R** if, on both platforms: G2d, G8, G3d and G7 pass at R, and G1, G4, G5b
and G6 pass at R (read from the frozen reports for 480 and 1000 Hz, from the new readings for 960 and 1200 Hz).
The wrapper's default changes only if one candidate passes at one rate.

## Where I argued with the starting positions

- **"No wheel beyond its strut travel"**: JSBSim's aircraft files have no strut travel. I use the compression at
  which the spring alone pushes with twice the aircraft's weight. A reviewer who has real gear data should
  replace it.
- **G7's margin is 2, not more**, and the dampers are judged on stability, not accuracy (above).
- **G8's synthetic case is reported, not judged** (above).
- **G3d has an energy condition** in addition to "finite, no runaway, bounded force", because "finite" passed
  aircraft that were thrown 1,000 ft in session 04.
- **G3d keeps the old crash set-ups**, engines and rotor stopped. They are crashes on purpose.
- **Perturbed repeats**: G2d and G8 have none. The landings proved deterministic on JSBSim's defaults (1.5%
  between 480 and 9600 Hz), and variety comes from five different cases per aircraft, not from 21 copies of
  one. G3d keeps 5 repeats because crashes are chaotic.

## How to run

```sh
PYTHONPATH=build/native/patched .venv/bin/python tests/gates/envelope05.py      # the fastest moments (G7)
PYTHONPATH=build/native/patched .venv/bin/python tests/gates/make_fixtures05.py  # the trims in gates-05.json
tests/gates/run-05.sh <config>              # G2d, G8, G3d, G7 at the configuration's rates -> results/05-new-<config>.txt
tests/gates/run-rates-05.sh <config> <hz>   # G1 to G6 and G5b read at 960 or 1200 Hz -> results/05-rates-<hz>-*.txt
```
