# FDM2 02 Work: YASim baseline

---

Name this chat "FDM2 02 Work: YASim baseline" (if you cannot, ask me to in your first line).

Read `CLAUDE.md`, `README.md`, `PLAN.md` and `RESEARCH.md` on `main` first, and follow their rules. Then read
`REPORT.md` on the branch `baseline/jsbsim` (tag `jsbsim-baseline-v1` if it exists; otherwise the commit named in
`PLAN.md`): it is the pattern for this session and it records what went wrong there.

**Goal:** FlightGear's YASim flight model compiled to WebAssembly with upstream physics, plus the smallest glue
that lets it run outside FlightGear, on a new branch `baseline/yasim` created from `main`. Same idea as the
JSBSim baseline: prove it against a native build of the same code and put a test page on the iPhone.

**Start with a short research step and write it down before anything is built** (file `RESEARCH-yasim.md` on the
branch, each fact with its source and a Verified / Supported / Reasoned label):
- Which FlightGear and SimGear release to pin, and why. YASim lives in FlightGear (`src/FDM/YASim`) and uses
  SimGear (property tree, XML reading, maths).
- The full list of what YASim needs from FlightGear and SimGear, and for each item: compile it unchanged, or
  replace it with a small stand-in. Upstream has a standalone YASim test program; check whether it already shows
  the minimum.
- How YASim is driven: load and its solver, initial state, step size and its own sub-steps, controls in, state
  out, ground and gear, turbulence and any other random input, crash handling.
- Which aircraft to use. YASim aircraft files live in FlightGear's data repositories, which are large. Pick a
  small set (for example one light piston aircraft, one jet, one helicopter) and record each file's licence.
- Licences: YASim and SimGear are GPL-2 or later / LGPL; record exactly what applies to what is shipped. A build
  that combines YASim with JSBSim (LGPL-2.1) would be GPL.
- If this research shows the build is clearly more than one session, stop after writing it, rewrite this prompt
  into two, and say so. One goal per session.

**Decided already (do not ask again):**
- Runs in a Web Worker; also timed on the main thread.
- The test page deploys from `main`: copy only the built page (it replaces or sits beside the JSBSim page; say
  which in the report). `main` already has the Pages workflow; it uploads `test-page/` as it is.
- Built binaries are committed in a folder that is not git-ignored, with a build-info file.
- No physics patches and no integrator tuning on a baseline branch.

**Reuse from `baseline/jsbsim` (tooling only, copy the files, do not merge the branch):**
- `tests/lib/compare.ts` and its self-test (trace comparison, the classes, the refusals).
- `ts/loop.ts`, `ts/worker-handler.ts`, `ts/files.ts`, the page skeleton in `web/`, `scripts/build-page.mjs`,
  the Chromium run in `tests/page.chromium.mjs`.
- The shape of the build: one CMake file for native and WebAssembly, flags set for all code, a script that stops
  on any error, a flag check from `compile_commands.json`, a build self-test, a repeat-build comparison.
- The shape of the answer key: one C++ scenario runner compiled into both the native program and the
  WebAssembly binary, plus a TypeScript-driven run that must equal the C++ run bit for bit.

**Write the pass/fail lines differently this time** (the JSBSim session had to stop twice because of this):
- WebAssembly and native agree to the last digit only until something amplifies a last-digit difference: a gear
  spring, a heading that sits on the 0 / 2π seam, an autopilot, a numerical blow-up. A fixed tiny limit is only
  right for smooth airborne runs.
- So make the main parity line noise-relative from the start: WebAssembly may differ from native by no more than
  3 times what native differs from itself when its start state is nudged by one last digit. Nudge altitude and
  heading (and anything else the research shows YASim is sensitive to). Keep position limits fixed and tight.
- For a run that ends in a failure (NaN, crash), do not require "the same step"; require the same kind of
  failure, and judge the rows before it.
- Before trusting any scenario's name, read back from the run that it is what it claims (on the slope, on the
  ground, engine running, and so on).

## Done means
Write this list at the top of `REPORT.md` on the new branch before any build. Never change it after seeing a
result (CLAUDE.md rule 3).

1. **Research written** (`RESEARCH-yasim.md`), including pins and licences.
2. **Pin and build.** Pinned FlightGear and SimGear commits, pinned Emscripten (6.0.13 unless the research gives a
   reason). Exceptions as the code needs them, for all code; an `-fwasm-exceptions` build and an `-fexceptions`
   fallback if exceptions are used at all. `-O3`, no fast-math, fixed memory size. The build stops on any error.
   Binaries and build-info committed. Every upstream file compiled is listed; every stand-in file is listed with
   what it replaces.
3. **Answer key.** Native build of the same code with the same wrapper C++.
4. **Wrapper (C++ + TypeScript).** One instance per load; step size fixed before load; controls in and state out
   through a bulk `Float64Array`; validated writes; errors become a JavaScript `Error` with the original message;
   log routed to JavaScript; crash and end reported as events.
5. **Ground.** YASim's own ground interface fed from a height grid we supply. Flat ground and a slope, against
   native running the same C++, with the slope read back from the run.
6. **Loop.** The same `FixedStepLoop` and Worker handler as the JSBSim baseline, with their tests.
7. **Load test.** Every chosen aircraft that loads (and solves) natively also does in WebAssembly. Table.
8. **Parity.** Step by step against native for each chosen aircraft: on the ground at rest, a take-off or hover,
   and a smooth airborne run with fixed control inputs. Lines written before the run, noise-relative as above.
   Random inputs off, read back.
9. **iPhone page.** As for JSBSim: user agent; batched timing at YASim's usual step sizes, in the Worker and on
   the main thread; a broken aircraft caught and shown; create and destroy 20 times; I paste the results back.
10. **Finish.** Tag `yasim-baseline-v1`, or record the commit in `PLAN.md` if the tag push is refused. Write the
    next prompt (stage 3: what to combine, decided from the two baselines), update `PLAN.md` and
    `prompts/README.md`, push.

**Out of scope:** changing YASim's physics or solver, combining with JSBSim, real terrain data, rendering.

If something fails, report it with evidence and stop. Keep messages to me short and plain; I read them on my
phone.
