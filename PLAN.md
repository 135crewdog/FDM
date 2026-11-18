# Plan (attempt 2)

Update this file at the end of every session: mark what is done, link the report, and name the next step.

## Done

- **Session 00 (research), 2026-11-18:** `RESEARCH.md` on `main`. User decisions recorded in `CLAUDE.md`.
- **Session 01 (JSBSim baseline), 2026-11-18:** branch `baseline/jsbsim` at `e478825`, report `REPORT.md` on
  that branch. The tag `jsbsim-baseline-v1` is to be created by the user (below).

## Stage 1: JSBSim baseline (`baseline/jsbsim`)

**Status:** done. The baseline is commit `e47882503ab765d575a38b5bcd59fd41da76b1ae`, the last commit of
`baseline/jsbsim`.

**The tag still has to be created by the user.** The session's git proxy refused the tag push (HTTP 403,
2026-11-18). On GitHub: Releases → "Draft a new release" → "Choose a tag" → type `jsbsim-baseline-v1` → "Create
new tag on publish" → Target: branch `baseline/jsbsim` (check that its last commit is `e478825`) → publish.
Later work starts from that tag, not from the moving branch. Do not add commits to `baseline/jsbsim` before the
tag exists.

**What exists** (details and evidence labels in `REPORT.md` on the branch):
- JSBSim v1.3.3 (`66f7fafc`), unpatched, built with Emscripten 6.0.13: `dist-wasm/fdm-weh` (`-fwasm-exceptions`)
  and `dist-wasm/fdm-jseh` (`-fexceptions`), `-O3`, fixed memory 16 MiB. A rebuild in another folder is
  byte-identical.
- Host layer: C++ wrapper with plain C exports, height-grid ground callback, logger; TypeScript wrapper, fixed-step
  loop, Worker handler. Native answer key built from the same C++.
- Test page: `test-page/` on `main`, published at `https://135crewdog.github.io/FDM/` by
  `.github/workflows/pages.yml` (uploads the folder as it is).

**Results against the done-criteria:**
- Wrapper, loop, load test (59 of 61 aircraft load everywhere; the same 2 fail everywhere), external forces: pass.
- Ground hook: passes, except one frozen line (slope run, Class A) that was written too tight for ground contact.
  It is kept as failed; the run passes the line added with the user's agreement (Class N).
- Parity: c1723, f16_test and NASA cases 01, 02, 03 meet their lines. In the wider sweep of the other 59 script
  files, 56 meet their line and **3 fail a frozen line and are kept as failed** (`c3104`, `c3105`,
  `mk82_script`). In all three, native differs from itself by the same amount after a one-last-digit change
  (user decision 2026-11-18: record, add no new line, continue).
- iPhone (Safari 27.2, the user's device): both builds pass every page line. About 8 µs per step with
  `-fwasm-exceptions` and 18 µs with `-fexceptions`, in the Worker and on the main thread, at every step size;
  20 forces cost about 1 µs; no heap growth over 20 create/destroy cycles; 20 fresh modules and 20 Workers
  complete.

**Left open on purpose** (not baseline work): `-flto`, Emscripten 7, stack depth, the fallback on a real
Safari 26.0, a real page-hidden event on the device. Listed in `REPORT.md` with the test that would settle each.

## Stage 2: YASim baseline (`baseline/yasim`)

**Status:** next (`prompts/02-yasim-baseline.md`).

**Goal:** FlightGear's YASim compiled to WebAssembly the same way, with only the minimum glue it needs to run
outside FlightGear (YASim depends on SimGear's property tree and XML parsing).

**Done when:** the same checks as stage 1, as far as they apply.
- The answer key is native YASim, the same code built natively.
- YASim is GPL-2. A combined build with JSBSim (LGPL-2.1) would be GPL. Record the licences in the report.
- The result is tagged `yasim-baseline-v1`.

## Stage 3: integration (`integrate/*`)

**Status:** not started.

**Goal:** to be decided after stages 1 and 2, from their tags. This is also where game-specific physics work
(wing-strip forces, ground model, integrator choice) happens, never on the baselines.
