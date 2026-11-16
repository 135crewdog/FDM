# Session 05: ground model and default integrator

Date: 2026-11-16. Raw outputs: `results/05-*`. **This report is written checkpoint by checkpoint; the sections
below the first are filled in as each checkpoint is reached.**

## Checkpoint 1 (done): set-up, reproduction, the review's binding defects

What was done:

- Everything rebuilt from scratch in a fresh container (Emscripten 6.0.13, native answer keys from source).
- Tests 0 to 5, the patch-off checks, and the floor and `c3-ab4` through every existing gate: every line equals
  session 04's reports except timings, and two new lines in test 0 (the build-failure checks added after the
  review, which pass). Files: `results/05-repro-*.txt`.
- The binding gaps of REVIEW-codex-04 are closed, each with a regression test that failed before and passes now
  (`tests/binding/regress.ts` section 8; 38 failures before, 129 of 129 after, both variants;
  `results/05-binding-before-*.txt`, `05-binding-after-*.txt`):
  - a script's own time step is checked before anything is loaded (negative, zero, infinite, missing);
  - `contact-active`, `contact-switches` and the eight midpoint counters are read-only; a negative or infinite
    hold time and an unknown release mode are refused (new patch `0003b`, see below);
  - `setIntegrators` reads each setting once and undoes earlier writes if a later one fails.
- **Patch `0003b-validated-switch-settings.patch`** (new; patches 0002 and 0003 are untouched, so their hashes in
  session 04's results still match). It changes property access only. With it in the build:
  - "off" is still bit-identical to unpatched JSBSim (11 native logs, 18 WebAssembly logs;
    `results/05b-native-key-*.txt`, `05b-wasm-patched-off-*.txt`);
  - the gate reports of `c3-ab4` and `c2-mid` (G1 to G6, G5b, G2b, G3b, G2c) equal session 04's line for line,
    apart from timings and the patch list (`results/05b-*.txt`).
  - Earlier results it could touch: none numerically (shown above for the two candidates). The diagnostics that
    read the counters only read them.

## Checkpoint 2 (done): fixtures and gates, committed before any candidate ran through them

| what | commit | when |
|---|---|---|
| Gates G2d, G8, G3d, G7, their fixtures, runners and judge (`GATES-05.md`, `tests/gates/gates-05.json`, `sim05.py`, `sim05.ts`, `run_native_05.py`, `run_wasm_05.ts`, `evaluate_05.py`) | **`888654f5b41fd0090c751542d5eb8da5f12cfd90`** | before the floor, `c3-ab4` or `c2-mid` had been run through any of them, and before patch 0004 was built |

What had been seen when they were written is listed in `GATES-05.md` ("What had been seen"): everything in
REPORT-04 and the review, about 310 fixture trials on JSBSim's default integrators (all logged in
`results/05-fixture-trials*.jsonl`), and one harness check of the whole pipeline on JSBSim's defaults
(`results/05-new-ref-default-05.txt`).
