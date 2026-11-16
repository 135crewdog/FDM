# Session 04: later gates, candidates 2 and 3, integrator decision

Date: 2026-11-15. Raw outputs: `results/04-*.txt`. How to rebuild and rerun: `CLAUDE.md`, `GATES-04.md`,
`GATES-04b.md`.

**Read "Review outcome" first.** The independent review (`REVIEW-codex-04.md`, 2026-11-16) says "not yet", and I
agree. The recommendation of 480 Hz is withdrawn, and three of this report's conclusions are narrowed. The rest
of the report is kept as written, with the changes marked.

## Review outcome (2026-11-16): not yet

The review's verdict: `c3-ab4` is a reasonable candidate, but 480 Hz is not qualified, and the shipped default
should stay as it is. I agree with its findings. I re-ran three of its tests here (the build failure, the forced
damping and the repeated switching); all three reproduce. The others I read but did not re-run.

What is withdrawn or narrowed:

| What this report said | What the review showed | Where it stands now |
|---|---|---|
| **Recommend `c3-ab4` at 480 Hz** | AB4 at 480 Hz blows up under a plain, stable damping moment with a 5 ms time constant: body rates pass 1e6 rad/s in 0.17 s, where Euler and midpoint simply decay. At 960 and 1000 Hz AB4 survives that case, and fails a 2.5 ms one. NASA's free-tumbling case cannot show this, because nothing pushes on the brick. | **480 Hz is withdrawn.** `c3-ab4` stays a candidate. Its step rate has to be chosen against the fastest moments the game will apply (aerodynamics, wing-strip forces), and those are not known yet. |
| **The switch adds no kick, so it is harmless** (finding 18) | True for a single step. But switching back and forth accumulates error. With 100 switches in 10 s under a smooth periodic moment, the rate error is 0.087 rad/s, against 1.7e-5 for AB4 alone and 0.021 for Euler alone. In that test switching is worse than either scheme by itself. Also, my switch diagnostic ran the variants with patch 0001 on, not `c3-ab4` itself; the review added those. | Finding 18 holds for what it measured. Whether repeated contact (touch-and-go, a wheel skipping) hurts in practice needs its own gate. |
| **The crash blow-ups have one cause** (summary, finding 8, "mistake 5") | Too broad. The review built two scratch versions. Capping wheel compression at 2 ft alone makes it worse (172 failures of 550, against 60), because the force is still divided by the same projection. Adding "no wheel contact when the leg is nearly parallel to the ground" removes all 60, but forces still reach 5,700 times the weight. And the f16 crash with AB4 throughout still runs away with compression bounded; removing friction on airframe contacts prevents it. | There are **at least two** mechanisms: wheel geometry (behind the floor's failures here) and friction on airframe contacts with AB4. My "60 of 60" is an association, not proof of what starts a failure: 176 runs that stayed finite had the same impossible compression. Finding 9 as I wrote it (limit the compression) is refuted in that simple form. |
| **The 737 and ah1s cannot test a landing** (summary, findings 6 and 7) | A 737 flown like a 737 (140 kt, full flaps, gear down, engines at idle, a pitch controller) lands in 24 of 24 trials, upright and above the ground, with the floor, `c3-ab4` and midpoint. My G2c fixed the direction but still flew every aircraft at 59 kt with engines off. | **The fixture was unsuitable, not the aircraft.** The 737 stays in scope. The ah1s is open: nobody has flown it with the rotor turning. Judging on three aircraft remains a selection made after the results, not a qualification. |
| **Candidate 2 needs the NASA limit relaxed** ("What would change it") | Midpoint at 1200 Hz is inside the frozen limit (1.6e-6 deg/s; 1.1e-6 at 1440 Hz). Both rates are whole multiples of 60 and 120 frames per second. | **The question I put to you (relax G4?) is withdrawn.** Midpoint at 1200 Hz is a candidate with no yardstick changed. On the iPhone that is about 11 ms of computing per second of flight. |
| **The build scripts record what was compiled** | A failed compile was hidden: both scripts ended with "ok", copied the old binary and recorded the new patches as built. | **Fixed with this commit** (below). |
| **G3b's 5% allowance catches a new systematic failure** | It passes a configuration that loses one case 21 of 21 if it wins another one back. | Agreed. Session 05 should judge crash cases one by one. |

What the review confirmed: patch 0003 reads the contact flag for the right instant; candidate 3 equals the floor at
rest and AB4 in free flight (in single-phase runs); patch 0002 is the pull request's solver plus counters; the
gate files were committed before the candidates' patches and are unchanged; patch 0001's algebra is consistent
(for frozen geometry); the c310 damper explanation; the G2 heading error.

Labels changed by the review (the rule is never to upgrade without evidence; these are downgrades):

- Findings 1 and 16: **Verified → Supported.** Agreeing with my own earlier results is not an outside answer key.
- Finding 9: Reasoned, and now **contradicted** in the form "limit the compression".
- Finding 11: Supported for the sweep; only **Reasoned** for "dampers play no part in landing failures".
- Finding 15: the wording "failure paths were never taken" was wrong. No Newton exception occurred, but the
  Euler fallback, which is one of those paths, was used 71 times.
- Findings 5 and 6: Supported only for what was measured ("finite and touched" on all 13 configurations; "upright
  and above ground" for three configurations, native only), and for that fixture.
- Finding 19: a hypothesis. A case that newly fails stays relevant until crashes are contained.

Fixed now, because it protects every later result:

- `scripts/build-native.sh` and `scripts/build-wasm.sh` now stop when the compiler fails. Two new checks in
  `tests/build/selftest_patches.sh` fail on the old scripts and pass on the new ones
  (`results/04-build-selftest-before-review-fix.txt`, `-after-`), and the review's own fault injection now ends
  with an error.
- Were session 04's builds stale? I see no sign of it (Supported): the session's build logs contain no compiler
  error; the candidates' properties exist in both patched builds (the gates refuse to run otherwise); candidate
  2's energy result can only come from the midpoint code; and the reviewer's fresh builds reproduce the numbers.
  A native rebuild with the fixed script gives the same module, byte for byte.

Not fixed here, left for session 05: the binding gaps the review found (a script's own negative time step is
accepted; the "read-only" switch and counter properties can be written, and one of them is read by the switch;
`setIntegrators` can be half-applied by an object whose values change while it is read).

**Where the decision stands.** The default is unchanged. There are two candidates: `c3-ab4` with its rate open,
and midpoint at 1200 Hz. My own reading, not tested (Reasoned): the review strengthens midpoint. It tolerates
stiff moments as Euler does, conserves energy exactly, has no switch and so no switching error, and meets the NASA
limit at 1200 Hz. What it still lacks is a policy for the step where Newton's method fails, and the same landing
and forced-flight tests as candidate 3. `prompts/05-ground-model-and-default.md` has been rewritten to follow
the review.

## Summary (as written before the review)

- **By the rule we set, nothing passes, so the shipped default is unchanged.** Every configuration fails the
  hard-landing gate.
- **But the hard-landing gate does not measure what we thought.** Three of the five test aircraft (c172x, f16,
  c310) land and stay upright in every run, with every configuration. The other two (737, ah1s) never land in
  any configuration: they tip over or tumble and pass through the ground. Every failure of that gate is one of
  those two.
- **The crash blow-ups have one cause, and it is not the integrator.** JSBSim's wheel code has no limit on strut
  compression. When an aircraft is tipped over or under the surface, a wheel reports a "compression" of tens to
  millions of feet and pushes with millions of pounds for one step. All 60 failed runs that I checked start
  that way.
- **Recommendation to carry forward: candidate 3 at 480 Hz.** AB4 body rates in the air, Euler while any contact
  point touches the ground, Buss 2 attitude, friction as in JSBSim (`c3-ab4`). It passes rest, NASA accuracy,
  energy conservation and parity at 480 and at 1000 Hz, and at 480 Hz it is the only candidate that does so
  without being worse than the floor in the crash cases.
- **What is missing before it can become the default:** a landing gate that tests landings, a limit on wheel
  compression (or crash detection in the game), and an independent review.

Two mistakes of earlier sessions were found and are corrected below: the "hard landing" was flown backward by four
of the five aircraft, and one test file of session 03 was never committed.

## Later gates: commits (recorded before candidate 2 or 3 was written or run)

| what | commit | when |
|---|---|---|
| Later gates G5b, G2b, G3b and the judged step rates (`GATES-04.md`, `tests/gates/gates-04.json`, runners, evaluator) | **`e5bcd1d24838f9474533219e1cd8384fdf9d9c5a`** | before either candidate's patch existed |
| Correction G2c, the forward hard landing (`GATES-04b.md`, `tests/gates/gates-04b.json`) | **`9fb7f637509bb4943dfdcb243da582917736d779`** | before either patch existed, and before any gate result of the floor or candidate 1 on the later gates was looked at (one traced floor run had been seen; see below) |
| Patches 0002 and 0003, binding, binaries | `18016cb` | after both |
| Results of all 13 configurations | `45a0c73` | |

These gates were written after the floor's and candidate 1's results on G1 to G6 had been seen. `GATES-04.md` and
`GATES-04b.md` list what was known at each commit, with one error that I correct here: `GATES-04b.md` says the
737 trace that exposed the problem used JSBSim's defaults. It used the floor's settings (Euler rates with Buss 2
attitude). So one floor run of G2b (737, 480 Hz, run 1) had been seen, as a trace, when G2c was written. The
file is frozen, so it is corrected here. The frozen files of session 03 are unchanged
(`git diff 164c1d0 HEAD` over them is empty).

## Evidence ledger

**Verified** = checked against an answer we did not produce. **Supported** = our own test shows it, no outside
answer key. **Reasoned** = explanation, not tested.

| # | Finding | Label | Evidence |
|---|---|---|---|
| 1 | Session 03 reproduces in a fresh container | Supported (lowered from Verified by the review: it reproduces our own results) | Everything rebuilt. Tests 0 to 5: every line equals session 03's except timings and build hashes. The G1 to G6 reports of the floor and of candidate 1 (AB4, AB3, AB2, and the floor with the patch) equal session 03's line for line, including every hard-landing and crash cell. No cell differed by luck. `results/04-test*.txt`, `results/04-gates-*.txt`. |
| 2 | With patches 0001, 0002 and 0003 switched off, the patched builds equal unpatched JSBSim | Verified (against the unpatched builds) | Bit-identical: 11 native logs, 18 WebAssembly logs. The source build also still equals pip's `jsbsim==1.3.3` (11 logs). `results/04-native-key-*.txt`, `results/04-wasm-patched-off-vs-unpatched.txt`. |
| 3 | `tests/build/selftest_patches.sh` (session 03) was never committed | Verified (git history) | `.gitignore`'s `build/` also matched `tests/build/`. Test 0 failed on a fresh clone. Rewritten from the nine checks recorded in `results/03-build-selftest.txt`; all nine pass. |
| 4 | G2 and G2b are a forward landing for the c172x only | Verified (the aircraft's own start files, and the body velocity read from JSBSim) | The scenario sets 100 ft/s **north**. Headings in the start files: c172x 0, f16 180, ah1s 180, c310 200, 737 225 deg. Body velocity at the start: f16 and ah1s 100 ft/s backward, c310 94 backward and 34 sideways, 737 71 backward and 71 sideways. `GATES-04b.md`. |
| 5 | In the hard-landing runs, the c172x, f16 and c310 always land and stay upright | Supported | G2c and G2b at 480 and 1000 Hz, all 13 configurations, both platforms: 21 of 21 good in every cell (6,552 runs), and the same at 120 and 240 Hz (another 6,552). For the floor, `c1-ab4` and `c3-ab4` every one of those runs stays above the ground and within 60 deg of level. `results/04-gates-summary.txt`, `results/04-diag-landing-anatomy-*.txt`. |
| 6 | The 737 and the ah1s never land in these runs, in any configuration checked | Supported | Floor, `c1-ab4`, `c3-ab4`, forward and backward, 480 and 1000 Hz: 0 of 504 runs stay above the ground and upright. Every failed run but one (222 of 223) went below the ground first. Many "finite" runs are thrown more than 100 ft into the air afterwards (20 of the floor's 21 forward 737 runs at 1000 Hz). Same files. |
| 7 | Why those two: the 737 model has no airframe contact points; the ah1s with its rotor stopped tumbles before it touches | Verified for the 737's contact list (its file: three wheels, nothing else). Supported for the rest | Trace of the 737, forward, floor, 480 Hz: the touchdown pitches it up, it rotates onto its tail over 9 s, nothing stops it, the body sinks to 157 ft below the surface, then a wheel throws it to 1,300 ft. The ah1s has body rates above 0.5 rad/s before the first touch in 21 of 21 runs. |
| 8 | Every blow-up starts with an impossible wheel compression | Formula: Verified (JSBSim source, `FGLGear.cpp`: `compressLength = height * normalZ / LGearProj`, and the force is divided by the same projection again; nothing limits either). That it precedes every failure: Supported | Floor, hard landings and impacts, 480 and 1000 Hz: **60 of 60** failed runs had a wheel "compression" above 10 ft first. Largest seen: 630 million ft; largest ground force: 5 million times the aircraft's weight. In the real landings the largest compression is 1.2 to 1.9 ft. `results/04-diag-blowup-cause-floor.txt`. |
| 9 | Limiting the wheel compression would remove these blow-ups | Reasoned; **contradicted by the review** in this simple form (see "Review outcome") | Follows from 8. Not tested: it needs a patch, and that patch must go through gates written first. Test: patch `FGLGear`, rerun G2c, G2b, G3b. |
| 10 | Session 03's explanation (ledger 15 there) is right for the c310 at rest | Supported (a damping sweep, and a linear model that shares no code with JSBSim) | The c310's gear damping was scaled until it stops settling. Largest damping tolerated at 120 Hz, as a multiple of the aircraft's own: AB4 0.71, AB3 1.20, AB2 1.81, Euler 2.58. The c310's own damping (1.0) lies between AB4's and AB3's limit, which is exactly session 03's result. Doubling the step rate doubles the limit (AB4: 0.71, 1.44, 2.64 at 120, 240, 480 Hz). The model predicts all seven numbers 6 to 26% low. `results/04-diag-gear-damper.txt`. |
| 11 | The same explanation is **wrong** for the hard-landing failures | Supported | If stiff dampers caused them, softer dampers would cure them. The opposite happens: 737 with dampers at one eighth, 0 of 11 survive at every rate; at double or four times, 11 of 11 at every rate. The c310 survives at every damping and rate. Same file. The real cause is finding 8. |
| 12 | The floor fails accuracy and energy conservation | Verified for G4 (NASA data). Supported for G5b | G4: body rates 0.092 deg/s (480 Hz) and 0.044 deg/s (1000 Hz) from NASA; gate 2e-6. G5b: energy drifts by a factor 5.4 (480 Hz) and 0.78 (1000 Hz) in 60 s of fast tumbling; gate 1e-6. |
| 13 | Candidate 1 with AB4 passes rest, NASA, energy and parity at 480 and 1000 Hz, and is worse than the floor in the crash cases | Verified for G4. Supported for the rest | G4 1.4e-6 and 3.2e-7 deg/s. G5b 2.4e-8 and 9.4e-10 (its G5 failures were start-up only, as session 03 said). Crash cases: G2b good runs 69 of 105 against the floor's 77 (480 Hz), 73 against 103 (1000 Hz); G3b runaway runs 84 against 42, 63 against 21. AB3 fails G5b (5.3e-5, 5.8e-6: a real drift). AB2 fails G4 and G5b. |
| 14 | Candidate 2 (implicit midpoint) conserves energy to rounding and settles at rest, but misses the NASA gate | Verified for G4. Supported for the rest | G5b 2.9e-14 (480 Hz) and 5.1e-14 (1000 Hz), and below 6e-14 at 120 and 240 Hz too. G1 pass. G4 body rates 1.0e-5 deg/s at 480 Hz (5 times the gate) and 2.3e-6 at 1000 Hz (15% over the gate). That is 9,000 times closer to NASA than the floor. Patch 0001 makes no difference to it. |
| 15 | Candidate 2 never threw (no Newton failure). Its Euler fallback was used 71 times. (Reworded after the review: "failure paths were never taken" was wrong.) | Supported | 3.7 million midpoint steps over the gates' workloads: 0 exceptions (Newton not converged or singular Jacobian), 0 rounding exits. Newton needs 2.0 to 3.7 iterations per step, at most 5. The Euler fallback was used in 71 steps, all in the landing and impact workloads where runs went non-finite. `results/04-diag-midpoint-counters.txt`. |
| 16 | Candidate 3 does exactly what it says, in runs that are all contact or all flight | Supported (lowered from Verified by the review: identity with our own configurations; it says nothing about a mixed flight) | In the air it is AB4: its 64 torque-free runs, 4 NASA logs and both flight logs are bit-identical to `c1-ab4`'s. On the ground it is the floor: the 12 rest runs that start in contact equal the floor's, on both platforms. (The other 8 start with a short drop.) |
| 17 | Candidate 3 with AB4 passes rest, NASA, energy and parity at 480 and 1000 Hz; in the crash cases it is no worse than the floor at 480 Hz and worse by the rule at 1000 Hz | Verified for G4. Supported for the rest | Same G4 and G5b numbers as finding 13. G2b good runs 96 / 94 against the floor's 77 / 76 (480 Hz), 94 / 96 against 103 / 105 (1000 Hz). G3b runaway runs 43 / 42 against 42 / 42 (480 Hz), 52 / 49 against 21 / 21 (1000 Hz). With AB3 in the air it fails G5b like AB3 does. |
| 18 | The switch adds no kick and does not flap in real landings | Supported | Touch-down steps and first steps back in the air differ from an Euler step by 1e-17 rad/s (rounding). A bouncing c172x changes scheme 3 times, never closer than 33 steps apart. Only the 737, while passing through the ground, switches every step; a 0.1 s hold stops that. `results/04-diag-contact-switch.txt`. |
| 19 | "Worse than the floor" in the crash cases does not rank integrators | Reasoned, from 8 and one traced case | At 1000 Hz every configuration except the floor loses the same case, the inverted ah1s (21 of 21), which the floor itself loses at 120, 240 and 480 Hz (21 of 21 each). Trace: at first contact a wheel reports 31,000 ft of compression and the ground pushes with 50 to 300 million pounds; a difference in the third digit of the state decides whether that step is survived. Test: finding 9's patch. |
| 20 | No configuration costs measurably more | Supported | c172x at 1000 Hz in Node, flight / on the ground: floor 19.2 / 25.0, `c1-ab4` 19.4 / 24.5, `c2-mid` 20.1 / 26.4, `c3-ab4` 19.3 / 23.8 microseconds per step. The scatter between repetitions is about 2. |
| 21 | Candidate 3 also holds at 960 Hz | Supported (native only; a confirmation run, not a gate) | Rest 1.7e-8 rad/s, NASA 3.5e-7 deg/s, energy 1.1e-9; c172x, f16, c310: 21 of 21 in every landing and impact. `results/04-diag-confirm-960-c3-ab4.txt`. |
| 22 | The new build (all three patches inside, switched off) runs on the iPhone at the same speed as session 02's build | Verified (the user's iPhone, Safari 27.2) | 59 of 61 aircraft load; errors arrive as `JSBSimError`. c172x 13.0, 8.7, 8.3 and f16 10.0, 10.0, 10.3 microseconds per step at 120, 480, 1000 Hz (session 02: 8 to 13 and about 10.5). 20 forces by handle or bulk cost 2 to 4 more. The end states (height, speed) equal the Chromium run's. This times JSBSim's defaults, not `c3-ab4`. `results/04-page-iphone-fwasm-exceptions.txt`. |

Yardsticks changed after seeing results, and how to read around them:

- **G2c replaced G2b as the hard-landing gate** after `GATES-04.md` was committed. Reason: finding 4. It was done
  before any candidate result existed, and every report prints the verdict both ways.
- **Reading the landing gate on the three aircraft that land** (finding 5) was decided after seeing the results.
  It is not a gate and decides nothing formally. It is the reason for my recommendation, and it is the first
  thing a reviewer should attack.
- No number in any gate file was edited.

## Every candidate against every gate

Judged at 480 and 1000 Hz. Cells with two numbers are native / WebAssembly. Full table with all 13 configurations:
`results/04-gates-summary.txt`. Per configuration: `results/04-gates-<name>.txt` (G1 to G6 as in session 03),
`04-later-<name>.txt` (G5b, G2b, G3b), `04-forward-<name>.txt` (G2c).

| Configuration | Rate | G1 Rest | G2c Forward hard landing: c172x, f16, c310 (of 63) | G2c: 737 and ah1s (of 42) | G2b Backward touchdown, good runs of 105 | G3b Impacts, runaway runs of 315 | G4 NASA rate error, deg/s | G5b Energy drift | G6 Parity |
|---|---|---|---|---|---|---|---|---|---|
| **Floor** | 480 | pass | 63 / 63 | 20 / 21 | 77 / 76 (reference) | 42 / 42 (reference) | **fail** 9.2e-2 | **fail** 5.4 | pass |
| | 1000 | pass | 63 / 63 | 38 / 40 | 103 / 105 | 21 / 21 | **fail** 4.4e-2 | **fail** 0.78 | pass |
| **Candidate 1**, AB4 (`c1-ab4`) | 480 | pass | 63 / 63 | 9 / 7 | 69 / 69 **worse** | 84 / 84 **worse** | pass 1.4e-6 | pass 2.4e-8 | pass |
| | 1000 | pass | 63 / 63 | 16 / 16 | 73 / 75 **worse** | 63 / 63 **worse** | pass 3.2e-7 | pass 9.4e-10 | pass |
| Candidate 1, AB3 (`c1-ab3`) | 480 | pass | 63 / 63 | 8 / 9 | 80 / 79 | 47 / 47 | pass 1.4e-6 | **fail** 5.3e-5 | pass |
| | 1000 | pass | 63 / 63 | 42 / 41 | 105 / 105 | 44 / 44 **worse** | pass 3.2e-7 | **fail** 5.8e-6 | pass |
| **Candidate 2**, midpoint (`c2-mid`) | 480 | pass | 63 / 63 | 28 / 32 | 102 / 100 | 42 / 43 | **fail** 1.0e-5 | pass 2.9e-14 | pass |
| | 1000 | pass | 63 / 63 | 37 / 39 | 105 / 105 | 42 / 42 **worse** | **fail** 2.3e-6 | pass 5.1e-14 | pass |
| Candidate 2 with patch 0001 (`c2-mid-fa`) | 480 | pass | 63 / 63 | 34 / 39 | 102 / 102 | 42 / 42 | **fail** 1.0e-5 | pass 2.9e-14 | pass |
| | 1000 | pass | 63 / 63 | 37 / 41 | 105 / 104 | 42 / 42 **worse** | **fail** 2.3e-6 | pass 5.1e-14 | pass |
| **Candidate 3**, AB4 in the air (`c3-ab4`) | **480** | pass | 63 / 63 | 23 / 25 | 96 / 94 | 43 / 42 | pass 1.4e-6 | pass 2.4e-8 | pass |
| | 1000 | pass | 63 / 63 | 41 / 41 | 94 / 96 **worse** | 52 / 49 **worse** | pass 3.2e-7 | pass 9.4e-10 | pass |
| Candidate 3 with patch 0001 (`c3-ab4-fa`) | 480 | pass | 63 / 63 | 22 / 24 | 76 / 74 | 63 / 63 **worse** | pass 1.4e-6 | pass 2.4e-8 | pass |
| | 1000 | pass | 63 / 63 | 41 / 41 | 104 / 104 | 42 / 42 **worse** | pass 3.2e-7 | pass 9.4e-10 | pass |
| Candidate 3, AB3 in the air (`c3-ab3`) | 480 | pass | 63 / 63 | 21 / 24 | 92 / 97 | 43 / 42 | pass 1.4e-6 | **fail** 5.3e-5 | pass |
| | 1000 | pass | 63 / 63 | 42 / 40 | 98 / 91 **worse** | 49 / 45 **worse** | pass 3.2e-7 | **fail** 5.8e-6 | pass |

Limits: G1 body rates below 1e-6 rad/s (all configurations are near 1e-8). G2c every run good, all five aircraft.
G2b bad runs at most the floor's plus 5. G3b runaway runs at most the floor's plus 15. G4 below 2e-6 deg/s (and
attitude below 1e-3 deg, which every row that passes the rate also passes). G5b below 1e-6.

**Verdict by the rule, every row: FAIL**, both as first committed (G2b must be 21 of 21) and corrected (G2c must be
21 of 21 for all five aircraft). The only gate every row fails is the hard landing, and only through the 737 and
the ah1s.

The original G1 to G6 verdicts (all four rates, single runs) are unchanged from session 03 for the floor and
candidate 1. For the new ones: `c2-mid` G1 pass, G2 fail, G3 worse, G4 fail, G5 pass, G6 pass; `c3-ab4` G1 pass,
G2 fail, G3 worse, G4 pass, G5 fail (AB4's start-up, as before), G6 pass.

At 120 and 240 Hz (reported only): G4 is not measured there. At 240 Hz AB4 (candidates 1 and 3) still passes
G1 and G5b. At 120 Hz AB4 fails G5b, and `c1-ab4` does not settle with the c310. Candidate 2 passes G1 and G5b at
all four rates. The c172x, f16 and c310 land in every run at these rates too. I see no reason to revisit the
judged rates.

## Recommendation (as written before the review; the 480 Hz recommendation is withdrawn, see "Review outcome")

**By the rule: no change.** Nothing passes every gate at the judged rates, so the shipped default stays JSBSim's
(Euler body rates). The binaries contain all three patches, switched off.

**What I recommend carrying forward: `c3-ab4` at 480 Hz.**

- In plain words: AB4 body rates while flying, Euler body rates while any contact point touches the ground, Buss 2
  attitude, friction as JSBSim has it. It needs patch 0003 only.
- Settings: `simulation/integrator/rate/rotational` = 5, `simulation/integrator/position/rotational` = 7,
  `simulation/integrator/rate/rotational-on-contact` = 1. In the wrapper:
  `sim.setIntegrators({ rateRotational: 5, positionRotational: 7, rateRotationalOnContact: 1 })`.

Why this one:

- It is the only candidate that passes rest, NASA accuracy, energy conservation and parity **and** is no worse
  than the floor in both crash gates, at a judged rate (480 Hz). (Two comparison variants of candidate 3 itself,
  with a hold time and with the history kept, do so as well.)
- On the ground it is JSBSim's default, bit for bit (finding 16). That is the most used configuration of JSBSim,
  and it tolerates 3.7 times stiffer gear dampers than AB4 does (finding 10).
- In the air it is AB4, bit for bit: 66,000 times closer to NASA than the floor at 480 Hz.
- It does not need patch 0001. That patch's mathematics is still unreviewed, and with Euler on the ground it has
  nothing left to fix in rotation.
- Why not candidate 1 (AB4 everywhere with patch 0001): it passes the same four gates, but it is worse than the
  floor in every crash gate, has about a quarter of the damper margin, and needs the unreviewed patch.
- Why not candidate 2 (midpoint): it fails the NASA gate as frozen. See "What would change it".
- Why 480 Hz and not 1000 Hz: at 480 Hz it passes everything it passes at 1000 Hz, it costs half, and it is a
  whole number of steps per frame at 60 and 120 frames per second. Its margin on the NASA gate is thin at 480 Hz
  (1.4e-6 against 2e-6). If more margin is wanted, 960 Hz holds too (finding 21).

What is missing before it can become the default:

1. **A landing gate that tests landings.** Aircraft that can land, flown forward, at descent rates from firm to
   hard, judged on more than "finite": the aircraft stays above the ground and upright, and does not gain energy.
   Written and committed before anything is run through it.
2. **A limit on wheel compression** (finding 8), as a patch with its own switch, or crash detection in the game's
   wrapper (stop the simulation when the aircraft is tipped over on the ground or below the surface). Until then
   every configuration, JSBSim's defaults included, can be thrown into the air by a tipped-over wheel.
3. **An independent review** of patch 0003 and of how I read the landing gate (`prompts/codex-review-04.md`).

What would change the recommendation:

- If the review finds an error in patch 0003, or disagrees that the 737 and ah1s runs say nothing about landings.
- If the new landing gate shows a difference between Euler on contact and the alternatives.
- **If you decide the NASA gate is tighter than a game needs.** G4's limit (2e-6 deg/s after 30 s of tumbling)
  was set at AB4's own level. Candidate 2 misses it by 15% at 1000 Hz and by 5 times at 480 Hz, and is still
  9,000 times better than the floor. It needs no switching between schemes and it conserves energy exactly. That
  is a decision about the yardstick, and it is yours to make, not mine after seeing the result.
- If the game has to run below 480 Hz. Nothing here supports that.

## What was done

**Step 1.** Everything rebuilt from scratch; tests and gates reproduce session 03 exactly (findings 1 to 3).

**Step 2.** Later gates written and committed (`GATES-04.md`): G5b (energy drift measured from 1 s), G2b and G3b
(each case run 21 times with starts moved by up to 1e-6 ft, ft/s and deg), judged at 480 and 1000 Hz. While
tracing a failing 737 run I found that the scenario is not a forward landing (finding 4) and added G2c before any
result was looked at (`GATES-04b.md`). Then the floor and candidate 1 were run. The test of session 03's damper
explanation is findings 10 and 11.

**Step 3, candidate 2.** `wasm/patches/0002-implicit-midpoint-body-rates.patch`: the source change of
PteroLabsAI/jsbsim pull request 13 (commit `33384d9`, fetched with git), unchanged, plus counters. Switched by
`simulation/integrator/rate/rotational` = 10. The pull request's second commit, which makes it JSBSim's default,
was not taken. Results: findings 14, 15, 20.

**Step 4, candidate 3.** `wasm/patches/0003-body-rate-scheme-on-contact.patch` (about 60 added lines): a second
body-rate scheme that takes over in every step whose forces include ground contact. Contact means any contact
point, wheels and airframe, each by its own flag. When the aircraft leaves the ground, the multistep history is
restarted, as JSBSim does at start-up. Patch 0001's friction is told which scheme is active on the ground. Native
JSBSim and WebAssembly run the same code. Variants tested: AB4 and AB3 in the air, with and without patch 0001,
with a 0.1 s hold, and with the history kept. Results: findings 16 to 18.

**Step 5.** The table and recommendation above.

## Earlier explanations that turned out wrong

1. **"100 ft/s forward" (the review's scenario, `GATES.md`, REPORT-03, and my own `GATES-04.md`).** Forward for
   one aircraft of five (finding 4).
2. **"The floor fails hard landings at low step rates" and "candidate 1 does not fix hard landings" (REPORT-03).**
   The numbers stand, but they were never about landings. The three aircraft that land always pass. The failures
   are the 737 and ah1s crashing (findings 5 to 8).
3. **"Hard landings are numerically chaotic" (REPORT-03 ledger 14).** True as an observation, and now explained:
   the chaos is an aircraft passing through the ground and being thrown by a wheel with millions of pounds.
4. **"The gear damper is too stiff for the integrator" as the cause of the hard-landing failures (REPORT-03 ledger
   15).** Right for the c310 at rest, wrong for the landings (findings 10 and 11). Also, "AB4 tolerates about 7
   times less damping than Euler" should read 3.7 times (measured: 2.58 against 0.71).
5. **"The first invalid operation in the crash is unknown" (sessions 02 and 03).** Now known for the cases
   traced: the unlimited wheel compression (finding 8).
6. **Patch 0003's own header** says that keeping the multistep history on release "adds an impulse of about half a
   step of the last ground moment". Measured in real landings: at most 3% of that (1.2e-5 rad/s), because the gear
   force fades to zero before the wheel leaves the ground. It was large only for the 737 passing through the
   ground (0.45 rad/s). The patch restarts the history anyway; the header overstates why. The text is left as it
   is, because the patch's hash is in every result file.
7. **Session 03's build self-test was not in the repository** (finding 3).
8. **`GATES-04b.md` misnames the configuration of its trace** (the floor's settings, not JSBSim's defaults; see
   "Later gates: commits"). The description of what the trace showed stands.

## What an independent reviewer should check first

1. **My reading of the landing gate** (findings 5 to 7, 19): is it fair to say the 737 and ah1s runs are not
   landings, and to recommend on the other three aircraft? This was decided after seeing results.
2. **Finding 8**: is the unlimited wheel compression really what starts every blow-up? `FGLGear.cpp`, and
   `tests/gates/diag/blowup_cause.py`.
3. **Patch 0003**: is the contact flag the right instant (it must belong to the derivative being integrated)? Is
   restarting the history on release sound? Is the change to patch 0001's accessor right?
4. **Whether the gates were fixed first**: `git log` around `e5bcd1d`, `9fb7f63`, `18016cb`; `GATES-04.md` and
   `GATES-04b.md` on what had been seen.
5. **G2c and the two-way verdict**: was replacing G2b legitimate?
6. **Patch 0002**: is it the pull request's code unchanged apart from the counters? Is G4's limit the right
   yardstick for a game (the "what would change it" question)?
7. **The damper model** (`tests/gates/diag/gear_damper.py`): it predicts the c310 well and the other aircraft
   badly (it is too cautious for them).
8. Still open from session 03: **patch 0001's mathematics** (not needed by the recommendation, but still in the
   build).

## Things a reader should know

- **Where I chose, not you:**
  - G2b's and G2c's pass mark is every run (1.0); G3b's allowance is 5% of the runs.
  - The perturbations are 1e-6 ft, ft/s and deg, and there are 21 runs per case.
  - G5b measures from 1.0 s.
  - Candidate 3 restarts the multistep history on release and has no hold time by default.
  - The binding now accepts integrator 10 for the body rates and validates the on-contact setting (80 regression
    checks, both variants).
- **Candidate 2's failure path throws.** If Newton's method ever failed, the pull request's code throws and the
  simulation step fails. It never happened in 3.7 million steps, but a shipped version should fall back instead.
- **The G3b rule did what it was built to do, and that turned out not to be useful.** It flags a case the floor
  always survives and a candidate never does. The one such case at 1000 Hz is decided by a 100-million-pound
  kick (finding 19).
- **The patch headers are frozen with the results** (their hashes are in every result file), so mistake 6 above
  is corrected here and not in the patch.
- **All three patches are in the shipped binary, switched off.** Finding 2 shows that "off" is unpatched JSBSim.
- **"Needs patch 0003 only" means switches, not files.** The recommended configuration leaves patches 0001 and
  0002 switched off. As a file, patch 0003 is written on top of 0002 and does not apply without it.
- **Pushed to `main`** at each checkpoint, as the prompt asked.
- **The test page runs the new build** in headless Chromium and on the iPhone (finding 22; added after the
  session's last push, when the user pasted the iPhone results). The page uses JSBSim's default integrators. At
  480 Hz a step costs about 9 microseconds on the iPhone, so one second of flight costs about 4 ms.
- **Not done:** the optional ground energy-balance gate; an iPhone timing of `c3-ab4` itself (in Node it costs
  the same as the defaults, finding 20); a memory-leak audit; a test of finding 9.

## What remains for session 05

(Superseded by the review: the current plan is `prompts/05-ground-model-and-default.md`. The list below is the plan
as written before the review.)

1. Read the independent review of sessions 03 and 04 first, and answer it.
2. Before running anything: a landing gate that tests landings (aircraft that can land, forward, several descent
   rates, judged on staying above the ground, upright and without gaining energy), and a gate for the crash
   cases that a limit on wheel compression should fix. Commit them.
3. Patch 0004: limit the wheel (BOGEY) compression, switched off by default, bit-identical when off.
4. Run the floor, `c3-ab4` and `c2-mid` through the new gates, with and without patch 0004.
5. If `c3-ab4` passes: make it the wrapper's default, and re-run the iPhone timing.
6. Crash detection in the wrapper (tipped over on the ground, or below the surface).

## How to reproduce

```sh
npm ci
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
source <emsdk>/emsdk_env.sh                       # Emscripten 6.0.13
scripts/build-native.sh                           # build/native/unpatched and build/native/patched
scripts/build-wasm.sh                             # wasm/bin (patches 0001-0003, all switched off by default)
PATCHSET=unpatched scripts/build-wasm.sh          # build/wasm-bin-unpatched
SESSION=04 NATIVE=patched scripts/run-tests.sh    # tests 0-5 -> results/04-test*.txt
tests/native/verify_key.sh unpatched pip          # the source build is a valid answer key
tests/native/verify_key.sh patched unpatched      # the patches change nothing while off (native)
tests/native/verify_wasm_patch_off.sh             # the same for WebAssembly
for c in floor c1-ab4 c1-ab3 c1-ab2 c1-euler c2-mid c2-mid-fa c3-ab4 c3-ab4-fa c3-ab3 c3-ab3-fa c3x-ab4-fa-hold c3x-ab4-fa-keep; do
  tests/gates/run.sh $c && tests/gates/run-later.sh $c && tests/gates/run-forward.sh $c   # about 5 minutes each; the floor first
done
.venv/bin/python tests/gates/summary_04.py floor c1-ab4 c3-ab4 ...                        # one table
# diagnostics (native; PYTHONPATH=build/native/patched, or unpatched for the floor):
.venv/bin/python tests/gates/diag/gear_damper.py modes|sweep|landing
.venv/bin/python tests/gates/diag/landing_anatomy.py <config>
.venv/bin/python tests/gates/diag/blowup_cause.py <config>
.venv/bin/python tests/gates/diag/midpoint_counters.py
.venv/bin/python tests/gates/diag/contact_switch.py
.venv/bin/python tests/gates/diag/confirm_rate.py c3-ab4 960
```
