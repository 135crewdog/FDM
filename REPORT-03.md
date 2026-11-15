# Session 03: fixes, acceptance gates, floor and first integrator candidate

Date: 2026-11-15. Raw outputs: `results/03-*.txt`. How to rebuild and rerun: `CLAUDE.md` and `GATES.md`.

## Summary

- **The defects from the independent review are fixed**, each with a permanent test that failed before the fix
  and passes after it.
- **We now have a native answer key that can carry patches.** JSBSim v1.3.3 built here from source gives
  bit-identical results to the official pip package.
- **The gates were written and committed before anything was run against them** (commit below).
- **No configuration passes every gate.** The integrator decision stays open for session 04, as planned.

| | G1 Rest | G2 Hard landing | G3 Extreme impacts | G4 NASA | G5 Rigid body | G6 Parity |
|---|---|---|---|---|---|---|
| **Floor** (Euler body rates, Buss 2 attitude, no patch) | PASS | FAIL | reference | FAIL | FAIL | PASS |
| **Candidate 1** with AB4 body rates | FAIL (19 of 20) | FAIL | worse than floor | PASS | FAIL | PASS |
| **Candidate 1** with AB3 body rates | PASS | FAIL | worse than floor | PASS | FAIL | PASS |
| **Candidate 1** with AB2 body rates | PASS | FAIL | worse than floor | FAIL | FAIL | PASS |

What that means in plain words:

- **Candidate 1 does what it was built for.** With the friction patch, aircraft standing on the ground settle
  with AB2, AB3 and AB4 body rates, where unpatched AB4 kept shaking. The one exception is the c310 at 120 Hz
  with AB4, and that one is not a friction problem (see "What we learned").
- **Candidate 1 keeps AB4's accuracy in the air.** AB4 and AB3 with Buss 2 attitude match NASA to 1.4e-6 deg/s and
  1.6e-5 deg at 480 Hz. The floor is 0.09 deg/s and 0.5 deg off, about 46,000 times the gate.
- **Candidate 1 does not fix hard landings or crashes.** With AB body rates they blow up somewhat more often than
  the floor. Friction was only part of the ground problem; the rest comes from the landing-gear springs and
  dampers, which the patch does not touch.
- **The floor is weaker than we thought.** It also blows up in hard landings at 120 and 240 Hz (and once at
  480 Hz), and its body rates lose or gain energy quickly when tumbling fast.
- **Hard-landing results are partly luck.** These runs are numerically chaotic: a rounding-level difference
  decides whether a run survives. Read single failures in G2 and G3 with that in mind.
- **Cost:** candidate 1 costs nothing measurable per step.

Nothing here changes the shipped default. The patch is in the build but switched off; with it off, results are
bit-identical to unpatched JSBSim.

## Gates commit (recorded before any candidate was run)

The acceptance gates (`GATES.md`, `tests/gates/`) were committed as
**`164c1d0380c3290525623e2ba82ce9b99b299ddb`**.

At that commit no candidate had been run, not even the floor, and candidate 1's patch had not been written.
Only two reference configurations with answers already known from the independent review had been run, to check
the measuring code (`results/03-gates-ref-default.txt`, `results/03-gates-ref-ab4.txt`).

The gate files have not changed since (`git diff 164c1d0 HEAD` over the frozen files is empty), and every result
file names that commit. `tests/gates/run.sh` refuses to run a candidate if the gate files are uncommitted or
changed.

## Evidence ledger

Labels as in `CLAUDE.md`: **Verified** = checked against an answer we did not produce; **Supported** = our own
test shows it, no outside answer key; **Reasoned** = explanation, not tested.

| # | Finding | Label | Evidence |
|---|---|---|---|
| 1 | Binding defects are fixed: every error is a `JSBSimError` with JSBSim's message; read-only writes, bad handles, bad dt, bad integrator ids and bad step counts are rejected; `reset()` clears bulk bindings and invalidates old handles | Supported | `tests/binding/regress.ts`, built from the review's probe: 53 of 73 checks failed before, all pass after, on both variants (now 75 checks). `results/03-binding-*`. No outside answer key for an API contract. |
| 2 | The comparator can no longer pass a broken log | Supported | `tests/parity/selftest_compare.py`: the old comparator let 10 kinds of bad log through with exit code 0; the new one refuses or fails all 16 kinds of bad log and still passes the 4 good cases. `results/03-comparator-*`. |
| 3 | Session 02's results still hold with the fixed harness and the new binaries | Verified (against native JSBSim) | Tests 2 and 4: every table line is identical to session 02's. Tests 1, 3, 5 reproduce. Both variants named and hashed in each file. `results/03-test*.txt`. |
| 4 | JSBSim v1.3.3 built here from source is a valid answer key | Verified (against pip's `jsbsim==1.3.3`) | Same load matrix; bit-identical logs on tests 2 to 4 and the review's four controlled flights (11 logs). `results/03-native-key-unpatched-vs-pip.txt`. |
| 5 | With the patch switched off, the patched builds equal the unpatched ones | Verified (against the unpatched builds) | Bit-identical: 11 native logs, 18 WebAssembly logs (both variants). `results/03-native-key-patched-off-vs-unpatched.txt`, `results/03-wasm-patched-off-vs-unpatched.txt`. |
| 6 | The gate harness measures correctly | Verified (against the review's numbers) | Reproduces the review's rest rates, hard-landing NaN times and NASA errors for the two reference configurations (list in `GATES.md`). |
| 7 | Floor: body rates 0.092 deg/s (480 Hz) and 0.044 deg/s (1000 Hz) from NASA; attitude 0.52 and 0.25 deg | Verified (NASA data) | G4. Buss 2 cannot help while the rates themselves are wrong. |
| 8 | Floor fails hard landings: ah1s at 120, 240 and 480 Hz, 737 at 120 and 240 Hz | Supported | G2, native and WebAssembly. The review had only run 480 and 1000 Hz. |
| 9 | Floor's Euler body rates do not conserve energy when tumbling: 0.4% drift in 60 s at NASA's slow spin (480 Hz), 63% at 229 deg/s, non-finite at 712 deg/s | Supported | G5. Consistent with the known NASA rate error (finding 7). |
| 10 | Candidate 1 makes aircraft settle at rest with AB2, AB3 and AB4 (59 of 60 runs; rates about 1e-8 rad/s) | Supported | G1, native and WebAssembly agree. An outside report of the same effect exists (PteroLabs PR 12) but is unreviewed. |
| 11 | Candidate 1 with AB4 or AB3 passes the NASA gate | Verified (NASA data) | G4: 1.4e-6 deg/s and 1.6e-5 deg at 480 Hz; 3.2e-7 and 3.8e-6 at 1000 Hz. AB2 fails the rate gate (5.4e-5, 1.2e-5 deg/s). |
| 12 | Candidate 1 with AB rates is worse than the floor in hard landings and crashes | Supported, noisy | G2: 13 to 14 of 20 stay finite (floor 15). G3: 12 to 16 runaways of 60 (floor 9 to 10). See finding 14 on noise. |
| 13 | The c310's leftover oscillation (120 Hz, AB4) is not friction | Supported | It is in pitch and persists with all friction removed; it disappears at 240 Hz, with AB3, or with Euler translation. `results/03-diag-c310-rest.txt`. |
| 14 | Hard landings are numerically chaotic, so a single pass or fail is partly luck | Supported | 737, 120 Hz, defaults: native and WebAssembly agree to 4e-7 for 3.4 s, then differ a millionfold within 0.15 s; one ends in NaN, the other does not. `results/03-diag-737-divergence.txt`. |
| 15 | The mechanism behind 13 and behind the AB hard-landing failures is the gear's spring-damper being too stiff for the integrator's stability limit | Reasoned | Fits: AB4 tolerates about 7 times less damping per step than Euler, and the failures move with rate and order as expected. Not tested. Test: sweep the gear damping coefficient, or compute the eigenvalues of the linearised gear modes times dt. |
| 16 | The 2010 formula as written lets a resting aircraft creep; the adapted formula does not | Supported | Creep in 10 s at 120 Hz: 0, 1.49e-3, 2.32e-3, 1.49e-3 ft at latitudes 0, 20, 45, 70 deg. The prediction from the Earth's rotation gives the same four numbers. `results/03-diag-creep-and-startup.txt`. |
| 17 | AB4's G5 failures are a start-up effect, not a drift | Supported | The energy changes in the first 4 steps (2.1e-6 at 480 Hz, with a 1.3e-5 spike inside them) and is then constant to 3 digits for 60 s. AB3 also drifts slowly afterwards. Same file. |
| 18 | Candidate 1 costs nothing measurable | Supported | Node, median of 7: all configurations within about 10% of each other, which is the scatter between repetitions. |
| 19 | The patch's derivation (matrix weighting, extra right-hand-side terms) is correct | Reasoned, with supporting tests | Derived by hand (patch header). Supported by findings 10 and 16. Not checked by anyone else. |

Yardsticks: no gate, tolerance or yardstick was changed after seeing results. Choices I made in turning the gates
into tests are listed in `GATES.md` and under "Things a reader should know" below.

## Step 1: defects fixed

| Defect (from the review) | Test that shows it | Before | After |
|---|---|---|---|
| Raw WebAssembly exception from `hasProperty`, `get`, `readOutputs`, `bindList` | `tests/binding/regress.ts` section 1 | raw `WebAssembly.Exception` | `JSBSimError` |
| `std::string` throws shown as "unknown C++ exception" | section 1 | "unknown C++ exception" | JSBSim's text, e.g. "unterminated index (looking for ']')" |
| Writes to read-only properties report success | section 2 | silent | error, by name, by handle and in bulk |
| `NaN`, fractions, 2^32 + h become handle 0 | section 3 | read or wrote the wrong property | rejected |
| `reset()` keeps bulk arrays; old handles alias new properties | section 4 | length 2, stale values | length 0; old handles rejected |
| Zero dt, unknown integrator ids accepted | section 5 | accepted | rejected; dt must also be set before loading |
| Bad step counts (added) | section 6 | ran 0 steps silently | rejected |
| 737 needs npm `ws` | section 7 | "Cannot find module 'ws'" | runs |
| Comparator ignores NaN, truncates | `tests/parity/selftest_compare.py` | exit 0 on 10 kinds of bad log | all 16 kinds of bad log refused |
| Runner compares a build with itself | `scripts/run-tests.sh` | default build twice | variant named on every run; hashes printed |
| "First non-finite" really meant rates > 1e6 | `tests/ab4/rate_sweep.ts` | one column | two columns |
| Benchmarks compare different workloads | `tests/extforce/` | evolving state; "no forces" had one | same workload each repetition; truly no force |
| New patches skipped by the build | `tests/build/selftest_patches.sh` | applied only on a fresh clone | re-applied every build; hashes recorded; wrong Emscripten stops the build |
| Native runs write into `jsbsim-data/` | check in `scripts/run-tests.sh` | 4 files had been committed | scratch directory; the runner fails if anything appears |

How each was fixed:

- **Handles** are now numbers of the form generation x 2^20 + index, passed as doubles and checked in C++.
  `reset()` starts a new generation, so an old handle can never address a new property. The rule is written at
  the top of `src/jsbsim.ts`.
- **dt:** `sim.dt = x` throws once a model is loaded, because control-system filters keep the old dt.
  `setDtAfterLoad()` exists for deliberate use.
- **737 and `ws`: I chose to disable socket input in our runtime**, not to add the dependency. A phone game has
  no use for a network input port, and it does not affect the physics unless something connects.
- **New binding call:** `loadIC(name)`, so the gate tests set an aircraft up the same way on both platforms.
- One thing found on the way: the review's own native probes also wrote a file into `jsbsim-data/`. One line was
  added to each.

Step 1.4: tests 1 to 5 were re-run with both variants named and the final binaries
(`results/03-test0..5-*.txt`). Session 02's results hold (ledger 3).

## Step 2: native answer key for patched JSBSim

`scripts/build-native.sh` builds JSBSim's Python module from the same pinned source, with the same patch
mechanics (`scripts/lib-jsbsim-src.sh`), as the WebAssembly build. Select it with `PYTHONPATH=build/native/<set>`.

- Unpatched source build against pip: bit-identical everywhere it was compared (ledger 4).
- Patched source build with the patch off against the unpatched one: bit-identical (ledger 5).
- So the patched native build is the answer key for the patched WebAssembly build. G6 uses it.

## Step 3: the gates

Defined in `GATES.md`; numbers in `tests/gates/gates.json`. In short:

| Gate | What must hold |
|---|---|
| G1 Rest | 5 aircraft, 60 s on the gear, 4 rates: body rates < 1e-6 rad/s and < 0.01 ft movement in the last 10 s |
| G2 Hard landing | 5 aircraft, 4 rates, 15 s: everything finite, no runaway |
| G3 Extreme impacts | 60 crash runs: no more runaways than the floor |
| G4 NASA case 02 | 480 and 1000 Hz, against NASA sims 01 and 04: rates < 2e-6 deg/s, attitude < 1e-3 deg |
| G5 Rigid body | 2 bodies, 7 spins, 60 s: energy and angular-momentum magnitude within 1e-6 |
| G6 Parity | WebAssembly against native of the same source, in controlled flight |

Every gate is measured in native JSBSim and in WebAssembly, and must pass on both.

## Step 4: the floor and candidate 1 against every gate

**Candidate 1** is `wasm/patches/0001-integrator-aware-friction.patch` (about 100 added lines in 4 files).

- JSBSim sizes ground friction so that slip is zero after the next step, assuming that step is an Euler step.
  The patch tells the friction code which integrators are really in use.
- It is switched by a new property, `simulation/integrator/friction-aware`: 0 = JSBSim unchanged (default),
  1 = candidate 1, 2 = the 2010 code's formula, kept for comparison.
- It follows the 2010 idea but is not a copy. Two things had to change for v1.3.3:
  - Translation and rotation use different integrators by default (AB2 and Euler). The 2010 code corrected each
    separately, which is only exact when they are the same. The patch weights the two parts of the friction
    equations instead.
  - JSBSim now integrates velocity in a frame that does not rotate with the Earth. The 2010 formula then leaves
    a small bias (ledger 16). The patch removes it.

Full table (`results/03-gates-summary.txt`; per-configuration detail in `results/03-gates-<name>.txt`):

| Gate | Floor | C1, AB4 | C1, AB3 | C1, AB2 |
|---|---|---|---|---|
| **G1 Rest** | **PASS** 20 of 20; worst rate 1.2e-8 rad/s | **FAIL** 19 of 20; c310 at 120 Hz: 1.9e-2 rad/s, moved 0.6 ft | **PASS** 20 of 20; worst 1.6e-8 | **PASS** 20 of 20; worst 1.0e-8 |
| **G2 Hard landing** | **FAIL** 15 of 20 finite. Fails: 737 at 120, 240 Hz; ah1s at 120, 240, 480 Hz | **FAIL** 13 of 20. Fails: 737 at 120, 240, 1000* Hz; ah1s at all four rates | **FAIL** 14 of 20. Fails: 737 at 120*, 240, 480* Hz; ah1s at 120, 240, 480* Hz | **FAIL** 14 of 20. Fails: 737 at 120, 240*, 480* Hz; ah1s at 120, 240, 480 Hz |
| **G3 Extreme impacts** (runaways of 60, native / WebAssembly) | reference: 9 / 10 | **WORSE**: 16 / 16 | **WORSE**: 13 / 12 | **WORSE**: 12 / 12 |
| **G4 NASA**, rate error deg/s (gate 2e-6) | **FAIL** 9.2e-2 at 480 Hz; 4.4e-2 at 1000 Hz | **PASS** 1.4e-6; 3.2e-7 | **PASS** 1.4e-6; 3.2e-7 | **FAIL** 5.4e-5; 1.2e-5 |
| G4, attitude error deg (gate 1e-3) | fail: 0.52; 0.25 | pass: 1.6e-5; 3.8e-6 | pass: 1.6e-5; 3.8e-6 | pass: 9.2e-5; 2.1e-5 |
| **G5 Rigid body**, cases within 1e-6 | **FAIL** 2 of 14 at both rates; worst drift 5.5 (480 Hz), 0.8 (1000 Hz) | **FAIL** 9 of 14 at 480 Hz, 11 of 14 at 1000 Hz; worst 3.6e-5, 8.3e-6 | **FAIL** 9 and 11 of 14; worst 4.9e-5, 8.3e-6 | **FAIL** 4 and 9 of 14; worst 8.1e-5, 1.5e-5 |
| **G6 Parity** | **PASS** | **PASS** | **PASS** | **PASS** |
| Cost, c172x at 1000 Hz in Node, flight / on the ground | 16.8 / 21.5 us | 18.2 / 22.3 us | 17.2 / 21.9 us | 19.5 / 21.4 us |

`*` = failed on one platform only (native or WebAssembly); the other stayed finite. This is the chaos of ledger 14.

G4 position differences (not gated): a constant 0.67 ft in ECEF X from t = 0, which comes from the planet radius
in `brick.xml`; altitude within 0.001 ft; the rest below 1e-5 ft.

Two extra comparison runs:

| | G1 | G2 | G3 | G4 | G5 | G6 |
|---|---|---|---|---|---|---|
| Floor's integrators **with** the friction patch on (`c1-euler`) | PASS | FAIL, 16 of 20 (all pass at 480 and 1000 Hz) | PASS, 9 / 8 | FAIL | FAIL | PASS |
| AB4 with the 2010 formula (`c1x-ab4-2010formula`) | FAIL, 19 of 20, and creeps up to 2.3e-3 ft in 10 s | FAIL, 12 of 20 | worse, 16 / 15 | PASS | FAIL | PASS |

Hard landings and crashes by step rate (failures, native / WebAssembly):

| | G2 at 120, 240, 480, 1000 Hz (of 5 each) | G3 at 120, 240, 480, 1000 Hz (of 15 each) |
|---|---|---|
| Floor | 2/2, 2/2, 1/1, 0/0 | 3/4, 3/3, 2/2, 1/1 |
| C1, AB4 | 2/2, 2/2, 1/1, 2/1 | 5/5, 4/4, 4/4, 3/3 |
| C1, AB3 | 1/2, 2/2, 1/1, 0/0 | 5/5, 4/3, 2/2, 2/2 |
| C1, AB2 | 2/2, 1/2, 2/1, 0/0 | 5/5, 2/2, 2/2, 3/3 |
| Floor + patch | 2/2, 2/2, 0/0, 0/0 | 3/3, 3/2, 2/2, 1/1 |

Reading: at 1000 Hz, hard landings survive with the floor, with AB3 and with AB2, but not with AB4.

## What we learned

- **Friction was half of the ground problem.** With the patch, a resting aircraft settles under every multistep
  scheme. The other half is the gear's spring and damper. A stiff damper needs a small enough step; AB4 needs a
  much smaller one than Euler. That is our reading of the c310 result and of the hard-landing failures (ledger
  13 is tested, ledger 15 is not).
- **This points at candidate 3** (AB in the air, Euler while touching the ground), now with a concrete reason.
  But it can be no better than the floor on the ground, and the floor itself fails hard landings at 120 and
  240 Hz.
- **G2 and G3 need statistics.** One run per case is a coin toss in the chaotic cases. Session 04 should repeat
  each case with tiny perturbations and count.
- **G5 mixes two things.** For AB4 the whole failure is JSBSim's start-up of the multistep history, in the first
  4 steps; after that the energy is constant. The gate is kept and the result stands. A separate, later gate
  that measures drift after the start-up would tell the two apart (to be written before session 04's candidates
  run).
- **AB3 is worth carrying forward** next to AB4: same NASA accuracy at 480 and 1000 Hz, settles on all five
  aircraft at all four rates, and survives hard landings at 1000 Hz.

## Things a reader should know

- **Where I chose, not you.** `GATES.md` lists them. The main ones:
  - G5 gates the magnitude of angular momentum, not its direction (the direction is reported).
  - G5 is gated at 480 and 1000 Hz, with a spin list I wrote before running anything.
  - G2 also fails a run whose rates pass 1e6 rad/s or that never touches the ground.
  - G3 compares counts.
- **Seen before the gates commit:** the two reference configurations' results, including G5 numbers for
  unpatched AB4. The spin list was not changed after seeing them. In torque-free flight candidate 1 behaves like
  unpatched AB4, so I knew before committing that AB4 would fail G5 at the fast spins, and left the gate alone.
- **The patch is in the shipped binary, switched off.** One binary serves the floor and the candidates, and
  ledger 5 shows that "off" is bit-identical to unpatched. The floor itself was run on the unpatched builds, as
  asked.
- **The patch has three modes, not one.** Mode 2 (the 2010 formula) is there to show what the adaptation changes.
- **Not bit-reproducible builds:** two builds of the same source differ in 336 bytes (JSBSim embeds the build
  time). Results are identical; hashes are per build.
- **Pushed to `main`** at each checkpoint, as the prompt asked, and to the session branch.
- **Not done:** no iPhone run of the new build (the page at https://135crewdog.github.io/FDM/ now serves it; a
  Chromium run is in `results/03-page-chromium-fwasm-exceptions.txt`). No memory-leak audit. The exact first
  invalid operation in the f16 crash is still unknown.

## What remains for session 04

1. Before running anything, add the later gates:
   - G5b: energy and momentum drift measured after the start-up steps.
   - G2b and G3b: each case repeated with tiny perturbations, judged on the fraction that survives.
   - Decide which step rates the game will really use, and say which rates each gate is judged at.
2. **Candidate 2:** implicit-midpoint body rates (PteroLabsAI/jsbsim PR 13) as patch 0002, with its own switch.
   It should pass G5 by construction; the open question is the ground.
3. **Candidate 3:** AB3 or AB4 in the air, Euler while any contact point (BOGEY or STRUCTURE) touches, with and
   without patch 0001. Watch the switch itself.
4. Test the Reasoned items: the gear-damper stability explanation (ledger 15).
5. Then the integrator decision, and a second independent review before the wing-strip work builds on it.

## What an independent reviewer should check first

1. **The patch's mathematics** (`wasm/patches/0001-integrator-aware-friction.patch`, mode 1): the weighting of
   the friction matrix and the extra right-hand-side terms. Ledger 19 is my own derivation.
2. **Whether the gates were really fixed first:** `git log` around `164c1d0`, and the frozen-file diff.
3. **My choices in G5** (magnitude, not direction; the spin list; start-up counted), and whether G5b is fair.
4. **The reading of G2 and G3** given the chaos (ledger 12 and 14): is "worse than the floor" real or noise?
5. **The c310 explanation** (ledger 13 and 15): only an ablation was done.
6. **The binding's handle scheme and error boundary** (`wasm/bindings.cpp`): is any path still unguarded?

## How to reproduce

```sh
npm ci
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
source <emsdk>/emsdk_env.sh                       # Emscripten 6.0.13
scripts/build-native.sh                           # build/native/unpatched and build/native/patched
scripts/build-wasm.sh                             # wasm/bin (patched, switch off by default)
PATCHSET=unpatched scripts/build-wasm.sh          # build/wasm-bin-unpatched
NATIVE=patched scripts/run-tests.sh               # tests 0-5 -> results/03-test*.txt
tests/native/verify_key.sh unpatched pip          # the source build is a valid answer key
tests/native/verify_key.sh patched unpatched      # the patch changes nothing while off (native)
tests/native/verify_wasm_patch_off.sh             # the same for WebAssembly
tests/gates/run.sh floor                          # then c1-ab4, c1-ab3, c1-ab2, c1-euler, c1x-ab4-2010formula
.venv/bin/python tests/gates/summary.py floor c1-ab4 c1-ab3 c1-ab2
```
