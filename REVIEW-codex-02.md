# Independent review of session 02

Reviewed 15 November 2026. Base: `main` at `d9ff31cb57ae8d9e213ea7550e565831885db233`.
Review branch: `review/codex-02`. No physics, original tests, or original results were changed.

## Verdict

**Do not adopt AB4 at 480–1000 Hz as the phase 2 physics baseline yet.** The build is useful and the short, controlled native/WASM comparisons are excellent, so the integration work need not be discarded. However, the proposed rate threshold is contradicted by additional native tests: AB4 fails on a 737 hard landing at both rates and an AH-1S hard landing at both rates, and several aircraft keep shaking after 60 seconds on their gear even at 1000 Hz. These are not proof that Euler is a complete solution: some extreme cases fail with Euler too. Fix the API errors and establish numerical acceptance tests before building the wing-strip physics on this integrator decision. The recommendation to use native WebAssembly exceptions is reasonable; it does not validate the integrator. **Label: Verified**, based on native JSBSim 1.3.3, the upstream source/history, and NASA data; the API defects below are separately labelled Supported.

## Findings, ordered by severity

Labels: **Verified** means checked against an independent source or native/NASA answer key; **Supported** means reproduced by my own test without such an answer key; **Reasoned** means an inference not experimentally established. A source check verifies what the code does, not every claimed physical consequence.

| Severity | Claim checked | Verdict | Label | Evidence |
|---|---|---|---|---|
| High | “At 480 and 1000 Hz both problems go away”; AB4 only needs ≥480 Hz | **wrong** as a general recommendation | Verified | New [native matrix](results/review-codex-02/ground-matrix.txt): 737 hard landing, first non-finite state at **7.194 s / 5.417 s** at 480/1000 Hz; Euler completes 15 s. AH-1S hard landing also fails with AB4 at **5.837 / 5.858 s**, while Euler completes at both rates. Details and limits below. |
| High | High rates eliminate ground chatter | **wrong** | Verified | Native c172x, final 10 s of a 60 s rest: peak body rate **0.01697 / 0.008005 rad/s** at 480/1000 Hz with AB4, versus **6.46e-9 / 4.42e-9** with Euler. F16, c310, AH-1S and 737 also do not settle with AB4. [Matrix](results/review-codex-02/ground-matrix.txt); [WASM replication](results/review-codex-02/ground-spot-wasm.jsonl). |
| High | The existing comparisons can establish numerical correctness | **weakened** | Supported | [Synthetic test](results/review-codex-02/comparator-probe.txt): `tests/parity/compare.py` compares a finite two-row reference with a one-row NaN candidate, prints **zero maximum difference**, and exits **0**. It truncates to the shorter log and never rejects non-finite values. NASA/AB4 reports are also descriptive, not numerical release gates. |
| High | Every binding call catches C++ exceptions; every error becomes `JSBSimError` | **wrong** | Supported | `sim.hasProperty('review/bad[')` throws a raw `WebAssembly.Exception` with the default build and a non-Error object with the JS-exception build. [Default](results/review-codex-02/binding-probe.txt), [other variant](results/review-codex-02/binding-js-probe.txt). `wasm/bindings.cpp:90`, `105`, `125`, `171` contain unguarded paths. |
| Medium | Reset gives a fresh bulk-exchange interface | **wrong** | Supported | After binding two inputs/outputs, then `reset()`, both views still have length 2 and outputs still read **[90, 91]**. C++ cleared the logical buffers, but TypeScript did not reset `nIn`/`nOut`. [Probe](results/review-codex-02/binding-probe.txt); `src/jsbsim.ts:125`, `173`, `189`. This is stale data, not a demonstrated memory overwrite outside an allocation. |
| Medium | A successful setter means the property was written | **wrong for read-only properties** | Supported | Writing `simulation/sim-time-sec = 1234` reports success but reads back **0**. The binding ignores the property node setter's boolean result. [Probe](results/review-codex-02/binding-probe.txt). This can silently discard an incorrectly bound input. |
| Medium | Handle bounds prevent an invalid handle accessing another property | **weakened** | Supported | Negative/out-of-range C++ integer handles are checked. But JS `NaN`, `0.9`, and `2**32` all access handle 0 after embind conversion. An old handle 0 also silently becomes a new property's handle 0 after reset/rebinding. [Probe](results/review-codex-02/binding-probe.txt). Validate JS integers and define/reset handle lifetimes. |
| Medium | The f16 impact NaN is explained by stiff STRUCTURE springs | **weakened** | Verified | Native ablation at **127 s**, before impact: zero only STRUCTURE static/dynamic friction, leaving springs/damping and the preceding trajectory unchanged. Both 120/240 Hz runs remain finite through 132 s; both baselines fail. [Results/traces](results/review-codex-02/crash-probe.txt). Friction is a causal contributor in these trials; a single exact source of the first NaN has not been instrumented. |
| Medium | `gear/wow` can classify all ground contact | **wrong** | Verified | Upstream [`FGGroundReactions.cpp:113`](https://github.com/JSBSim-Team/jsbsim/blob/66f7fafc07fe13e7ede9db20873030fed2881713/src/models/FGGroundReactions.cpp#L113) explicitly includes only **BOGEY** contacts. Existing AB4 ground/air comparisons use this property. STRUCTURE contact can therefore be labelled airborne. This also matters for any future integrator-switch detector. |
| Medium | AB4 “sits on NASA's solutions” | **holds for body rates; weakened for the full state** | Verified | NASA archive re-downloaded; all five CSVs are byte-identical. At 100 Hz, rate errors against sim_01 are **2.16e-5, 3.21e-5, 1.04e-5 deg/s**: excellent. But attitude errors are **0.104°, 0.0498°, 0.0245°** and ECEF X differs by 0.67 ft. [Audit](results/review-codex-02/nasa-audit.txt), [original numbers](results/02-test4-nasa.txt). |
| Medium | A worst-distance/spread ratio near 1 means “inside NASA's spread” | **wrong as an envelope statement** | Verified | At 100 Hz, AB4 rates lie outside the pointwise NASA min/max envelope at **163 / 135 / 123 of 301** samples; maximum excesses are only the small rate errors above. The new ratio is a legitimate descriptive distance, but is not a containment test or a predeclared pass threshold. [Audit](results/review-codex-02/nasa-audit.txt). |
| Medium | Native sensitivity proves c1723/f16 differences are “not our build”; logic errors would jump suddenly | **wrong as proof** | Reasoned | A small systematic force/control error can also grow smoothly in a sensitive system. A single altitude perturbation shows sensitivity, not equivalence, and does not locate the first differing computation. The report's ledger is more cautious than its summary and “Proof” paragraph. |
| Medium | Present reruns compare `-fexceptions` against `-fwasm-exceptions` | **wrong in parts of the runner** | Supported | `createSim()` now defaults to `jsbsim-weh`. `scripts/run-tests.sh` test 2 creates its baseline without setting `JSBSIM_VARIANT`, then compares it to explicitly selected `jsbsim-weh`: the same build. Test 3's first benchmark is similarly mislabelled `-fexceptions`. Test 1 explicitly selects both and remains valid. [Rerun](results/review-codex-02/rerun-parity.txt), `src/wasm.ts:21`. |
| Medium | All aircraft that load are usable in the supplied Node installation | **weakened** | Supported | The 737 loads, but stepping reaches its configured socket input and fails with **Cannot find module 'ws'** on clean dependencies. `ws` is absent from `package.json`. [Failure](results/review-codex-02/node22-missing-ws.txt). This is separate from numerical stability. |
| Medium | Restoring the 2010 friction “changes nothing when Euler is used” | **wrong for the usual default configuration** | Verified | The old correction covers translation **and** rotation. Current defaults are Euler rotation but **AB2 translation**. Restoring it changes translation even if rotation stays Euler. [Historical diff](results/review-codex-02/source-history.txt); upstream `FGPropagate.cpp:88`. |
| Medium | A new `wasm/patches/*.patch` will be used by the next build | **weakened** | Reasoned | `scripts/build-wasm.sh:19` applies patches only when cloning the source directory. With an existing `build/jsbsim-v1.3.3`, newly added integrator patches are silently skipped. This will matter immediately in phase 2. No patched rebuild was performed. |
| Low | The 2010 correction was lost in the cited August 2011 commit | **holds in substance; chronology weakened** | Verified | `53709ba8` introduced it. **`e67c5e42` (17 July)** moved it into FGAccelerations and disabled it. **`85b3a574` (24 July)** re-enabled friction with Euler-style RHS. **`40279c20` (14 August)** deleted the already-disabled helper. It was not simply moved elsewhere and retained. [History](results/review-codex-02/source-history.txt). |
| Low | A friction solver assuming Euler interacts badly with AB4 | **holds for the mismatch; exact share of each observed instability remains unisolated** | Verified | Upstream `FGAccelerations.cpp:232` uses slip/dt and has no integrator/history inputs. `FGPropagate.cpp:352` uses AB4 weights. History confirms an explicit integrator-aware correction formerly existed. The ablation supports involvement in the crash, but does not prove every ground oscillation comes solely from this term. |
| Low | Bulk views recover after WASM memory growth | **holds with a lifetime condition** | Supported | Forced actual C++ allocation grew memory; the old cached view detached (length 0), while reacquiring `sim.inputs` produced a valid length-2 view and correct [90,91] exchange. Callers must reacquire views after allocation-capable calls. [Probe](results/review-codex-02/binding-probe.txt). Reset/rebinding is a separate issue. |
| Low | The native/WASM build agrees in controlled flight | **holds for the new tests** | Verified | Four 10 s flights: c172x/f16 × Euler/AB4, 480 Hz, identical binary-valued open-loop controls; every one of 4801 rows and 30 properties compared. Max position difference **3.73e-9 ft**, body/linear velocity differences below **8e-13**, force differences below **1.2e-9 lb**. Both exception variants pass. [Default](results/review-codex-02/parity-probe.jsonl), [JS exceptions](results/review-codex-02/parity-js-probe.jsonl). These flights do not prove crash/ground-roll equivalence. |
| Low | 59/61 loads; external force hook matches native | **holds for tested cases** | Verified | Reran tests 1–5. Both explicitly selected variants load the same 59 as native. External force/moment comparison is exact in the single-force schedule. [Load matrix](results/review-codex-02/rerun-loadmatrix.txt), [forces](results/review-codex-02/rerun-extforce.txt). “Identical end state” in force benchmarks checks only altitude and speed, not the full state. |
| Low | Exception flags reach JSBSim; the default build choice is sensible | **holds by source inspection and new timing, with limits** | Supported | Flags are set before `add_subdirectory`; upstream CMake contains no disabling override found. Fresh, alternating-order Node batches favour native WASM exceptions by about **1.5–1.6×** in medians. [Timing](results/review-codex-02/benchmark-probe.jsonl). No Emscripten rebuild, no original generated flags, no new iPhone measurements. |

## What the additional ground tests establish

**Verified.** [ground_matrix.py](tests/review/ground_matrix.py) ran **120 native trials**: six models, five scenarios, two rates and two rotational-rate integrators. Rest runs last 60 s; impact runs last 15 s or stop at the first non-finite checked state. Every step checks rates, AGL and three local velocities. Other integrator slots retain their defaults. Engines are not commanded to start.

Impact initial conditions are explicit: 40 ft AGL; hard landing = level, 100 ft/s north and 30 ft/s down; inverted = 180° bank, 100 north and 80 down; banked = 75° bank/−15° pitch, 100 north and 80 down; nose impact = 10° bank/−75° pitch, 20 north and 100 down. These are numerical stress tests, not validated representations of survivable accidents.

Final-ten-second native rest results, maximum absolute component of body angular rate:

| Model | AB4, 480 Hz | AB4, 1000 Hz | Euler, 480/1000 Hz |
|---|---:|---:|---:|
| c172x | 0.01697 | 0.008005 | both <7e-9 |
| f16 | 0.03393 | 0.01506 | both <2e-9 |
| c310 | 0.003675 | 0.001743 | both <2e-9 |
| ah1s | 0.09540 | 0.03744 | both <3e-9 |
| 737 | 0.001810 | 0.000858 | both <2e-9 |

**Verified.** Merely checking that a run remains finite misses persistent motion by many orders of magnitude. The original taxi peak also mixes startup transients with sustained jitter; the final-ten-second statistic directly tests settling. New failures on AH-1S and 737 disprove a general 480/1000 Hz sufficiency claim. Their cause has not been separated into contact, rotor/aerodynamic and gyroscopic contributions. In particular, 737 lacks STRUCTURE contacts, so its crash geometry is incomplete; this does not make an accepted hard-landing state numerically safe.

**Reasoned limitation.** The F450 `initGrnd` places its reference at ground elevation, initially penetrating its contacts. Its violent startup and failures, including an Euler failure, are retained in the raw matrix but excluded from the rest comparison above. They should not be presented as evidence of a correctly initialized resting drone failing. Several other extreme impacts fail under both integrators. None of these tests establishes realistic crash physics, and a crash-stop policy is still needed.

## The F-16 failure: what is now isolated

**Verified.** [crash_probe.py](tests/review/crash_probe.py) follows the unmodified native `f16_test` until 127 s, then compares three variants: unchanged AB4; AB4 with only the seven STRUCTURE points' static/dynamic friction set to zero; and rotation switched to Euler. The last two remain finite through 132 s at both low rates. The no-friction intervention retains the original spring and damping coefficients. It is a diagnostic ablation, not a proposed physical fix.

| Rate | First STRUCTURE contact, baseline | First rate >1e6 rad/s | First non-finite logged quantity |
|---|---:|---:|---:|
| 120 Hz | 127.875 s | 127.983 s | 128.025 s |
| 240 Hz | 127.892 s | 128.029 s | 128.050 s |

**Verified.** The report's “first non-finite” rate-sweep column actually stops when a rate is **≥1e6**, whether finite or not (`tests/ab4/rate_sweep.ts:24`). Those are runaway times, not the first actual NaNs. In the new 120 Hz trace, rates alternate and grow rapidly during contact; by 127.933 s roll rate is −124 rad/s, then +231 and −283 in successive steps. Ground roll moments exceed 1e8 lb-ft. At 127.983 s the model leaves contact with rates already in the millions and enormous aerodynamic loads. At 128.025 s logged position/accelerations become NaN while the rates are still finite at roughly 1e162.

**Reasoned.** Subsequent overflow is unsurprising: the equations contain quadratic products of angular velocity and velocity-dependent aerodynamic loads. However, I did not instrument the native C++ execution to identify the first invalid floating-point operation. The justified conclusion is **unstable coupled contact with friction contributing causally, followed by nonlinear runaway/overflow**. It is not “springs alone”, nor proof that restoring the old friction fully fixes the crash.

## NASA: good rate accuracy, overstated scope

**Verified.** I downloaded the [NASA archive](https://nescacademy.nasa.gov/src/flightsim/Datasets/Atmos_02_TumblingBrickNoDamping.zip) independently. [nasa-audit.txt](results/review-codex-02/nasa-audit.txt) records SHA-256 hashes and byte equality for every supplied CSV. The archive supplies five participant files, not six files; sim_03 is absent. The JSBSim runs cover all 301 expected 0.1 s samples. Sim_05 has only **245 exact time matches**, so the original comparisons silently use less coverage for it.

**Verified.** AB4's rate agreement is real and large compared with Euler. At 480 Hz its worst rate error against sim_01 is **1.393e-6 deg/s**; at 1000 Hz it is **3.207e-7 deg/s**. The report's “within 1e-6 at 480–1000” misses the 480 Hz pitch value, but that small wording error does not change the numerical result. The Euler rate errors and approximately 100×/10× spread ratios reproduce.

**Reasoned interpretation.** The replacement ratio answers “how far am I from the most distant participant, relative to the largest participant separation over the whole run?” It does not answer “am I inside the participants' range at this time?” Its near-1 values are dominated by the farthest participant. Changing and disclosing this metric is acceptable exploration; using it to turn an earlier failed containment test into an unconditional pass is not an independent accuracy gate. The absolute distances are the stronger evidence here. Predeclare separate tolerances for rates, attitude and position.

**Verified.** Fixing rotational **rates** leaves rotational **position** on its default Euler integrator. At 480 Hz, AB4 still has roll/pitch/yaw errors of **0.02172° / 0.01039° / 0.00452°** against sim_01. I tested the existing JSBSim alternatives without patching physics: using its **Buss 2 quaternion integrator (position/rotational = 7)** with AB4 rates reduces the worst attitude error to **1.64e-5°**, with unchanged rate errors. AB2 rates with Buss 2 give worst rate error **5.39e-5 deg/s** and worst attitude error **9.16e-5°** at 480 Hz. [Test](tests/review/nasa_integrators.py), [results](results/review-codex-02/nasa-integrators.txt). This is a worthwhile additional candidate, not evidence of ground stability.

**Verified.** The constant ECEF X offset is consistent with the configured planet radius: `brick.xml` specifies 20925646.9951 ft; at zero latitude/longitude and 30000 ft altitude, the model starts at 20955646.9951 ft, whereas NASA sim_01 starts at 20955646.3253 ft. The **0.6698 ft initial offset is already in the initial geometry**. This does not validate every later position difference or the entire planet model.

## Friction history and alternatives

**Verified.** The upstream [2010 change](https://github.com/JSBSim-Team/jsbsim/commit/53709ba8e1f2cacf1272a2c3a799b1d3f9f43ff2) really included leading weights and derivative history. The 2011 sequence is recorded in [source-history.txt](results/review-codex-02/source-history.txt). The current solver's Euler-style correction is real. There is also explicit time-step dependence in `FGLGear.cpp:366`: contact compression speed is capped by compression distance/dt. Spring/damping forces, switching between contact/no contact and static/dynamic friction, the constraint iteration and default AB2/AB3 translation all interact. The friction RHS is not the whole ground model.

**Verified.** The requested three alternatives are **already present** in the current REPORT-02.md. They are not missing options. I independently read [PteroLabs PR 12](https://github.com/PteroLabsAI/jsbsim/pull/12) and [PR 13](https://github.com/PteroLabsAI/jsbsim/pull/13), including the latter's implementation; I did not run either patch.

**Reasoned risks and further candidates:**

- **Restore integrator-aware friction.** History makes this plausible, not a drop-in guarantee. Derivative histories, coordinate transforms and the changed scheduling must match current JSBSim. Translation and rotation can use different leading weights in the same coupled contact constraint. Verify their combined effect, friction limits and work, not only residual slip. The default translation behaviour changes too.
- **Implicit midpoint body rates.** The fork treats the gyroscopic term implicitly but keeps the applied moment explicit. Conservation of a free rigid body's energy does not imply stable spring/friction contact or accurate forced motion/attitude. It has Newton solves, substeps and tolerances. The code throws on finite Newton non-convergence or a singular Jacobian; its Euler fallback is for excessive/non-finite step rates, not a universal recovery path. Count these paths and assess their runtime.
- **Air/ground switching.** Detect every BOGEY and STRUCTURE point, not only `gear/wow`. Account for detection one step after penetration, chatter at the switching boundary, release/recontact, changing dt and multistep history. Ordinary scheme selection does not restart history. The Euler-at-127 ablation is not a tested automatic switching algorithm.
- **Existing AB2/AB3 plus improved attitude integration.** The NASA experiment above shows AB4 is not the only accurate airborne option. Lower-order multistep rates still mismatch the current friction solver, so do not substitute them without the same rest/contact tests.
- **Contact substeps or a joint velocity-level constraint/integration design.** Worth evaluating if accuracy and robustness remain incompatible, but larger changes require new native baselines and force/work checks. Raising frequency alone is not a stability argument.

## Missed issues

**Supported.** The raw `hasProperty` exceptions, silently ignored read-only writes, stale reset outputs, handle coercion/aliasing, NaN/truncation-blind comparator, same-build variant comparison and missing `ws` runtime dependency are absent from the original report. Their reproductions and consequences are in the findings table.

**Verified.** Time-step changes have an additional trap: upstream `FGFCSComponent.cpp:59` copies the channel dt into each component at construction, and `FGFilter.cpp:112` calculates its coefficients from that cached value. `FGFDMExec::Setdt` only sets the executive's dt. Setting a new dt after loading a model therefore does not generally retime its controller filters. Set the intended rate **before** loading the model, or reload/reinitialize the affected systems. Script loading already sets dt before loading the aircraft. This matters when comparing rates or designing adaptive contact substeps.

**Supported provenance note.** My first native matrix set dt after model loading. It is preserved as `ground-matrix-dt-after-load.txt`; the final `ground-matrix.txt` sets dt before model loading. Some violent outcomes change with this initialization choice. The direct script-loading native/WASM spot probes are also retained. Their impact trajectories need not match after small initial differences; they must not be described as bit-identical crash replications. The repeated rest failure and native 737 AB4 failures remain the relevant counterexamples.

## Binding, build and performance

**Supported.** The tested invalid-path exception escapes `hasProperty`, which lacks `guard`. Other unguarded paths include cached `get`, `readOutputs` and allocations/conversion in `bindList`. The paths actually reproduced are in both [binding logs](results/review-codex-02/binding-probe.txt). A getter may invoke tied C++ code; protecting only writes is not a complete exception boundary.

**Supported.** The guarded `getProperty('review/bad[')` does produce `JSBSimError`, but loses the parser's message: it reports `unknown C++ exception`. Upstream property parsing throws `std::string`, which the guard's `std::exception` catch does not cover specifically. Read-only property writes also falsely report success, as reproduced above. Error conversion and write validation need to cover these ordinary paths.

**Reasoned.** `std::unique_ptr` and smart property pointers provide ordinary destruction ownership. I found no demonstrated steady-state leak. But TypeScript `JSBSim.create()` does not delete its raw Sim when `init`/`check` throws; `createSim()` does not clean up if file copying fails. Embind objects require explicit deletion. Exception recovery also is not transactional rollback of a partially loaded model. Test repeated failure/recovery with heap accounting before claiming “no leaks” or universal survival. The current common load errors do recover in the existing smoke/page tests.

**Supported.** Zero dt and unknown integrator ID 12345 are accepted. JSBSim's integration switch has a default branch doing nothing, so a typo can silently freeze an integrated quantity. Missing property reads intentionally return zero and writes create a property; misspelled force channels can consequently appear to succeed. For setup this mirrors JSBSim; a physics hot path needs strict names, IDs, finite values and units.

**Supported.** Actual WASM growth works when the wrapper getter is used again. Caching a Float64Array across allocation-capable calls is unsafe. Reset leaves old lengths and stale values; rebinding also invalidates the meaning/lifetime of views. C++ `vector::clear()` retains capacity, so the reset reproduction is not proof that memory was freed or that another object was corrupted.

**Supported.** In seven alternating-order, freshly initialized Node timing batches at 1000 Hz, median µs/step were:

| Aircraft / rates | JS exceptions | Native WASM exceptions |
|---|---:|---:|
| c172x / Euler | 35.17 | 23.21 |
| c172x / AB4 | 33.05 | 22.04 |
| f16 / Euler | 38.97 | 24.02 |
| f16 / AB4 | 39.59 | 24.81 |

**Reasoned interpretation.** These cloud timings support the default exception choice, not a transferable phone cost. Batching addresses the phone timer's 1 ms resolution. However, the original Node benchmark takes the best of successive batches on different evolving states, not repetitions of the same workload; the supposed “no external forces” case actually loads the **one-force** fixture. The browser benchmark takes one short batch per case in fixed order. Its end-state comparison rounds **altitude/speed only**. Neither isolates try/catch overhead from all other work, tests a no-exception build with identical source/flags, nor measures sustained phone thermals and rendering/wing-strip costs. “About 1% of one core” is a short-run extrapolation, not a product frame-budget measurement.

**Reasoned build limitation.** The CMake ordering is correct for passing the chosen exception flag into JSBSim and bundled expat; I found no source override disabling it. I did not rebuild or inspect the original generated `flags.make`, so cannot independently attest that the committed binaries were produced by this exact recipe. The script warns rather than fails on a different Emscripten version, applies patches only on a fresh clone, and records no applied-patch hashes. Those are reproducibility gaps before adopting a physics patch.

## Tests to add before phase 2

The following are **Reasoned recommendations**. Thresholds are proposed review gates, not claims that a real aircraft has been validated. Declare product tolerances before seeing candidate-fix results.

| Test | Pass/fail condition |
|---|---|
| Sixty-second rest, c172x/f16/c310/ah1s/737, supported rates and all proposed integrator combinations | During 50–60 s, every checked state finite; every body-rate component <1e-6 rad/s. Also set an explicit creep limit, e.g. <0.01 ft displacement over those ten seconds. Exclude startup transients from the rest statistic. Current AB4 fails the rate gate. |
| Controlled hard landings and attitude sweep, including STRUCTURE-only contact | Every state/force/moment checked every step. No unhandled exception or non-finite state. Establish rate/penetration/energy limits for survivable landings against a step-refined reference. For destructive impacts, enter a defined crash state before runaway and keep rendering inputs finite. Current AB4 fails the finite gate in several added cases. |
| F16 crash attribution | Replay the same pre-impact trajectory; compare baseline, integrator-aware friction, normal-force diagnostics and explicit crash policy at 120/240/480/1000 Hz. Pass only when the candidate handles the impact without runaway or hidden clamp/fallback; log first contact, first threshold crossing and first actual non-finite value separately. |
| Native/WASM parity | Reject length/time/header mismatch and any NaN/Inf before computing differences. Both variants explicitly selected. The new smooth-flight gates are positions ≤1e-4 ft; velocity ≤1e-5 ft/s; rate/attitude/surface positions ≤1e-7; force/moment difference ≤1e-5 + 1e-7 times native peak magnitude. All new smooth-flight cases pass. Add engine-on states and synchronized short-window ground/contact replays; do not hide coherent force bias inside a chaotic long-run tolerance. |
| NASA full state and convergence | Require all 301 JSBSim samples and report per-reference matching counts. At ≥480 Hz, proposed gates vs sim_01/04: rate error <2e-6 deg/s and attitude error <1e-3°. Retain every position offset with its physical cause; do not redefine “inside spread” after running. Current AB4 rates pass, default Euler attitude integration fails the attitude gate. |
| Torque-free rigid bodies and forced rotation | Fixed positive-definite inertia, including products of inertia; test several spin axes/rates and longer durations. Bound relative energy/angular-momentum drift, e.g. <1e-6 over 60 s for a proposed production configuration, and test convergence to an independent high-accuracy solution. Under applied torque check work and spin-up, not conservation. |
| Ground work/energy | Still air, fixed mass, no propulsion, stationary terrain, defined gravity potential; include stored spring energy or its work balance. Require bounded numerical energy error and correct dissipation under refinement. “Engine off implies total energy never increases” alone is not a valid general test in wind, moving terrain, or while springs release stored energy. |
| Switching, reset and variable dt | Repeated touches/releases at every contact type; no missed STRUCTURE contacts, stale derivative startup, extra impulse or rapid scheme flapping. Quantify errors against fixed-step reference. After reset, input/output lengths must be zero and old handles/views must fail safely under a documented lifetime contract. |
| Exception boundary and lifecycle | Malformed paths through every public accessor, failed bind/load/init, then valid use; every declared recoverable failure is `JSBSimError`, not a raw WASM exception. Bounded heap usage over repeated failure/reset/delete cycles; no bulk buffer state mismatch after a failed bind. |
| Strict API input validation | Reject NaN/fractional/wrapped handles, invalid integrator/slot combinations, non-positive/non-finite dt and invalid step counts before embind conversion. Wrong property names in strict force bindings must fail rather than create unused channels. |
| Test harness self-tests | Feed truncated, time-shifted, NaN/Inf and out-of-tolerance synthetic logs. Every case exits nonzero. Explicitly log variant names and binary hashes so a same-build comparison cannot be labelled cross-variant. |
| Reproducible patch build and runtime matrix | Adding/changing a patch in an existing build tree must change the recorded patch hash and rebuild the intended source. Clean install must run selected aircraft, not just load them; resolve or deliberately disable socket I/O dependencies. Verify the actual EH binary on minimum supported browsers. |
| Product performance | Measure the selected complete integrator, contact/crash handling, output exchange, wing-force calculation and rendering together on the target iPhone. Use repeated batches, median/tail frame cost and a sustained run (e.g. 10 minutes); require no growing simulation backlog within a declared game frame budget. |

## Reproduction and what could not be checked

**Supported execution record.** Upstream JSBSim cloned successfully at tag v1.3.3, commit `66f7fafc07fe13e7ede9db20873030fed2881713`. `jsbsim==1.3.3` installed successfully in Python **3.12.14**. npm initially failed because its default cache under `/home/agent/.npm` was unavailable; `npm ci --cache /workspace/work/npm-cache` succeeded. No npm/pip/clone/NASA network operation remained blocked. Original tests 1–5, smoke and typecheck ran on Node **24.22.1**; additional smoke/binding/contact checks used separately installed Node **22.23.5**. The preserved baseline summaries are named `rerun-*`, not replacements for the original results. Typecheck passed.

New commands, from the repository root after dependency setup:

```sh
npx tsx tests/review/binding_probe.ts
JSBSIM_VARIANT=jsbsim npx tsx tests/review/binding_probe.ts
JSBSIM_DEBUG=0 .venv/bin/python tests/review/ground_matrix.py
JSBSIM_DEBUG=0 .venv/bin/python tests/review/crash_probe.py
JSBSIM_DEBUG=0 .venv/bin/python tests/review/parity_probe.py
npx tsx tests/review/parity_probe.ts
.venv/bin/python tests/review/parity_compare.py
JSBSIM_VARIANT=jsbsim npx tsx tests/review/parity_probe.ts
.venv/bin/python tests/review/parity_compare.py
.venv/bin/python tests/review/nasa_audit.py /path/to/Atmos_02_TumblingBrickNoDamping.zip
JSBSIM_DEBUG=0 .venv/bin/python tests/review/nasa_integrators.py
.venv/bin/python tests/review/comparator_probe.py
npx tsx tests/review/benchmark_probe.ts
npx tsc
```

**Supported runtime qualification.** `ground_spot.ts` additionally replicates selected matrix cases in WASM. Its 737 needs `ws`, which the repository does not declare. I installed `ws` outside the repository and used `NODE_PATH=/workspace/work/review-runtime/node_modules` for that diagnostic run. See the preserved clean-install failure and the final spot log. No dependency manifest or aircraft was changed to hide that failure.

**Could not check:** iPhone/Safari timing or long-run battery/thermal behaviour; actual browser minimum-version compatibility; original user-device logs beyond their transcription in REPORT-02; a clean Emscripten rebuild (no activated Emscripten toolchain was supplied) or original build flags; the PteroLabs fixes running in this project; real-aircraft ground/contact accuracy; a precise C++ stack trace for the first floating-point invalid operation; and a full allocation/leak audit. These are **not run**, not passes. The controlled parity experiment strengthens build confidence but leaves the exact original c1723 ground-roll divergence and the libm seed location unresolved. A native altitude perturbation cannot close those questions.
