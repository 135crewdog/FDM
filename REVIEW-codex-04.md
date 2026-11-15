**Verdict: not yet.** `c3-ab4` is a reasonable candidate to investigate, but the evidence does not establish **480 Hz as the choice for the game**. The contact flag is timed correctly and the switch does select Euler for the contact derivative. However, the landing comparison uses unsuitable approaches, repeated switching can lose substantial accuracy, and NASA's free-body case says little about stability under aerodynamic or JavaScript-supplied moments. The claim that every crash blow-up has one cause is too broad. Keep the shipped default unchanged, fix the native build failure check, and compare properly configured landings and forced flight before choosing between contact switching and midpoint. Midpoint at **1200 Hz** is an additional option that meets the existing NASA limits without relaxing them.

Independent review of sessions 03–04, 15 November 2026. Reviewed `main` at `2d1a767`. No existing gates, patches, aircraft or shipped binaries were changed. Diagnostic source changes were built separately under ignored `build/` directories.

Labels: **Verified** = checked against independent source/history, native release or an independent answer; **Supported** = my own experiment establishes the stated observation; **Reasoned** = inference or recommendation, not a completed validation.

## Findings

| What I checked | How | What I found | How sure / evidence |
|---|---|---|---|
| **High: “limiting wheel compression removes the blow-ups”** | Rebuilt the native library with a 2 ft BOGEY compression cap, then repeated the exact 550-trial floor diagnostic | A cap alone is insufficient: **172 failures**, versus the original **60**. Compression stays ≤2 ft, but the force still divides by the gear-leg projection and reaches **83 million times weight**. This is not a production fix. | **Supported.** [Scratch builder](tests/review/review04_build_scratch.py), [cap results](results/review-codex-04/compression-cap.txt). |
| **High: the wheel geometry is the only crash mechanism** | Added a second scratch variant: the same cap plus no wheel contact when the leg's ground-normal projection is ≤0.1. Also repeated the F-16 STRUCTURE-friction ablation | The guard removes the floor diagnostic's **60/550** failures, but the low-rate, always-AB4 F-16 still runs away at the **same times**, with compression bounded at 2 ft. Removing STRUCTURE friction still prevents it. There are separate mechanisms. | **Supported.** [Baseline](results/review-codex-04/compression-baseline.txt), [guard](results/review-codex-04/compression-guard.txt). Details below; this F-16 test is not a test of `c3-ab4`. |
| **High: native build results reliably identify the compiled patches** | Injected a compiler failure into a temporary incremental build containing an old, valid unpatched library | `scripts/build-native.sh` exits **0**, copies the stale library and records all three patches as present. The resulting module has no midpoint property. `cmake --build ... \| grep ... \|\| true` masks the failed build. Fix this before testing another patch. | **Supported.** [Fault injection](tests/review/review04_build_failure.py), [result](results/review-codex-04/native-build-failure.txt). This does **not** establish that the published builds were stale; my genuine fresh builds succeeded. |
| **High: the 737 can be set aside when recommending an integrator** | Flew a new 140 kt, gear-down, fully flapped, engine-running 737 setup with the same pitch controller for the floor, `c3-ab4` and midpoint | All **24** trials touch down, finish 25 s finite, stay above **3.08 ft AGL**, and remain within **9.55° pitch / 0.05° bank**. The 737 is usable in a better landing fixture. The old fixture cannot establish a landing ranking. | **Supported.** [Test](tests/review/review04_powered_landing.py), [results](results/review-codex-04/powered-737.txt), [traces](results/review-codex-04/landing-traces). This is a diagnostic, not a newly passed acceptance gate. |
| **High: 480 Hz is supported for forced flight by passing NASA** | Tested a contact-free spherical body with a known, stable damping law, both inside JSBSim and through the bulk input hook | With in-core damping `p′ = −200p`, `c3-ab4` at 480 Hz exceeds **1e6 rad/s at 0.173 s**; Euler and midpoint decay. At 960/1000 Hz AB4 decays. A faster damping law defeats AB4 at those rates too. NASA does not establish a forced-flight stability envelope. | **Verified against the closed-form decay**, using the shipped WASM. [Test](tests/review/review04_airborne.ts), [results](results/review-codex-04/airborne-damping.jsonl). These are synthetic loads, not a finding that an existing aircraft has that damping. |
| **Medium: “no kick” establishes harmless switching/restart** | Checked the original diagnostic, reran it on the actual recommended configuration, and added an analytically solvable repeated-contact test | The first released step is indeed Euler and adds no extrapolated ground impulse. That does not preserve airborne accuracy. In a 10 s, 100-switch diagnostic, rate error reaches **0.0874 rad/s**, versus **1.67e-5** for uninterrupted AB4. Keeping history gives 0.0839: most error comes from switching schemes, with an additional restart cost. | **Verified against the analytic solution** for this synthetic test. [Release accuracy](results/review-codex-04/release-accuracy.txt), [test](tests/review/review04_release.py). Not a prediction of a particular aircraft's touch-and-go. |
| **Medium: a 5% pooled crash allowance catches systematic new failures** | Examined the counting rule | It can hide an entire new 21/21 failure case if another 21/21 case is recovered. Equal total counts pass. The per-case notes do not change the verdict. Invalid crash fixtures weaken physical ranking, but do not make newly introduced numerical failures irrelevant. | **Reasoned**, directly from `evaluate_04.py`/`evaluate_04b.py` and the declared allowance. |
| **Medium: binding validation is complete and integrator updates are atomic** | Reran both 80-check suites and added script/setting tests | Ordinary invalid-ID batches correctly leave settings unchanged. But a script with `dt="-0.01"` loads successfully; status properties advertised as read-only are writable; an accessor-based settings object can cause a later write to fail after an earlier setting changed. | **Supported.** [Extra checks](results/review-codex-04/binding-extra.txt); [WEH](results/review-codex-04/binding-regress-weh.txt), [JS exceptions](results/review-codex-04/binding-regress-js.txt). Scope below. |
| **Medium: the favourable three-aircraft reading is an acceptance result** | Compared the gate definitions, anatomy code and recommendation | It is a disclosed **post-result selection**, not a passing gate. “Finite and touched” is not “landed upright”; upright/above-ground anatomy was checked only for a subset of configurations, natively. A better fixture should retain the 737, not remove it because the bad fixture fails. | **Supported**, by the tests and [powered 737 diagnostic](results/review-codex-04/powered-737.txt). |
| **Low: patch 0003 uses the wrong instant's contact flag** | Read upstream execution order and the patched `LoadInputs`/`Run`; checked flag/derivative alignment | **No timing defect found for the tested fixed configurations.** Propagate receives the stored derivative and contact flags from the same previous force evaluation. The synthetic switch test records **zero alignment errors**, and Euler-step residuals on contact are rounding-sized. | **Verified** against JSBSim's scheduling/source and the analytic diagnostic. See the patch analysis below. |
| **Low: candidate 3 is bit-identical to the floor on the ground and AB4 in the air** | Compared every sampled state in separate, single-phase native runs | Holds in the tested domains: six 60 s rest runs starting in contact match the floor exactly; both NASA flights match AB4 exactly at every step. Runs starting with a drop already differ. It is not a statement that a mixed flight/contact trajectory equals either fixed scheme. | **Supported.** [Identity test](results/review-codex-04/single-phase-identity.txt). Original ledger 16 should not be labelled Verified solely by comparison with the author's own configurations. |
| **Low: patch 0002 is the PteroLabs midpoint solver, apart from counters** | Downloaded commit `33384d9981614509c65698f5f8be8eb8d1950228` independently and compared the solver block | The solver matches after removing instrumentation and normalizing the equivalent split convergence test. I found no additional numerical algorithm change. The upstream stress-test suite itself was not imported by this patch. | **Verified.** [Audit code](tests/review/review04_source_audit.py), [audit result](results/review-codex-04/midpoint-source-audit.txt). |
| **Low: midpoint requires relaxing G4 to remain a candidate** | Repeated native NASA comparisons at five rates, without changing G4 | At **1200 Hz**, worst rate error is **1.617e-6 deg/s**, with attitude also inside the existing limit. At 1440 Hz it is 1.123e-6. Both rates are multiples of 60/120 Hz. These are accuracy confirmations, not passes of every gate at those rates. | **Verified** against NASA sims 01/04. [Results](results/review-codex-04/nasa-rates.txt). |
| **Low: the gates were frozen before candidates 2/3 were committed** | Inspected the commit trees and diffs | Yes: 0002/0003 first appear at `18016cb`, after both gate commits. The frozen files remain unchanged. Git cannot prove when uncommitted experiments happened or which reports were opened. The disclosure already admits substantial reference results before freezing. | **Verified** for repository history only. [History record](results/review-codex-04/gate-history.txt). |
| **Low: patch 0001's mixed-scheme algebra** | Derived the discrete constraint response and checked 1000 frozen-geometry cases against direct velocity updates | The leading-weight matrix and history correction are consistent for the supported linear schemes under frozen-geometry assumptions. Maximum residual slip is **1.75e-14**; matrix finite-difference error is **4.34e-13**. This is not proof of exact nonlinear contact, midpoint or frozen-rate behaviour. | **Supported** by an independent mathematical oracle. [Code](tests/review/review04_friction_math.py), [result](results/review-codex-04/friction-math.txt). |
| **Low: the damper model explains the c310 and excludes damping from landing failures** | Reran its mode calculation and damping sweep; inspected the landing experiment | The c310 agreement reproduces and supports the rest explanation. The landing sweep refutes the simple “too much damping is the cause” story, but cannot prove damping/stiffness never contributes during nonlinear contact. “Wrong for the landings” is broader than that test establishes. | **Supported.** [Modes](results/review-codex-04/damper-modes.txt), [sweep](results/review-codex-04/damper-sweep.txt); original landing table remains in `results/04-diag-gear-damper.txt`. |

## What the direct compression test establishes

**Supported.** I built two diagnostic variants of the same patched native source, with the integrator patches left off for the floor:

1. **Cap only:** limit computed BOGEY compression to 2 ft, before calculating the displaced contact point. The projected-force divisions remain unchanged.
2. **Cap plus projection guard:** the same limit, and suppress BOGEY contact when `LGearProj <= 0.1`.

Neither variant edits `wasm/patches/`, `wasm/bin/`, the aircraft or the frozen tests. They are interventions to test the explanation, not proposed production physics. Source hashes and binary provenance are in [the cap metadata](results/review-codex-04/native-info-review04-cap.json) and [guard metadata](results/review-codex-04/native-info-review04-guard.json).

| Same 550 floor trials | Rate-runaway failures | Largest wheel compression | Largest total ground force / weight |
|---|---:|---:|---:|
| Original source | 60 | 630 million ft | 5.03 million |
| Compression cap only | 172 | 2 ft | 83.2 million |
| Cap plus projection guard | 0 | 2 ft | 5714 |

**Supported.** The original **60/60 association reproduces**. But **176 finite runs also exceed 10 ft compression**. Observing excessive compression before a rate threshold is crossed does not identify the first unstable operation. The original diagnostic monitors body rates for failure; it is not a complete physical landing or energy test. Its “before failure” means before that numerical threshold, not necessarily before the instability began.

**Verified source explanation.** `FGLGear.cpp` divides compression, compression speed and the BOGEY normal-force conversion by the leg projection. Before a cap, the spring contribution to normal force can grow roughly as the inverse square of that projection. Capping compression leaves the force-conversion division singular. The guard experiment supports a geometry-related failure in these floor trials. Zero rate-runaway counts still leave forces thousands of times weight, so it does not make the ground model trustworthy.

**Supported second mechanism.** On the separate, original `f16_test` trajectory with AB4 used **throughout**, both guarded variants still cross 1e6 rad/s at **127.983 s / 128.029 s** at 120/240 Hz. No wheel compression exceeds 2 ft. Setting only STRUCTURE static/dynamic friction to zero at 127 s prevents those runaways through 132 s, without changing springs or damping. The original source's first wheel compression above 10 ft occurs only at **127.967 / 128.000 s**, late in the growing instability. That is a causal counterexample to the broad single-cause story.

This does **not** show the recommended contact-switch configuration fails that F-16 test: that experiment deliberately leaves AB4 active on contact to isolate the separate friction interaction. The narrower conclusion is useful: session 05 needs to guard wheel geometry **and** retain tests for other contact/integration mechanisms.

## Landing fixtures and the recommendation

**Supported.** The report is right that G2/G2b did not describe forward landings for four aircraft. My session 02 northward drop was a numerical stress setup; it should not have been treated as a forward landing for every model. Correcting the heading was justified. G2c still uses about **59 kt for every aircraft**, no started engines and no landing trim/controller. A correct direction does not make that a meaningful 737 approach or a rotor-supported helicopter landing.

The new 737 diagnostic uses **140 kt northward, 3° initial pitch, full flaps, gear down, running engines commanded to idle**, a common pitch controller and braking after contact. It covers initial descent rates of 5, 10, 15 and 30 ft/s at both judged rates, for the floor, `c3-ab4` and midpoint. It logs actual body velocity, engine N2 and flap position. Actual touchdown descent rates differ from the initial settings because lift acts during the approach; do not label them “30 ft/s touchdowns” without reading that measurement. All 24 trials touch and remain upright/above the surface. The hardest starts bounce to about 23 ft; no energy or certified strut-travel conclusion is implied.

**Supported provenance note.** My first exploratory version accidentally left engine N2 at zero and let the flaps slew from zero. That output is retained as [737-first-fixture-engines-not-started.txt](results/review-codex-04/737-first-fixture-engines-not-started.txt). I corrected the setup before calling the later trials powered. The final program and trace files correspond to the corrected setup; it is not a frozen gate and was not used to declare a candidate accepted.

**Reasoned conclusion.** It is fair to reject an invalid fixture as a physical landing test and retain its results as crash stress data. It is not fair to turn “three models passed this numerical test” into a complete landing qualification, or to exclude the other models before trying suitable approaches. The post-result three-aircraft reading is disclosed honestly, but disclosure does not supply the missing evidence. I did not construct a rotor-running AH-1S approach; that remains open rather than established as an unusable aircraft.

## Patches 0003 and 0001

**Verified scheduling check.** In JSBSim, `Run()` increments time, then schedules Propagate before the new ground/acceleration calculation. The patch supplies Propagate with **both** the stored acceleration and the previous force evaluation's individual contact flags. Thus the contact flag belongs to the derivative being integrated, not the newly propagated position. It counts STRUCTURE and BOGEY points. I found no one-step mismatch here for fixed settings. The additional synthetic test confirms this alignment through 100 transitions at each tested rate.

**Reasoned accessor check.** Patch 0003 makes the accessor used by patch 0001 return the on-contact integrator whenever switching is enabled. In the intended configuration this is correct where friction is solved: if active friction multipliers exist, the derivative will be integrated by the contact scheme next step. Away from contact the friction routine returns without a solve, so returning the contact ID is harmless. This is not a general “currently active integrator” accessor; code using it for another purpose could be misled. Runtime changes to settings between derivative evaluation and integration need separate care.

**Supported identity check.** Single-phase equivalence holds in [my native tests](results/review-codex-04/single-phase-identity.txt): c172x/f16/AH-1S rest runs starting in contact equal the floor bit for bit at both judged rates; c310/737 runs starting with a short drop already differ. Both NASA trajectories equal fixed AB4 at every sampled integration step. None of that proves equivalence after a real landing/release history.

**Verified accuracy counterexample.** The release diagnostic uses spherical inertia and a smooth sinusoidal roll moment with a closed-form solution. A nearly force-free wheel supplies controlled contact intervals; its actual gear moment remains below **1e-7 lb-ft**. It is a deliberate test of integration, not terrain or aircraft realism. At 480 Hz over 10 s:

| Configuration | Maximum rate error | Final rate, whose exact value is zero |
|---|---:|---:|
| Uninterrupted AB4 | 1.67e-5 rad/s | 2.07e-7 rad/s |
| Contact switching, history kept | 0.08394 | 0.08394 |
| Contact switching, history restarted | 0.08738 | 0.08705 |
| Euler throughout | 0.02083 | 9.55e-9 |

The contact steps still match an Euler step to about **3e-17 rad/s**. Both switched versions lose accuracy: selecting Euler over particular phases of a periodic load can accumulate a bias; restarting adds another error. At 960 Hz the restarted maximum falls to 0.0393, and at 1920 Hz to 0.0185. This is convergence, but much less accurate than uninterrupted AB4. A tiny measured “kick” on one step does not bound the accumulated error. Do not interpret this synthetic result as a measured error for a particular real touch-and-go.

**Supported scope correction.** The original `contact_switch.py` tests only variants with **friction-aware enabled**, including the variant described there as “the candidate.” The recommendation leaves it off. I added [the actual `c3-ab4` cases](results/review-codex-04/contact-c3-vs-fa.txt). They support rounding-sized Euler-step residuals in the tested contacts, but a broad no-flapping/no-accuracy-loss claim still needs a repeated skip/touch-and-go gate.

**Supported algebra check for 0001.** With geometry frozen, let the contact Jacobian map translational/angular velocity to slip. A friction impulse changes those velocities through mass and inverse inertia. For leading multistep weights `bt` and `br`, the effective response is:

`A = bt * Jtranslation * (1/m) * Jtranslationᵀ + br * Jrotation * I⁻¹ * Jrotationᵀ`.

The right-hand side must cancel predicted slip including the current and historical derivatives, each with its own weights. That is what mode 1 implements. The history indices match the upstream push/pop schedule. Translation history is inertial and is rotated to the current body frame; rotational component derivatives are used in the same coordinates as the rate integrator. The 1000-case independent calculation confirms the matrix and RHS, including unequal schemes; the old divided-RHS/unweighted-matrix approach fails that mixed-weight check.

**Reasoned limits.** This is a frozen-geometry linear response, with a sufficiently converged, unsaturated constraint solve. It is not exact nonlinear contact at finite dt. The helper treating unknown schemes as Euler is not exact for frozen rates (`id 0`) or for the nonlinear midpoint response (`id 10`). Friction saturation, changing contact geometry, moving terrain, angular momentum direction and work/energy still need tests. The recommendation leaves this patch off, but it must remain tested and correctly identified in the binary.

## Rates, midpoint, gates and evidence

**Verified.** NASA errors reproduce: AB4 is **1.393e-6 deg/s at 480 Hz**, 3.480e-7 at 960 and 3.207e-7 at 1000. Midpoint is 1.011e-5, 2.527e-6 and 2.329e-6 respectively. Midpoint at **1200 Hz** gives **1.617e-6**, and at 1440 gives 1.123e-6; attitude is below 1e-3° too. These extra rates have not been put through the complete candidate gates on both platforms. They should be considered before presenting “relax G4 or reject midpoint” as the choice.

**Verified, limited to the analytic load.** The shipped WASM test of `p′ = −200p` has a 5 ms damping time and no contacts. Its exact motion decays. AB4's negative-real-axis stability condition is about `|λ|dt < 0.3`, whereas Euler's is 2. At 480 Hz the test has `|λ|dt = 0.417`: AB4 grows, Euler and the gyro-only midpoint update decay. For a 2.5 ms damping time even 960/1000 Hz does not save in-core AB4. A bulk-input damping law also demonstrates a feedback delay: inputs are computed before `run`, but Propagate first consumes the derivative already stored from the preceding force evaluation. The force-update schedule therefore belongs in the wing-strip validation, not just its write benchmark.

**Reasoned rate recommendation.** 960 Hz gives roughly four times the measured AB4 NASA accuracy and twice the step-size stability margin relative to 480, and fits 60/120 Hz rendering. It is a sensible additional qualification rate. Neither it nor 1000 is a proof of stability for unspecified wing-force gradients or feedback. Establish the intended flight envelope and force Jacobians, then test convergence and force-update timing. The synthetic loads above demonstrate the missing requirement; they do not establish that an existing aircraft reaches those damping rates.

**Verified source, Reasoned operational policy.** Patch 0002's solver is the PteroLabs implementation plus counters, as claimed. It treats the gyroscopic term implicitly and **keeps applied moments explicit**. Its free-body conservation result does not make external stiffness implicit. A failed Newton solve throws; the exceptional step has already advanced time and may have updated attitude. Catching `JSBSimError` is not a transactional rollback. A game can handle this by stopping at a last accepted finite state, or use a separately validated fallback/substep strategy. “It never happened in these workloads” is useful evidence, not a recovery policy. The report itself records **71 Euler fallbacks**; its “failure paths never taken” wording must mean Newton exceptions, not every exceptional path.

**Reasoned judgement of G4.** A 2e-6 deg/s tolerance is a very strict numerical regression target, selected with AB4's known error available. Nothing supplied connects that particular number to game handling, pixels or flight accuracy. Keeping it frozen is correct. The owner should approve a clear engineering tradeoff, not be asked to judge flight-dynamics physics from a 15% miss. If a different accuracy requirement is justified, retain G4 and add a separately justified gate; first investigate the 1200 Hz option, which needs no relaxation.

**Verified history; limits on “fixed first.”** The gate files are unchanged from their declared commits. Both new gate commits precede committed candidate 2/3 implementations. Correcting G2b's heading error by adding G2c, retaining the old data and printing both verdicts is legitimate exploratory practice. It is not a blind acceptance experiment. The lists disclose reference runs performed after choosing numbers but before committing; those are results seen before freezing. The earlier PteroLabs results were also already known from REPORT-02 and the earlier review, and friction-free AB4 reference results already describe the airborne part of candidates 1 and 3. Commit order cannot prove no uncommitted trial occurred or no report was opened; I found no evidence of an undisclosed gate-number edit.

**Reasoned judgement of the later gates.** G5b is a useful *additional* test of steady drift, but excludes a real persistent startup error. Repeated releases make that exclusion particularly important. Twenty-one tiny perturbations test local sensitivity, not the operating envelope or player failure probability; they vary neither realistic speed, loading, trim nor surfaces. Even independent Bernoulli trials with 21 successes would not establish near-zero failure probability; these clustered perturbations are not independent population samples. Requiring every physically valid landing to avoid a simulation failure is appropriate. The 5% pooled crash allowance is a heuristic, not a statistical confidence statement, and can mask exchanges of failed cases. Replace that ranking with per-case crash containment and physical/accuracy criteria, rather than simply waiving an unfavourable count.

**Supported damper conclusion.** The original mode table and critical-scale sweep reproduce, including c310's approximate 0.707/1.201/1.810/2.581 damping multiples at 120 Hz. This supports the local rest explanation. The model omits friction constraints, changing contact, leg tilt, nonlinear damping/clamping and much of the aircraft. Softer damping can make a real system bounce/tip more even while easing a numerical stiffness limit. The landing sweep therefore weakens the simple damping explanation; the new geometric intervention is stronger evidence for the tested floor failures. It does not establish that stiffness is irrelevant in all landings.

## Audit of every REPORT-04 ledger label

| Row | Assessment of the stated label and scope |
|---|---|
| 1 | **Lower to Supported.** Reproducing the author's own earlier results is reproducibility evidence, not an independent answer key under the report's definition. My review did not rerun all 13 complete suites. |
| 2 | **Verified for the tested native numerical logs.** Both fresh native checks pass: unpatched vs pip and patched-off vs unpatched, 11 logs each. Not universal equivalence of APIs, timing or every state. The 18 WASM comparisons were not independently rebuilt/rerun here. |
| 3 | **Verified.** Git history confirms the missing session-03 test file. The repaired build-mechanics self-test passes, but misses the compiler-failure defect found above. |
| 4 | **Verified for the headings/initial velocities.** This establishes the scenario error, not that correcting heading alone creates a valid landing. |
| 5 | **Supported, narrower scope required.** The gate successes are finite/contact successes. Above-ground/upright anatomy was measured natively for three configurations, not all 13 on both platforms. |
| 6 | **Supported for the tested anatomy subset.** Do not generalize it to the aircraft being unable to land or every possible configuration; the new 737 setup is a counterexample to that broader reading. |
| 7 | **Keep the split.** The 737 contact list is Verified; observed AH-1S pre-contact tumble is Supported. Attributing it solely to the stopped rotor requires a controlled running-rotor comparison. |
| 8 | **Keep source Verified / association Supported.** “First invalid operation now known” and the single-cause headline are not earned by that association. The direct interventions above delimit it. |
| 9 | **Reasoned originally; cap-only version now contradicted.** A cap plus projection guard removes these floor rate-runaways but still permits enormous forces and does not fix the separate F-16 mechanism. |
| 10 | **Supported.** The rest sweep/model comparison reproduces; no broader aircraft-ground validation follows. |
| 11 | **Supported for the damping sweep; Reasoned for its broad causal exclusion.** The opposite damping trend does not logically exclude every stiffness interaction. |
| 12 | **Keep Verified for NASA, Supported for G5b.** These are the specified tumbling cases, not every ordinary flight. |
| 13 | **Keep the split for the recorded gates.** G5b excludes startup, and crash “worse” means the declared count rule. |
| 14 | **Keep the split.** NASA mismatch reproduces; energy/rest results remain workload-specific. “Patch 0001 makes no difference” applies to those friction-free accuracy/energy metrics, not every landing result. |
| 15 | **Supported, correct the wording.** No observed Newton exception/rounding exit is different from no exceptional path: Euler fallback was used 71 times. |
| 16 | **Lower to Supported.** Bit identity with the author's own measured configurations is not an outside answer key. State the single-phase limitation; the timing subclaim has a separate source check. |
| 17 | **Keep the split for those gate results.** It is not a landing/forced-flight qualification. |
| 18 | **Supported only for the tested cases and local residual.** The original diagnostic enables friction-aware; my bare-configuration checks help, but repeated-switch accuracy still needs a gate. |
| 19 | **Reasoned, retain it as a hypothesis.** Unphysical kicks undermine physical ranking, but a newly failing case remains relevant until containment is demonstrated. |
| 20 | **Supported for the short Node timing sample.** It does not establish performance equivalence or target-phone cost of the selected candidate. |
| 21 | **Supported, correctly called native confirmation.** It is not complete two-platform qualification at 960 Hz. |
| 22 | **Verified only as the supplied user's device measurement.** It explicitly times patches-off defaults and compares limited end-state outputs. I cannot independently rerun the phone; it does not time `c3-ab4`. |

## Binding and remaining build issues

**Supported.** Both existing binding suites pass **80/80**, and the comparator regression suite rejects its broken logs. I found no repeat of the original ordinary malformed-path C++ exception escape. Handles/reset, read-only ordinary writes and normal invalid-ID batches are materially improved.

The extra checks expose narrower gaps:

- The script's **own** negative dt bypasses the argument validation; the wrapper accepts a loaded simulation with `dt = -0.01`. Validate the parsed script rate before constructing rate-dependent components, not only the optional override.
- `contact-active`, `contact-switches` and midpoint counters accept writes despite being described as read-only. `contactActive` is actually read by the switch logic, so it is not merely a harmless counter. Negative hold time and an unknown release mode also accept writes.
- `setIntegrators` validates values before applying them but reads the settings object repeatedly and has no rollback. A getter that changes value between validation and application reproduces a half-applied batch. That is an adversarial API test, not a failure of ordinary constant-object invalid-ID validation. Snapshot inputs and make the transactional promise precise.
- Allocation/leak behaviour was not audited. In particular, Node file-copy failure cleanup and partial model/step failure recovery still need tests; “caught” does not mean the state rolled back.

**Supported.** The native compiler-failure injection is separate and more serious for future result integrity. The script must propagate the compiler exit status before copying or writing new provenance. Test a failed incremental compile with an existing old artifact. Existing patch-application self-tests alone cannot catch this.

## What session 05 should do differently

These are **Reasoned recommendations**, not edits to the frozen gates or the session-05 prompt.

1. **Fix native build failure propagation before confirming a new patch.** Retest the stale-artifact case. Keep patch/binary hashes and fresh source-key comparisons. Do not infer the existing reports were invalid merely because this defect exists.
2. **Keep `c3-ab4` provisional and the shipped default unchanged.** Allow diagnostic/validation work to continue; do not interpret this review as permission to choose the default after fixing only wheel compression. Compare midpoint at **1200 Hz** as well as c3 at 480/960/1000, with prospective criteria and target-device cost.
3. **Admit aircraft using valid approaches, not post-result exclusions.** Use each aircraft's loading, speed, attitude, configuration and running propulsion/rotor as needed. Verify actual touchdown velocity, not just initial inputs. Retain the old crash tests. The 737 should stay in scope; leave the AH-1S qualification open until a proper rotor-running fixture is built.
4. **Keep the new landing gates prospective.** Easy-case fixture checks necessarily precede them and must be disclosed. Then freeze descent ranges, upright/penetration/contact requirements, bounded forces and a full work/energy budget before comparing candidates. Include springs, propulsion, wind and changes in kinetic/potential energy; “no energy gain” alone is not a valid landing criterion.
5. **Require both wheel geometry and force safety.** Compression-only clipping is disproved here. Check leg projection, compression/rebound speed, projected force, contact location and timestep convergence. A 2 ft cap/0.1 projection guard is a diagnostic, not a universal travel model. Complete airframe contacts and wrapper crash handling remain necessary; zero numerical runaways with 5714-times-weight forces is not success.
6. **Add repeated-contact and forced-flight tests.** G5b alone misses errors introduced at each release. Test touch-and-go, sustained wheel skipping, accumulated angular-rate/attitude error, angular-momentum direction, and force-update latency. Bound the fastest aerodynamic/control/wing-strip modes over the intended envelope. More Hz is margin, not a stability proof.
7. **Contain crashes every physics step.** A check once per rendered frame, after `step(n)`, can be too late. Stop before another invalid step, retain the last accepted finite rendering state and define recovery from `run`/Newton exceptions. Do not blindly continue after a partial update or merely count which integrator produced NaN later.
8. **Choose an engineering accuracy requirement, not a candidate-shaped waiver.** Keep G4's original result. If a separate game-oriented requirement is needed, explain the practical error and create a new gate before comparing candidates. The owner should not have to decide solver correctness from the numerical tolerance alone.

The compression interventions and powered landing diagnostics are evidence for redesigning these tests, **not** new gates used to accept a default retrospectively.

## Reproduction and limits

Outputs and scripts are under `results/review-codex-04/` and `tests/review/review04_*`. [manifest.json](results/review-codex-04/manifest.json) records the shipped binary/patch hashes; they still match the original metadata. Native build metadata records the compiler and module hashes for each diagnostic variant. Python 3.12.14 and Node 22.23.5 were used for the new runtime checks.

Native builds initially needed CMake installed into the virtual environment; that succeeded. No clone, pip, npm or source-download request remained blocked. Typical commands:

```sh
.venv/bin/pip install -r requirements.txt cmake
PATH="$PWD/.venv/bin:$PATH" scripts/build-native.sh
tests/native/verify_key.sh unpatched pip
tests/native/verify_key.sh patched unpatched
.venv/bin/python tests/review/review04_build_failure.py
.venv/bin/python tests/review/review04_build_scratch.py cap
PYTHONPATH=build/native/review04-cap .venv/bin/python tests/review/review04_compression.py
.venv/bin/python tests/review/review04_build_scratch.py guard
PYTHONPATH=build/native/review04-guard .venv/bin/python tests/review/review04_compression.py
PYTHONPATH=build/native/unpatched .venv/bin/python tests/review/review04_compression.py
PYTHONPATH=build/native/patched .venv/bin/python tests/review/review04_powered_landing.py
PYTHONPATH=build/native/patched .venv/bin/python tests/review/review04_release.py
PYTHONPATH=build/native/patched .venv/bin/python tests/review/review04_nasa_rates.py
PYTHONPATH=build/native/patched .venv/bin/python tests/review/review04_identity.py
PYTHONPATH=build/native/patched .venv/bin/python tests/review/review04_contact_cases.py
npx tsx tests/review/review04_airborne.ts
npx tsx tests/review/review04_binding.ts
.venv/bin/python tests/review/review04_friction_math.py
```

Also rerun: both binding variants, comparator self-tests, build-mechanics self-test, native damper modes/sweep and original contact-switch diagnostic. Typecheck and Python syntax checks passed. The PteroLabs source audit takes an independently downloaded `src/models/FGPropagate.cpp` at [commit 33384d9](https://github.com/PteroLabsAI/jsbsim/blob/33384d9981614509c65698f5f8be8eb8d1950228/src/models/FGPropagate.cpp) as its argument.

**Not checked:** all 13 complete native/WASM gate suites again; a new Emscripten build and the unpatched-WASM comparison; candidate timing or thermal behaviour on the iPhone; a powered AH-1S landing; real-aircraft contact-force/travel data; a complete nonlinear proof of patch 0001; a forced Newton-failure recovery experiment; or a memory-leak audit. The scratch compression experiments are native only. The forced damping test uses the shipped WASM, and the powered landing/switch-accuracy results are native. These limits prevent a production recommendation; they are not hidden passes.
